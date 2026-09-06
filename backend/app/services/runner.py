"""语言无关的程序编译/运行原语（供评测 judge 与 AI 对拍引擎共用）。

- 基于语言注册表（languages）的 compile_cmd/run_cmd；{src}/{exe} 替换为相对路径（./main.ext），
  全部在 cwd=临时目录 内执行（不泄露绝对路径）；
- 支持超时 kill（TLE）与 psutil 内存监控（MLE），并记录耗时与峰值内存；
- 输出归一：忽略行末空格与末尾多余换行。
"""
import shlex
import subprocess
import threading
import time
from pathlib import Path

import psutil

COMPILE_TIMEOUT = 30.0  # 编译超时（秒）


def normalize(text: str) -> str:
    """输出归一：每行去除行末空白、去除末尾多余空行（api.md：忽略行末空格与最后多余换行）。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [line.rstrip() for line in lines]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines).rstrip("\n")


def build_cmd(template: str, src_ref: str, exe_ref: str | None) -> list[str]:
    cmd = template.replace("{src}", src_ref)
    if exe_ref is not None:
        cmd = cmd.replace("{exe}", exe_ref)
    return shlex.split(cmd)


def compile_source(language: dict, workdir: Path, src_ref: str, exe_ref: str) -> tuple[dict | None, bool]:
    """返回 (compile_info, ok)。无编译命令 → (None, True)。"""
    template = language.get("compile_cmd")
    if not template:
        return None, True
    cmd = build_cmd(template, src_ref, exe_ref)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=COMPILE_TIMEOUT, cwd=workdir)
    except subprocess.TimeoutExpired:
        return {"result": "compile error", "message": "compile timeout"}, False
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "").strip()[-2000:]
        return {"result": "compile error", "message": message or "unknown compile error"}, False
    return {"result": "success", "message": ""}, True


def _monitor_memory(proc: subprocess.Popen, mem_limit_mb: float, holder: dict) -> None:
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


def run_case(cmd: list[str], input_text: str, timeout: float, workdir: Path,
             mem_limit_mb: float = 128.0) -> dict:
    """运行单个输入，返回 {returncode, output, timed_out, mle, time, memory}。"""
    started = time.perf_counter()
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=workdir,
        )
    except OSError:
        return {"returncode": None, "output": "", "timed_out": False, "mle": False,
                "time": 0.0, "memory": 0, "error": "cannot launch"}
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
        return {"returncode": None, "output": "", "timed_out": True, "mle": False,
                "time": round(timeout, 3), "memory": holder["peak"], "error": "timeout"}
    monitor.join(timeout=2)
    elapsed = round(time.perf_counter() - started, 3)
    return {"returncode": proc.returncode, "output": out, "timed_out": False,
            "mle": holder["mle"], "time": elapsed, "memory": holder["peak"], "error": ""}
