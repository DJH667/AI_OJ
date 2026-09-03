"""认证接口：POST /api/auth/login、POST /api/auth/logout（Step4）。
"""
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.response import success
from app.services import sessions, users as user_service

router = APIRouter()


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/api/auth/login")
async def login(body: LoginBody, response: Response):
    user = user_service.authenticate(body.username, body.password)
    sid = sessions.create_session(user)
    sessions.set_session_cookie(response, sid)
    return success(
        msg="login success",
        data={"user_id": user["user_id"], "username": user["username"], "role": user["role"]},
    )


@router.post("/api/auth/logout")
async def logout(request: Request, response: Response, user: dict = Depends(get_current_user)):
    sid = request.cookies.get(sessions.SESSION_COOKIE)
    if sid:
        sessions.delete_session(sid)
    sessions.clear_session_cookie(response)
    return success(msg="logout success")
