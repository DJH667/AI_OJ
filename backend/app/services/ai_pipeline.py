"""AI 命题任务执行管线（后台线程运行，R1–R4 + 硬核对拍）。

流程（单任务）：
1) 组装 system/user prompt（题目 JSON schema、语言规则、硬核三代码要求、完整性/梯度/无错误数据）；
2) 调用 LLM（真实或 mock）→ 解析结构化题目 JSON → 校验语言（纯文本兜底拒绝）；
3) hardcore：对拍（ai_verify.verify_problem）——失败把 VerifyError 摘要追加为反馈再请求
   （retry_limit 为额外重试次数），用尽 → completed + review=True（题目不入库）；
   普通模式：直接接受 AI 产出 testcases；
4) 统计 usage（多轮累计）并按 model-config 单价算费用（R4）；
中断（P1 修复 2026-09-07）：写任何状态前经 _guard_interrupted 读最新任务——
cancel 一旦置位即转 interrupted，后续阶段不再覆盖为 running/completed/failed。
"""
import json

from app.services import ai_config, ai_tasks, ai_verify, languages, llm_client, problems

SYSTEM_PROMPT = """你是一个 OJ 命题助手。严格只输出一个 JSON（不要代码块围栏、不要额外文字），结构如下：
{
  "id": "短横线小写标识", "title": "...", "description": "...",
  "input_description": "...", "output_description": "...",
  "samples": [{"input": "...", "output": "..."}],
  "constraints": "...",
  "testcases": [{"input": "...", "output": "..."}],   // 完整评测点：必须给出全部、含规模梯度（小/中/大），大点应能区分不同复杂度算法；数据不得有错误
  "time_limit": 1.0, "memory_limit": 128,
  "difficulty_score": 数字,
  "language": "题目/代码语言（必须是已支持语言）",
  "meta": {
    "std_solution": "用所选语言编写的正解代码",
    "brute_solution": "用所选语言编写的朴素/暴力对照代码（小数据规模）",
    "generator": "用所选语言编写的测试数据生成器：向 stdout 输出 JSON 数组 [{\\"input\\": \\"...\\", \\"small\\": true|false}]；large 输入规模应足以使较劣复杂度（如 O(n^2)）超时"
  }
}
要求：题目与输入的知识点/难度/预期复杂度/数据规模一致；samples 清晰；testcases 覆盖边界并含多档规模；
除硬核对拍所需 meta 外，代码均须为能通过评测的所选语言。若用户要求了未支持/未注册的语言，
不要生成题目，直接输出 {"error": "language not supported: <语言>"}。"""


