"""站点配置接口（polish 2026-09-09）：
- GET /api/site-config   站点设置（登录可读；前端按此渲染编辑入口）
- PUT /api/site-config   修改设置（仅管理员；当前仅 allow_user_edit 开关）
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user, require_admin
from app.core.response import success
from app.services import site_config

router = APIRouter()


class SiteConfigBody(BaseModel):
    allow_user_edit: bool = True


@router.get("/api/site-config")
async def get_site_config(current: dict = Depends(get_current_user)):
    return success(msg="success", data=site_config.get())


@router.put("/api/site-config")
async def update_site_config(body: SiteConfigBody, admin: dict = Depends(require_admin)):
    data = site_config.set_allow_user_edit(body.allow_user_edit)
    return success(msg="site config updated", data=data)
