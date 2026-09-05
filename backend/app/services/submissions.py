"""提交记录数据层与统计口径（评测执行见 services/judge.py）。

- 全 JSON 存储：submissions/{id}.json，id 为自增数字字符串（api.md 示例 "123"）；
- 记录字段：submission_id/user_id/username/problem_id/language/code/status/score/counts/
  compile_info/run_info/error_info/details/created_at；
- 429 限频口径（助教确认 2026-09-03）：同一用户对**同一题目** 1 分钟内提交 >3 次；
- 删除题目的统计回退（助教确认）：submit_count 按提交数减、resolve_count 若该题 AC 过减 1。
"""
from datetime import datetime, timedelta

from app import config
from app.db import store
from app.services import users as user_service

RATE_WINDOW = timedelta(seconds=60)
RATE_LIMIT = 3  # 1 分钟内同人同题最多 3 次提交


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def next_submission_id() -> str:
    maximum = 0
    for key in store.list_keys(config.SUBMISSIONS_DIR):
        try:
            maximum = max(maximum, int(key))
        except ValueError:
            continue
    return str(maximum + 1)


def get(submission_id: str) -> dict | None:
    return store.load_json(config.SUBMISSIONS_DIR, submission_id)


def delete(submission_id: str) -> None:
    store.delete_json(config.SUBMISSIONS_DIR, submission_id)


def save(record: dict) -> None:
    store.save_json(config.SUBMISSIONS_DIR, record["submission_id"], record)


def new_pending(user: dict, problem_id: str, language: str, code: str) -> dict:
    submission_id = next_submission_id()
    return {
        "submission_id": submission_id,
        "user_id": user["user_id"],
        "username": user["username"],
        "problem_id": problem_id,
        "language": language,
        "code": code,
        "status": "pending",
        "score": 0,
        "counts": 0,
        "compile_info": None,
        "run_info": None,
        "error_info": "",
        "details": [],
        "created_at": _now_iso(),
    }


def count_recent_submissions(user_id: str, problem_id: str) -> int:
    """1 分钟窗口内该用户对该题的提交数（429 口径：单人单题）。"""
    threshold = (datetime.now() - RATE_WINDOW).isoformat(timespec="seconds")
    count = 0
    for _, rec in store.iter_all(config.SUBMISSIONS_DIR):
        if rec.get("user_id") == user_id and rec.get("problem_id") == problem_id:
            if rec.get("created_at", "") >= threshold:
                count += 1
    return count


def list_records(
    user_id: str | None,
    problem_id: str | None,
    status: str | None,
    page: int | None,
    page_size: int | None,
) -> tuple[int, list[dict]]:
    """评测列表（api.md §10 / 需求 §5 Step3）。

    调用方（API 层）已完成权限归一与"一级条件至少其一"检查；
    此处负责 status 过滤、按提交时间倒序（最新在前）、分页（语义同 submissions 列表）。
    列表摘要：pending/error 条目只含 submission_id+status；其余含 submission_id/status/score/counts。
    """
    from app.services.pagination import normalize_page

    page, page_size = normalize_page(page, page_size)
    records = [rec for _, rec in store.iter_all(config.SUBMISSIONS_DIR)]
    if user_id is not None:
        records = [r for r in records if r.get("user_id") == user_id]
    if problem_id is not None:
        records = [r for r in records if r.get("problem_id") == problem_id]
    if status is not None:
        records = [r for r in records if r.get("status") == status]
    records.sort(key=lambda r: int(r["submission_id"]) if r["submission_id"].isdigit() else 0, reverse=True)
    total = len(records)
    if page_size is None:
        return total, [summary(r) for r in records]
    start = (page - 1) * page_size
    return total, [summary(r) for r in records[start:start + page_size]]


def summary(record: dict) -> dict:
    """列表条目（api.md：pending/error 只需 submission_id+status；其余含 score/counts）。"""
    if record.get("status") in ("pending", "error"):
        return {"submission_id": record["submission_id"], "status": record["status"]}
    return {
        "submission_id": record["submission_id"],
        "status": record["status"],
        "score": record.get("score", 0),
        "counts": record.get("counts", 0),
    }


def reset_for_rejudge(submission_id: str) -> dict:
    """rejudge：覆盖原记录为 pending（复用评测流程重新判定）。"""
    record = get(submission_id)
    if record is None:
        from app.core.exceptions import ApiError
        from app.core.messages import SUBMISSION_NOT_FOUND

        raise ApiError(404, SUBMISSION_NOT_FOUND)
    record.update(status="pending", score=0, counts=0, compile_info=None, run_info=None, error_info="", details=[])
    save(record)
    return record


def is_ac(record: dict) -> bool:
    """AC 口径：评测完成（success）且全部测例通过（score == counts > 0）。"""
    return record.get("status") == "success" and record.get("counts", 0) > 0 and record.get("score") == record.get("counts")


def delete_all_for_problem(problem_id: str) -> None:
    """删除某题全部提交并回退相关用户统计（助教确认 2026-09-03）。"""
    affected: dict[str, dict] = {}  # username -> {"submits": n, "ac": bool}

    def _account(username: str) -> dict:
        if username not in affected:
            affected[username] = {"submits": 0, "ac": False}
        return affected[username]

    for key, rec in list(store.iter_all(config.SUBMISSIONS_DIR)):
        if rec.get("problem_id") != problem_id:
            continue
        acc = _account(rec.get("username", ""))
        acc["submits"] += 1
        if is_ac(rec):
            acc["ac"] = True
        store.delete_json(config.SUBMISSIONS_DIR, key)

    for username, acc in affected.items():
        user = user_service.get_by_username(username)
        if user is None:
            continue
        user["submit_count"] = max(0, user.get("submit_count", 0) - acc["submits"])
        if acc["ac"]:
            user["resolve_count"] = max(0, user.get("resolve_count", 0) - 1)
        user_service.save_user(user)
