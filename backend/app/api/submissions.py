"""提交评测接口（官方 Step2 + Step3）：
- POST /api/submissions/            提交评测（登录；429 单人单题；404 题目/语言不存在）
- GET  /api/submissions/            评测列表（本人/管理员；一级条件至少其一；分页；摘要裁剪）
- GET  /api/submissions/{id}        评测详情（仅本人或管理员）
- PUT  /api/submissions/{id}/rejudge 重新评测（仅管理员，覆盖原记录回 pending）
"""
import asyncio
import threading

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin
from app.core import messages
from app.core.exceptions import ApiError
from app.core.response import success
from app.services import judge, languages, problems, submissions, users

router = APIRouter()

# 评测任务串行锁（P1 并发修复，2026-09-04）：见模块注释与 d3 实现说明 §6。
JUDGE_LOCK = threading.Lock()

DETAIL_FIELDS = (
    "submission_id", "user_id", "problem_id", "language", "code",
    "status", "score", "counts", "compile_info", "run_info", "error_info",
)


class SubmissionBody(BaseModel):
    problem_id: str
    language: str
    code: str


def _judge_locked(submission_id: str) -> None:
    with JUDGE_LOCK:
        judge.judge_submission(submission_id)


async def _judge_serial(submission_id: str) -> None:
    await asyncio.to_thread(_judge_locked, submission_id)


@router.post("/api/submissions/")
async def create_submission(body: SubmissionBody, current: dict = Depends(get_current_user)):
    # 异常顺序 429 > 404：先做限频判定（按 单人单题，助教确认 2026-09-03）
    if submissions.count_recent_submissions(current["user_id"], body.problem_id) >= submissions.RATE_LIMIT:
        raise ApiError(429, messages.RATE_LIMITED)
    problem = problems.get(body.problem_id)
    if problem is None:
        raise ApiError(404, messages.PROBLEM_NOT_FOUND)
    language = languages.get(body.language)
    if language is None:
        raise ApiError(404, messages.LANGUAGE_NOT_FOUND)

    record = submissions.new_pending(current, body.problem_id, body.language, body.code)
    submissions.save(record)

    # 用户提交计数（按提交算，一题可多次）；event loop 单线程串行，无并发窗口
    user = users.get_by_username(current["username"])
    user["submit_count"] = user.get("submit_count", 0) + 1
    users.save_user(user)

    asyncio.create_task(_judge_serial(record["submission_id"]))

    return success(msg="success", data={"submission_id": record["submission_id"], "status": "pending"})


@router.get("/api/submissions/")
async def list_submissions(
    user_id: str | None = Query(default=None),
    problem_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int | None = Query(default=None),
    page_size: int | None = Query(default=None),
    current: dict = Depends(get_current_user),
):
    # 权限归一（api.md/需求 §5 Step3）：普通用户只能查自己的记录
    if current["role"] != "admin":
        if user_id is not None and user_id != current["user_id"]:
            raise ApiError(403, messages.PERMISSION_DENIED)
        user_id = current["user_id"]
    # 一级条件（user_id/problem_id）不可全空
    if user_id is None and problem_id is None:
        raise ApiError(400, messages.FILTER_REQUIRED)
    total, items = submissions.list_records(user_id, problem_id, status, page, page_size)
    return success(msg="success", data={"total": total, "submissions": items})


@router.get("/api/submissions/{submission_id}")
async def get_submission(submission_id: str, current: dict = Depends(get_current_user)):
    record = submissions.get(submission_id)
    if record is None:
        raise ApiError(404, messages.SUBMISSION_NOT_FOUND)
    if current["role"] != "admin" and record.get("user_id") != current["user_id"]:
        raise ApiError(403, messages.PERMISSION_DENIED)
    data = {k: record.get(k) for k in DETAIL_FIELDS}
    return success(msg="success", data=data)


@router.put("/api/submissions/{submission_id}/rejudge")
async def rejudge_submission(submission_id: str, admin: dict = Depends(require_admin)):
    submissions.reset_for_rejudge(submission_id)  # 404 inside；覆盖为 pending
    asyncio.create_task(_judge_serial(submission_id))
    return success(msg="rejudge started", data={"submission_id": submission_id, "status": "pending"})
