"""评测日志接口（官方 Step5）：
- GET  /api/submissions/{submission_id}/log     评测日志（可见性见需求文档 §5 Step5 / ta-qa Q7）
- PUT  /api/problems/{problem_id}/log_visibility  配置日志公开（仅管理员）
- GET  /api/logs/access/                         日志访问审计（仅管理员；user_id/problem_id 至少其一）
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin
from app.core import messages
from app.core.exceptions import ApiError
from app.core.response import success
from app.services import logs as log_service
from app.services import problems, submissions

router = APIRouter()


@router.get("/api/submissions/{submission_id}/log")
async def submission_log(submission_id: str, current: dict = Depends(get_current_user)):
    record = submissions.get(submission_id)
    if record is None:
        raise ApiError(404, messages.SUBMISSION_NOT_FOUND)  # 不存在不记录审计
    problem_id = record.get("problem_id", "")
    public = problems.get_public_cases(problem_id)
    is_admin = current["role"] == "admin"
    is_owner = record.get("user_id") == current["user_id"]

    if not is_admin and not public:
        if not is_owner:
            log_service.record_access(current, problem_id, 403)
            raise ApiError(403, messages.PERMISSION_DENIED)
        # 本人 + 未公开：可见 score/counts，但 details 不可见（助教 Q7）
        log_service.record_access(current, problem_id, 200)
        return success(msg="success", data={
            "details": [],
            "score": record.get("score", 0),
            "counts": record.get("counts", 0),
        })

    # 管理员 或 题目公开（本人/所有登录用户均可看 details）
    log_service.record_access(current, problem_id, 200)
    return success(msg="success", data={
        "details": record.get("details", []),
        "score": record.get("score", 0),
        "counts": record.get("counts", 0),
    })


class PublicCasesBody(BaseModel):
    public_cases: bool = False


@router.put("/api/problems/{problem_id}/log_visibility")
async def set_log_visibility(problem_id: str, body: PublicCasesBody, admin: dict = Depends(require_admin)):
    problems.set_public_cases(problem_id, body.public_cases)  # 404 inside
    return success(msg="log visibility updated", data={"problem_id": problem_id, "public_cases": body.public_cases})


@router.get("/api/logs/access/")
async def list_access_logs(
    user_id: str | None = Query(default=None),
    problem_id: str | None = Query(default=None),
    page: int | None = Query(default=None),
    page_size: int | None = Query(default=None),
    admin: dict = Depends(require_admin),
):
    if user_id is None and problem_id is None:
        raise ApiError(400, messages.FILTER_REQUIRED)
    entries = log_service.query_access(user_id, problem_id, page, page_size)
    return success(msg="success", data=entries)
