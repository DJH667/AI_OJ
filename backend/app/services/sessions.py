"""服务端 session（D2 起用）。

约定（需求文档 §4.3/加密传输边界）：Cookie 只携带 uuid4 session id，不含明文身份；
会话内容存 data/sessions/{sid}.json，登出即删、可设过期时间；
服务端可立即失效（删除文件）是相对 JWT 的优势，reset 通过清空 sessions 目录实现"退出登录"。
"""
import uuid
from datetime import datetime, timedelta

from app import config
from app.db import store

SESSION_COOKIE = "oj_session"
SESSION_TTL = timedelta(days=7)


def create_session(user: dict) -> str:
    sid = uuid.uuid4().hex
    now = datetime.now()
    store.save_json(config.SESSIONS_DIR, sid, {
        "session_id": sid,
        "user_id": user["user_id"],
        "username": user["username"],
        "created_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + SESSION_TTL).isoformat(timespec="seconds"),
    })
    return sid


def get_session(sid: str) -> dict | None:
    session = store.load_json(config.SESSIONS_DIR, sid)
    if session is None:
        return None
    try:
        if datetime.fromisoformat(session["expires_at"]) < datetime.now():
            delete_session(sid)  # 过期即清除
            return None
    except (KeyError, ValueError):
        delete_session(sid)
        return None
    return session


def delete_session(sid: str) -> None:
    store.delete_json(config.SESSIONS_DIR, sid)


def set_session_cookie(response, sid: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, sid,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True, samesite="lax", path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
