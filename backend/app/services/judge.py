"""评测执行器（官方 Step2/3）。

流程：读提交 → 取题目/语言 → 编译（如需要）→ 逐测例运行 → 输出归一比对 → 结构化结果。
- 程序编译/运行/资源限制复用 services/runner.py（judge 与 AI 对拍引擎共用同一执行原语）；
- 测试点结果：AC/WA/TLE/MLE/RE/CE/UNK；submission 状态：pending/success/error；
- CE → status=error（用户判定 2026-09-05）；error 亦用于评测框架级问题（题目/语言缺失等）；
- 计分：score=通过测例数×10，counts=测例总数×10（CE/框架错误为 0）；
- 评测完成（含 rejudge）后实时重算该用户统计（Q6）：submissions.recompute_stats。
"""
import shutil
import tempfile
from pathlib import Path

from app.core import messages
from app.services import languages, problems, runner, submissions

DEFAULT_TIMEOUT = 3.0
DEFAULT_MEMORY_MB = 128.0


class _JudgeError(Exception):
    """评测级错误（安全 msg，不泄露内部路径）。"""


def judge_submission(submission_id: str) -> None:
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
        timeout = float(problem.get("time_limit") or language.get("time_limit") or DEFAULT_TIMEOUT)
        mem_limit_mb = float(problem.get("memory_limit") or language.get("memory_limit") or DEFAULT_MEMORY_MB)

        workdir = Path(tempfile.mkdtemp(prefix="oj_judge_"))
        ext = language.get("file_ext", ".txt")
        src_ref = f"./main{ext}"
        exe_ref = "./main"
        (workdir / src_ref[2:]).write_text(record.get("code", ""), encoding="utf-8")

        compile_info, compile_ok = runner.compile_source(language, workdir, src_ref, exe_ref)
        record["compile_info"] = compile_info

        details: list[dict] = []
        ac_count = 0
        if compile_ok:
            run_template = language["run_cmd"]
            if "{exe}" in run_template and not language.get("compile_cmd"):
                raise _JudgeError("language run command requires compiled executable")
            cmd = runner.build_cmd(run_template, src_ref, exe_ref if language.get("compile_cmd") else None)
            for idx, case in enumerate(testcases, start=1):
                case_input = case.get("input", "")
                res = runner.run_case(cmd, case_input, timeout, workdir, mem_limit_mb)
                if res["mle"]:
                    verdict = "MLE"
                elif res["timed_out"]:
                    verdict = "TLE"
                elif res["returncode"] is None:
                    verdict = "UNK"
                elif res["returncode"] != 0:
                    verdict = "RE"
                else:
                    expected = case.get("output", "")
                    verdict = "AC" if runner.normalize(expected) == runner.normalize(res["output"]) else "WA"
                    if verdict == "AC":
                        ac_count += 1
                details.append({"id": idx, "result": verdict, "time": res["time"], "memory": res["memory"]})
            record["run_info"] = {"result": "finished", "message": f"{len(testcases)} test cases finished"}
            final_status = "success"
            final_counts = len(testcases) * 10
        else:
            # CE：编译失败 → submission 状态 error（用户判定 2026-09-05）；compile_info 保留
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
        record.update(status="error", error_info=str(exc), details=[], score=0, counts=0,
                      compile_info=None, run_info=None)  # P3 兜底清零（评审 9.7）
    except Exception:
        record.update(status="error", error_info=messages.JUDGE_FAILED, details=[], score=0, counts=0,
                      compile_info=None, run_info=None)
    finally:
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)

    submissions.save(record)
    # Q6（2026-09-05）：评测完成（含 rejudge）后实时重算该用户统计
    submissions.recompute_stats(record.get("username", ""))
