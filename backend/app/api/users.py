"""用户管理接口（Step4）：
- POST   /api/users/            注册（公开）
- GET    /api/users/            用户列表（仅管理员，分页语义同 submissions）
- POST   /api/users/admin       创建管理员（仅管理员）
- GET    /api/users/{user_id}   用户详情（仅本人或管理员）
- PUT    /api/users/{user_id}/role  权限变更（仅管理员，记录操作日志）
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, require_admin
from app.core import messages
from app.core.exceptions import ApiError
from app.core.response import success
from app.services import users as user_service

router = APIRouter()


class RegisterBody(BaseModel):
    # 长度校验交给 pydantic（触发 422→400 统一处理器）；service 内再做 strip 后防御校验
    username: str = Field(min_length=user_service.USERNAME_MIN, max_length=user_service.USERNAME_MAX)
    password: str = Field(min_length=user_service.PASSWORD_MIN)


class AdminBody(BaseModel):
    username: str = Field(min_length=user_service.USERNAME_MIN, max_length=user_service.USERNAME_MAX)
    password: str = Field(min_length=user_service.PASSWORD_MIN)


class RoleBody(BaseModel):
    role: str


@router.post("/api/users/")
async def register(body: RegisterBody):
    data = user_service.register(body.username, body.password)
    return success(msg="register success", data=data)


@router.get("/api/users/")
async def list_users(
    page: int | None = Query(default=None),
    page_size: int | None = Query(default=None),
    admin: dict = Depends(require_admin),
):
    total, users = user_service.list_users(page, page_size)
    return success(msg="success", data={"total": total, "users": users})


@router.post("/api/users/admin")
async def create_admin(body: AdminBody, admin: dict = Depends(require_admin)):
    user = user_service.register(body.username, body.password)  # 注册为普通 user
    # 提升为 admin
    changed = user_service.change_role(admin, user["user_id"], "admin")
    return success(msg="success", data={"user_id": changed["user_id"], "username": body.username.strip()})


@router.get("/api/users/{user_id}")
async def get_user(user_id: str, current: dict = Depends(get_current_user)):
    # 仅本人或管理员；普通用户访问他人一律 403（不泄露存在性），管理员查不存在 → 404
    if current["role"] != "admin" and current["user_id"] != user_id:
        raise ApiError(403, messages.PERMISSION_DENIED)
    user = user_service.get_by_user_id(user_id)
    if user is None:
        raise ApiError(404, messages.USER_NOT_FOUND)
    return success(msg="success", data=user_service.to_public(user))


@router.put("/api/users/{user_id}/role")
async def change_user_role(user_id: str, body: RoleBody, admin: dict = Depends(require_admin)):
    data = user_service.change_role(admin, user_id, body.role)
    return success(msg="role updated", data=data)
