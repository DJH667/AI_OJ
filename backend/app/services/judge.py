"""评测执行器（官方 Step2 主体；psutil 内存监控在 D4 收尾）。

流程：读提交 → 取题目/语言 → 编译（如需要，C++ 先编译再运行）→ 逐测例运行 →
输出比对（忽略行末空格与最后多余换行）→ 结构化结果。
- 测试点结果：AC/WA/TLE/MLE/RE/CE/UNK；submission 状态：pending/success/error；
- CE → status=error（用户判定 2026-09-05，遵循一般共识；compile_info 保留供详情展示，
  score/counts=0，不跑测例）；error 也用于评测框架级问题（题目/语言缺失等）；
- 计分：score=通过测例数×10，counts=测例总数×10（CE/框架错误为 0）；
- 评测以同步阻塞形式在线程池执行（API 层以全局锁串行调度，见 api/submissions.py）；
- error_info / compile_info.message 不泄露服务器路径/临时目录：编译与运行均在
  cwd=临时目录 内、命令使用相对路径（./main.ext），g++ 报错不再带 /tmp/oj_judge_* 前缀。
"""
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import psutil

from app.core import messages
from app.services import languages, problems, submissions

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


def _monitor_memory(proc: subprocess.Popen, mem_limit_mb: float, holder: dict) -> None:
    """FAQ 参考：psutil 轮询用户进程 RSS，超限即 kill（→MLE），并记录峰值内存（MB）。"""
    try:
        p = psutil.Process(proc.pid)
    except psutil.Error:
        return
    peak = 0.0
    while proc.poll() is None:
        try:
            rss_mb = p.memory_info().rss / (1024 ** 2)
        except (psutil.Error, ProcessLookupError):
            break
        peak = max(peak, rss_mb)
        if peak > mem_limit_mb:
            proc.kill()
            holder["mle"] = True
            break
        time.sleep(0.02)
    holder["peak"] = round(peak, 1)


def _run_case(cmd: list[str], input_text: str, timeout: float, workdir: Path, mem_limit_mb: float) -> dict:
    """运行单个测例；含超时 kill（TLE）与 psutil 内存监控（MLE），返回峰值内存。

    返回 {result:None|AC|WA|TLE|MLE|RE|UNK, output, time, memory}。
    """
    started = time.perf_counter()
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=workdir,
        )
    except OSError:
        return {"result": "UNK", "output": "", "time": 0.0, "memory": 0}
    holder = {"mle": False, "peak": 0.0}
    monitor = threading.Thread(target=_monitor_memory, args=(proc, mem_limit_mb, holder), daemon=True)
    monitor.start()
    try:
        out, _err = proc.communicate(input=input_text, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            proc.communicate(timeout=1)
        except Exception:
            pass
        monitor.join(timeout=2)
        return {"result": "TLE", "output": "", "time": round(timeout, 3), "memory": holder["peak"]}
    monitor.join(timeout=2)
    elapsed = round(time.perf_counter() - started, 3)
    if holder["mle"]:
        return {"result": "MLE", "output": "", "time": elapsed, "memory": holder["peak"]}
    if proc.returncode != 0:
        return {"result": "RE", "output": "", "time": elapsed, "memory": holder["peak"]}
    return {"result": None, "output": out, "time": elapsed, "memory": holder["peak"]}


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
        mem_limit_mb = float(problem.get("memory_limit") or language.get("memory_limit") or 128)

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
                r = _run_case(cmd, case_input, timeout, workdir, mem_limit_mb)
                if r["result"] is None:
                    expected = case.get("output", "")
                    actual = r["output"]
                    r["result"] = "AC" if _normalize(expected) == _normalize(actual) else "WA"
                    if r["result"] == "AC":
                        ac_count += 1
                details.append({"id": idx, "result": r["result"], "time": r["time"], "memory": r["memory"]})
            record["run_info"] = {"result": "finished", "message": f"{len(testcases)} test cases finished"}
            final_status = "success"
            final_counts = len(testcases) * 10
        else:
            # CE：编译失败 → submission 状态为 error（用户判定 2026-09-05，一般共识），
            # 不再运行测例；compile_info 保留供详情展示；score/counts 记 0（无评测结果）。
            record["run_info"] = None
            final_status = "error"
            final_counts = 0
        record.update(
            status=final_status,
            score=ac_count * 10,
            counts=final_counts,
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
    # Q6（2026-09-05 用户判定）：评测完成（含 rejudge）后实时重算该用户统计
    # （submit=现存提交数、resolve=AC 题目去重数），幂等、无读改写竞态。
    submissions.recompute_stats(record.get("username", ""))
