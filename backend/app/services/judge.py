"""评测执行器（官方 Step2 主体；psutil 内存监控在 D4 收尾）。

流程：读提交 → 取题目/语言 → 编译（如需要，C++ 先编译再运行）→ 逐测例运行 →
输出比对（忽略行末空格与最后多余换行）→ 结构化结果。
- 测试点结果：AC/WA/TLE/MLE(占位)/RE/CE/UNK；submission 状态：pending/success/error；
- CE 时 submission 状态记为 success（评测流程正常完成，结果见 compile_info；2026-09-04 决策，
  见 d3-implementation-notes §6 与 ta-qa-pending Q5）；
- 计分：score=通过测例数×10，counts=测例总数×10；
- 评测以同步阻塞形式在线程池执行（API 层以全局锁串行调度，见 api/submissions.py）；
- error_info / compile_info.message 不泄露服务器路径/临时目录：编译与运行均在
  cwd=临时目录 内、命令使用相对路径（./main.ext），g++ 报错不再带 /tmp/oj_judge_* 前缀。
"""
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from app import config
from app.core import messages
from app.db import store
from app.services import languages, problems, submissions, users

COMPILE_TIMEOUT = 30.0  # 编译超时（秒）


class _JudgeError(Exception):
    """评测级错误（安全 msg，不泄露内部路径）。"""


def _normalize(text: str) -> str:
    """输出归一：每行去除行末空格/制表，去除末尾多余空行（api.md：忽略行末空格与最后多余换行）。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [line.rstrip() for line in lines]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines).rstrip("\n")


def _build_cmd(template: str, src_ref: str, exe_ref: str | None) -> list[str]:
    """{src}/{exe} 替换为相对路径引用（如 ./main.cpp），配合 cwd 使用；{src} 必须是路径而非裸文件名。"""
    cmd = template.replace("{src}", src_ref)
    if exe_ref is not None:
        cmd = cmd.replace("{exe}", exe_ref)
    return shlex.split(cmd)


def _compile(language: dict, workdir: Path, src_ref: str, exe_ref: str) -> tuple[dict | None, bool]:
    """返回 (compile_info, ok)。无编译命令 → (None, True)。"""
    template = language.get("compile_cmd")
    if not template:
        return None, True
    cmd = _build_cmd(template, src_ref, exe_ref)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=COMPILE_TIMEOUT, cwd=workdir)
    except subprocess.TimeoutExpired:
        return {"result": "compile error", "message": "compile timeout"}, False
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "").strip()[-2000:]
        return {"result": "compile error", "message": message or "unknown compile error"}, False
    return {"result": "success", "message": ""}, True


def _run_case(cmd: list[str], input_text: str, timeout: float, workdir: Path) -> dict:
    """运行单个测例，返回 {result:None|AC|WA|TLE|RE|UNK, output, time, memory}。"""
    started = time.perf_counter()
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=workdir,
        )
    except OSError:
        return {"result": "UNK", "output": "", "time": 0.0, "memory": 0}
    try:
        out, _err = proc.communicate(input=input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.communicate(timeout=1)
        except Exception:
            pass
        return {"result": "TLE", "output": "", "time": round(timeout, 3), "memory": 0}
    elapsed = round(time.perf_counter() - started, 3)
    if proc.returncode != 0:
        return {"result": "RE", "output": "", "time": elapsed, "memory": 0}
    return {"result": None, "output": out, "time": elapsed, "memory": 0}


def judge_submission(submission_id: str) -> None:
    """执行一次评测并落盘；AC 时按"一题最多一次"更新 resolve_count。

    调用方（api/submissions.py）保证同一时刻只有一个评测任务在跑（全局锁串行），
    因此统计的读-改-写安全；本函数不做额外并发防护。
    """
    record = submissions.get(submission_id)
    if record is None:
        return
    workdir: Path | None = None
    try:
        problem = problems.get(record["problem_id"])
        if problem is None:
            raise _JudgeError("problem not found")
        language = languages.get(record["language"])
        if language is None:
            raise _JudgeError("language not found")
        testcases = problem.get("testcases", []) or []
        timeout = float(problem.get("time_limit") or language.get("time_limit") or 3.0)

        workdir = Path(tempfile.mkdtemp(prefix="oj_judge_"))
        ext = language.get("file_ext", ".txt")
        src_ref = f"./main{ext}"
        exe_ref = "./main"
        (workdir / src_ref[2:]).write_text(record.get("code", ""), encoding="utf-8")

        compile_info, compile_ok = _compile(language, workdir, src_ref, exe_ref)
        record["compile_info"] = compile_info

        details: list[dict] = []
        ac_count = 0
        if compile_ok:
            run_template = language["run_cmd"]
            if "{exe}" in run_template and not language.get("compile_cmd"):
                raise _JudgeError("language run command requires compiled executable")
            cmd = _build_cmd(run_template, src_ref, exe_ref if language.get("compile_cmd") else None)
            for idx, case in enumerate(testcases, start=1):
                case_input = case.get("input", "")
                r = _run_case(cmd, case_input, timeout, workdir)
                if r["result"] is None:
                    expected = case.get("output", "")
                    actual = r["output"]
                    r["result"] = "AC" if _normalize(expected) == _normalize(actual) else "WA"
                    if r["result"] == "AC":
                        ac_count += 1
                details.append({"id": idx, "result": r["result"], "time": r["time"], "memory": r["memory"]})
            record["run_info"] = {"result": "finished", "message": f"{len(testcases)} test cases finished"}
        else:
            # CE：编译失败，不再运行（submission 状态仍为 success，见模块 docstring）
            record["run_info"] = None
        record.update(
            status="success",
            score=ac_count * 10,
            counts=len(testcases) * 10,
            details=details,
            error_info="",
        )
    except _JudgeError as exc:
        record.update(status="error", error_info=str(exc), details=[])
    except Exception:
        record.update(status="error", error_info=messages.JUDGE_FAILED, details=[])
    finally:
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)

    submissions.save(record)
    _update_resolve_on_ac(record)


def _update_resolve_on_ac(record: dict) -> None:
    """该用户该题首次 AC（全部测例通过）时 resolve_count +1（一题最多一次）。

    依赖外层评测串行锁：同用户同题两个提交不会并发完成。
    """
    if not submissions.is_ac(record):
        return
    user_id = record["user_id"]
    problem_id = record["problem_id"]
    submission_id = record["submission_id"]
    already = False
    for _, other in store.iter_all(config.SUBMISSIONS_DIR):
        if (
            other.get("submission_id") != submission_id
            and other.get("user_id") == user_id
            and other.get("problem_id") == problem_id
            and submissions.is_ac(other)
        ):
            already = True
            break
    if already:
        return
    user = users.get_by_username(record["username"])
    if user is None:
        return
    user["resolve_count"] = user.get("resolve_count", 0) + 1
    users.save_user(user)
