"""POST /api/reset/ —— 系统重置（测试支持接口）。

api.md：清空测试产生的用户、题目和提交数据，退出当前登录状态，
并重新创建初始管理员账户。权限"仅管理员"（测试环境可不校验），
异常含 401（未登录）/ 403（权限不足）——按异常处理顺序 401 > 403 > … 落实。

实现（2026-09-03 依据 api.md 修正）：默认 require admin（未登录 401、非管理员 403）；
若评测确需免登录调用，将 config.RESET_REQUIRE_ADMIN 置 False（"测试环境可不校验"）。
reset 会清空 sessions 目录，实现"退出当前登录状态"。
"""
from fastapi import APIRouter, Request

from app import config
from app.api.deps import get_current_user
from app.core import messages
from app.core.exceptions import ApiError
from app.core.response import success
from app.db import store
from app.db.seed import ensure_admin
from app.services import languages as lang_service

router = APIRouter()


@router.post("/api/reset/")
async def reset_system(request: Request):
    if config.RESET_REQUIRE_ADMIN:
        current = await get_current_user(request)
        if current["role"] != "admin":
            raise ApiError(403, messages.PERMISSION_DENIED)
    store.clear_all()                            # 用户/题目/提交/语言/日志/会话全部清空
    ensure_admin()                               # 重建初始管理员
    lang_service.ensure_builtin_languages()      # 重建内置 python/cpp（注册接口仍可用）
    return success(msg="system reset successfully")
