"""提交评测接口（官方 Step2 主体；列表/详情/rejudge 属 Step3，D4 实现）：
- POST /api/submissions/  提交评测（登录；429 单人单题 >3 次/分钟；404 题目/语言不存在）
"""
import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core import messages
from app.core.exceptions import ApiError
from app.core.response import success
from app.services import judge, languages, problems, submissions, users

router = APIRouter()


class SubmissionBody(BaseModel):
    problem_id: str
    language: str
    code: str


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

    # 用户提交计数（按提交算，一题可多次）
    user = users.get_by_username(current["username"])
    user["submit_count"] = user.get("submit_count", 0) + 1
    users.save_user(user)

    # 异步评测（官方建议 asyncio.create_task；同步评测放线程池执行）
    asyncio.create_task(asyncio.to_thread(judge.judge_submission, record["submission_id"]))

    return success(msg="success", data={"submission_id": record["submission_id"], "status": "pending"})
