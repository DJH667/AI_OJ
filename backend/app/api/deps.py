"""FastAPI 依赖：get_current_user / require_admin（供 Step1–6 全部受保护接口复用）。

关键语义：
- 服务端 session：读 Cookie 中 session id → 查 data/sessions/ → 校验过期；
- 每次请求【实时查库】取用户与角色 ⇒ banned 会话立即失效（决策 dec-0f895a1ddd678090）；
- 判定顺序 401 > 403：无/失效会话 → 401；已登录但被 ban 或权限不足 → 403。
"""
from fastapi import Depends, Request

from app.core import messages
from app.core.exceptions import ApiError
from app.services import sessions, users as user_service


async def get_current_user(request: Request) -> dict:
    sid = request.cookies.get(sessions.SESSION_COOKIE)
    if not sid:
        raise ApiError(401, messages.NOT_LOGGED_IN)
    session = sessions.get_session(sid)
    if session is None:
        raise ApiError(401, messages.NOT_LOGGED_IN)
    user = user_service.get_by_username(session["username"])
    if user is None:
        # 用户已不存在（如 reset 清空后残留会话），会话作废
        sessions.delete_session(sid)
        raise ApiError(401, messages.NOT_LOGGED_IN)
    if user["role"] == "banned":
        # banned 会话立即失效：请求实时命中 403
        raise ApiError(403, messages.USER_BANNED)
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise ApiError(403, messages.PERMISSION_DENIED)
    return user
