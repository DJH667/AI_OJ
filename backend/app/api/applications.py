"""题目修改/删除申请接口（polish 2026-09-08，用户反馈 2）：
- POST /api/problems/{problem_id}/apply   提交申请（登录；409 已有 pending 申请）
- GET  /api/applications/                申请列表（管理员=全部；普通用户=仅自己）
- PUT  /api/applications/{application_id} 审批（仅管理员；accept 执行 / reject 标记）
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin
from app.core import messages
from app.core.exceptions import ApiError
from app.core.response import success
from app.services import applications as application_service
from app.services import problems as problem_service

router = APIRouter()


class ApplyBody(BaseModel):
    action: str  # "edit" | "delete"
    payload: dict | None = None  # edit 时的完整题目字段


class DecideBody(BaseModel):
    decision: str  # "accept" | "reject"


@router.post("/api/problems/{problem_id}/apply")
async def apply_change(problem_id: str, body: ApplyBody, current: dict = Depends(get_current_user)):
    if body.action not in application_service.ACTIONS:
        raise ApiError(400, messages.INVALID_ACTION)
    problem = problem_service.get(problem_id)
    if problem is None:
        raise ApiError(404, messages.PROBLEM_NOT_FOUND)
    if application_service.has_pending(current["user_id"], problem_id):
        raise ApiError(409, messages.APPLICATION_ALREADY_PENDING)
    data = application_service.create(
        current, problem_id, problem.get("title", ""), body.action, body.payload,
    )
    return success(msg="application created", data=data)


@router.get("/api/applications/")
async def list_applications(
    status: str | None = Query(default=None),
    problem_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    current: dict = Depends(get_current_user),
):
    # 权限归一：普通用户只能看自己的申请
    if current["role"] != "admin":
        user_id = current["user_id"]
    items = application_service.list_records(status=status, user_id=user_id, problem_id=problem_id)
    return success(msg="success", data={"total": len(items), "applications": items})


@router.put("/api/applications/{application_id}")
async def decide_application(application_id: str, body: DecideBody,
                             admin: dict = Depends(require_admin)):
    if body.decision not in ("accept", "reject"):
        raise ApiError(400, messages.INVALID_ACTION)
    data = application_service.decide(application_id, body.decision, admin)
    return success(msg=f"{body.decision} success", data=data)
