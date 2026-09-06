"""日志访问审计（官方 Step5）与评测日志读取辅助。

- 审计条目 action 统一为 "view_logs"（助教澄清 2026-09-02）；
- 记录"已鉴权且资源存在"的日志访问（成功 200 或被拒 403）；
  未登录（401）/ submission 不存在（404）/ 参数错误不记录（api.md"不必记录"）；
- 查询：user_id/problem_id 至少其一（全空 400，助教确认 2026-09-03），分页语义同 submissions。
"""
from datetime import datetime

from app import config
from app.db import store
from app.services.pagination import normalize_page


def record_access(user: dict, problem_id: str, status_code: int) -> None:
    """记录一次日志访问（登录用户、资源存在前提下；200/403 均记录，便于审计"被拒"）。"""
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    store.save_json(config.ACCESS_LOGS_DIR, f"{stamp}-{user['user_id']}", {
        "user_id": user["user_id"],
        "username": user.get("username", ""),
        "problem_id": problem_id,
        "action": "view_logs",
        "time": datetime.now().isoformat(timespec="seconds"),
        "status": str(status_code),
    })


def query_access(
    user_id: str | None,
    problem_id: str | None,
    page: int | None,
    page_size: int | None,
) -> list[dict]:
    """审计查询：按 user/problem 过滤，按时间倒序（最新在前），返回分页后的条目数组。"""
    page, page_size = normalize_page(page, page_size)
    entries = [e for _, e in store.iter_all(config.ACCESS_LOGS_DIR)]
    if user_id is not None:
        entries = [e for e in entries if e.get("user_id") == user_id]
    if problem_id is not None:
        entries = [e for e in entries if e.get("problem_id") == problem_id]
    entries.sort(key=lambda e: e.get("time", ""), reverse=True)
    if page_size is None:
        return entries
    start = (page - 1) * page_size
    return entries[start:start + page_size]