def _fence_strip(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def _parse_problem(content: str) -> dict:
    try:
        problem = json.loads(_fence_strip(content))
    except json.JSONDecodeError as exc:
        raise ValueError(f"model output is not valid JSON: {exc}") from exc
    if not isinstance(problem, dict):
        raise ValueError("model output is not a JSON object")
    return problem


def _guard_interrupted(task_id: str) -> bool:
    """P1 修复（评审 9.7）：写状态前先读最新任务；若已请求中断则置 interrupted 并返回 True（调用方应终止）。"""
    t = ai_tasks.get(task_id)
    if t is None:
        return True
    if t.get("cancel_requested"):
        if t["status"] != ai_tasks.STATUS_INTERRUPTED:
            ai_tasks.set_status(t, ai_tasks.STATUS_INTERRUPTED, "任务已中断")
        return True
    return False


def _reference_context(problem_id: str | None) -> str:
    """站内参考题上下文（仅题面/限制，不含测试点）。"""
    if not problem_id:
        return ""
    data = problems.get(problem_id)
    if data is None:
        return ""
    return (
        f"\n参考已有题目（{problem_id}，难度分 {data.get('difficulty_score')}）：\n"
        f"标题：{data.get('title','')}\n描述：{data.get('description','')}\n"
        f"输入：{data.get('input_description','')}\n输出：{data.get('output_description','')}\n"
        f"限制：{data.get('constraints','')}\n"
    )


def run_task(task_id: str) -> None:
    task = ai_tasks.get(task_id)
    if task is None:
        return
    username = task.get("username") or "admin"
    if _guard_interrupted(task_id):
        return
    ai_tasks.set_status(task, ai_tasks.STATUS_RUNNING, "正在处理命题需求")
    usage_acc = {"prompt_tokens": 0, "completion_tokens": 0}

    def finish(status: str, progress: str, **fields) -> None:
        if _guard_interrupted(task_id):
            return
        t = ai_tasks.get(task_id)
        if t is None:
            return
        t.update(fields)
        t["usage"] = ai_config.estimate_cost(usage_acc, username)
        ai_tasks.save(t)
        ai_tasks.set_status(t, status, progress)

    try:
        ref = _reference_context(task.get("problem_id"))
        user_prompt = (
            f"命题需求：{task.get('requirement')}\n"
            f"语言：{task.get('language') or '（由你按需选择已支持语言）'}\n"
            + ref
            + ("模式：硬核（必须给出 meta 三代码，测试点须经对拍校验）" if task.get("hardcore")
               else "模式：普通（直接给出完整 samples 与 testcases）")
        )
        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        max_calls = (task.get("retry_limit", 0) or 0) + 1  # retry_limit 为额外重试次数

        while True:
            if _guard_interrupted(task_id):
                return
            resp = llm_client.chat(messages, username)
            usage_acc["prompt_tokens"] += int(resp["usage"].get("prompt_tokens", 0))
            usage_acc["completion_tokens"] += int(resp["usage"].get("completion_tokens", 0))
            if _guard_interrupted(task_id):  # chat 返回后先查中断，不再被 RUNNING/终态覆盖
                return

            try:
                problem = _parse_problem(resp["content"])
            except ValueError as exc:
                finish(ai_tasks.STATUS_FAILED, "解析失败", error=str(exc), result=None)
                return
            if problem.get("error"):
                finish(ai_tasks.STATUS_FAILED, "模型拒绝（语言不支持等）", error=str(problem["error"]), result=None)
                return

            language_name = task.get("language") or problem.get("language") or "python"
            if languages.get(language_name) is None:
                available = ", ".join(languages.all_names())
                finish(ai_tasks.STATUS_FAILED, "语言不支持",
                       error=f"language not supported: {language_name}; available: {available}", result=None)
                return
            problem["language"] = language_name

            if not task.get("hardcore"):
                finish(ai_tasks.STATUS_COMPLETED, "命题完成", result=problem)
                return

            # 硬核：对拍
            if _guard_interrupted(task_id):
                return
            t = ai_tasks.get(task_id)
            ai_tasks.set_status(t, ai_tasks.STATUS_RUNNING, "硬核对拍校验中")
            try:
                verified = ai_verify.verify_problem(problem, language_name)
            except ai_verify.VerifyError as exc:
                t = ai_tasks.get(task_id)
                if _guard_interrupted(task_id):
                    return
                t["attempts"] = t.get("attempts", 0) + 1
                ai_tasks.save(t)
                if t["attempts"] >= max_calls:
                    finish(ai_tasks.STATUS_COMPLETED, "对拍未通过，需人工复核",
                           review=True, review_note=f"对拍 {t['attempts']} 次未通过，请人工复核：{exc}",
                           result=None)
                    return
                messages = messages[:1] + [{
                    "role": "user",
                    "content": f"对拍未通过（第 {t['attempts']} 次），错误摘要：{exc}\n请修正代码/生成器后重新只输出完整 JSON。",
                }]
                continue
            # 对拍通过：以对拍集作为 testcases（无错误数据、含梯度）
            if _guard_interrupted(task_id):
                return
            problem["testcases"] = verified
            finish(ai_tasks.STATUS_COMPLETED, "对拍通过，命题完成", result=problem)
            return
    except Exception as exc:  # 兜底（安全消息；若已中断保持 interrupted）
        if _guard_interrupted(task_id):
            return
        finish(ai_tasks.STATUS_FAILED, "执行异常", error=f"ai task failed: {type(exc).__name__}", result=None)
