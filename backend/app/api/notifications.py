"""信息中心接口（polish 2026-09-09）：
- GET  /api/notifications/              当前用户的通知列表（时间倒序）
- GET  /api/notifications/unread-count  未读数
- PUT  /api/notifications/{id}/read     单条已读（仅本人）
- PUT  /api/notifications/read-all      全部已读（仅本人）
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.response import success
from app.services import notifications as notification_service

router = APIRouter()


@router.get("/api/notifications/")
async def list_notifications(current: dict = Depends(get_current_user)):
    items = notification_service.list_for_user(current["user_id"])
    return success(msg="success", data={
        "total": len(items),
        "unread": notification_service.unread_count(current["user_id"]),
        "notifications": items,
    })


@router.get("/api/notifications/unread-count")
async def get_unread_count(current: dict = Depends(get_current_user)):
    return success(msg="success", data={
        "unread": notification_service.unread_count(current["user_id"]),
    })


@router.put("/api/notifications/{notification_id}/read")
async def read_notification(notification_id: str, current: dict = Depends(get_current_user)):
    data = notification_service.mark_read(notification_id, current["user_id"])
    if data is None:
        from app.core.exceptions import ApiError
        from app.core.messages import NOTIFICATION_NOT_FOUND

        raise ApiError(404, NOTIFICATION_NOT_FOUND)
    return success(msg="read", data=data)


@router.put("/api/notifications/read-all")
async def read_all_notifications(current: dict = Depends(get_current_user)):
    count = notification_service.mark_all_read(current["user_id"])
    return success(msg="read all", data={"count": count})
