"""AI 命题对拍引擎（"硬核模式"，2026-09-05 定案，仅本地执行，不对外）。

协议（模型在硬核模式须于问题 JSON 的 meta 提供，均用所选语言 python/cpp/…）：
- meta.generator：测试数据生成器——运行后向 stdout 输出 JSON 数组
  [{"input": "...", "small": true|false}]（small 缺省按输入文本长度 ≤512 判定）；
- meta.std_solution：标准/正解代码——对每个输入计算 expected；
- meta.brute_solution：朴素/暴力对照代码——仅对小规模输入运行，与 std 输出比对。

流程：编译三程序（按语言注册，复用 runner）→ 生成器产输入集 → std 求 expected →
小点 brute 对照 → 全部一致返回 testcases（含大小梯度、无错误数据）；不一致/异常抛 VerifyError
（消息摘要用于回传大模型重试，不泄露服务器路径）。
"""
import json
import shutil
import tempfile
from pathlib import Path

from app.services import languages, runner

SMALL_INPUT_CHARS = 512


class VerifyError(Exception):
    """对拍失败（携带可回传给 AI 的中文/英文摘要）。"""


def _prepare_program(language: dict, workdir: Path, name: str, code: str) -> list[str]:
    """写源码并按语言编译，返回 run cmd（list）；任何失败抛 VerifyError。"""
    ext = language.get("file_ext", ".txt")
    src_ref = f"./{name}{ext}"
    exe_ref = f"./{name}"
    (workdir / src_ref[2:]).write_text(code or "", encoding="utf-8")
    compile_info, ok = runner.compile_source(language, workdir, src_ref, exe_ref)
    if not ok:
        message = (compile_info or {}).get("message", "unknown compile error")
        raise VerifyError(f"{name} compile error: {message[:400]}")
    if language.get("compile_cmd"):
        return runner.build_cmd(language["run_cmd"], src_ref, exe_ref)
    return runner.build_cmd(language["run_cmd"], src_ref, None)


def _run(cmd: list[str], input_text: str, workdir: Path, timeout: float, mem_mb: float = 128.0) -> str:
    res = runner.run_case(cmd, input_text, timeout, workdir, mem_mb)
    if res["mle"]:
        raise VerifyError("program exceeded memory limit (MLE)")
    if res["timed_out"]:
        raise VerifyError(f"program timed out (>{timeout}s)")
    if res["returncode"] is None:
        raise VerifyError("program could not be launched")
    if res["returncode"] != 0:
        raise VerifyError(f"program exited with code {res['returncode']}")
    return res["output"]


def verify_problem(problem_json: dict, language_name: str, timeout: float = 5.0,
                   mem_mb: float = 128.0) -> list[dict]:
    """执行一轮对拍；通过返回 testcases（[{input, output}]，全量、含大小梯度）；失败抛 VerifyError。"""
    language = languages.get(language_name)
    if language is None:
        raise VerifyError(f"language not supported: {language_name}")
    meta = problem_json.get("meta") or {}
    for key in ("generator", "std_solution", "brute_solution"):
        if not meta.get(key):
            raise VerifyError(f"hardcore mode requires meta.{key}")

    workdir = Path(tempfile.mkdtemp(prefix="oj_verify_"))
    try:
        gen_cmd = _prepare_program(language, workdir, "gen", meta["generator"])
        std_cmd = _prepare_program(language, workdir, "std", meta["std_solution"])
        brute_cmd = _prepare_program(language, workdir, "brute", meta["brute_solution"])

        raw = _run(gen_cmd, "", workdir, timeout, mem_mb)
        try:
            cases = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VerifyError(f"generator output is not valid JSON: {exc}") from exc
        if not isinstance(cases, list) or not cases:
            raise VerifyError("generator produced no cases")
        if len(cases) > 20:
            cases = cases[:20]  # 限制用例数量

        testcases = []
        for idx, case in enumerate(cases, start=1):
            input_text = case.get("input", "")
            if not isinstance(input_text, str):
                raise VerifyError(f"case {idx} has non-string input")
            expected = _run(std_cmd, input_text, workdir, timeout, mem_mb)
            is_small = bool(case.get("small")) if isinstance(case.get("small"), bool) else len(input_text) <= SMALL_INPUT_CHARS
            if is_small:
                brute_out = _run(brute_cmd, input_text, workdir, timeout, mem_mb)
                if runner.normalize(expected) != runner.normalize(brute_out):
                    raise VerifyError(
                        f"mismatch on small case {idx}: std vs brute differ\n"
                        f"input(head): {input_text[:200]}\nstd(head): {expected[:200]}\nbrute(head): {brute_out[:200]}"
                    )
            testcases.append({"input": input_text, "output": expected})
        return testcases
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
