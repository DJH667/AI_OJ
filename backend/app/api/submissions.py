"""提交评测接口（官方 Step2 主体；列表/详情/rejudge 属 Step3，D4 实现）：
- POST /api/submissions/  提交评测（登录；429 单人单题 >3 次/分钟；404 题目/语言不存在）
"""
import asyncio
import threading

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core import messages
from app.core.exceptions import ApiError
from app.core.response import success
from app.services import judge, languages, problems, submissions, users

router = APIRouter()

# 评测任务串行锁（P1 并发修复，2026-09-04）：
# judge 内统计读-改-写（submit/resolve_count）与"该题是否已有 AC"扫描非原子；
# 官方仅要求单用户串行 → 用 threading.Lock 让评测任务排队执行。
# 说明：评测逻辑在 asyncio.to_thread 的线程池执行，故用 threading.Lock（不用 asyncio.Lock，
# 后者绑定 event loop，TestClient/多 loop 场景会跨 loop 冲突）。
JUDGE_LOCK = threading.Lock()


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

    # 异步评测（官方建议 asyncio.create_task；全局锁串行，评测逻辑放线程池）
    asyncio.create_task(_judge_serial(record["submission_id"]))

    return success(msg="success", data={"submission_id": record["submission_id"], "status": "pending"})
