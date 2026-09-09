"""信息中心（polish 2026-09-09）：全 JSON 存储 notifications/{id}.json。

通知类型：
- ai_task：AI 命题任务完成（含对拍用尽需人工复核）——创建者可见；
- application：题目修改/删除申请审批结果——申请人可见。
reset 清空（NOTIFICATIONS_DIR 在 ALL_DATA_DIRS）。
"""
from datetime import datetime

from app import config
from app.db import store


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def next_notification_id() -> str:
    maximum = 0
    for key in store.list_keys(config.NOTIFICATIONS_DIR):
        try:
            maximum = max(maximum, int(key))
        except ValueError:
            continue
    return str(maximum + 1)


def create(user_id: str, username: str, kind: str, title: str, body: str,
           problem_id: str | None = None, task_id: str | None = None) -> dict:
    record = {
        "notification_id": next_notification_id(),
        "user_id": user_id,
        "username": username,
        "kind": kind,
        "title": title,
        "body": body,
        "problem_id": problem_id,
        "task_id": task_id,
        "read": False,
        "created_at": _now_iso(),
    }
    store.save_json(config.NOTIFICATIONS_DIR, record["notification_id"], record)
    return public(record)


def public(record: dict) -> dict:
    return {k: record.get(k) for k in (
        "notification_id", "user_id", "username", "kind", "title", "body",
        "problem_id", "task_id", "read", "created_at",
    )}


def get(notification_id: str) -> dict | None:
    return store.load_json(config.NOTIFICATIONS_DIR, notification_id)


def save(record: dict) -> None:
    store.save_json(config.NOTIFICATIONS_DIR, record["notification_id"], record)


def list_for_user(user_id: str) -> list[dict]:
    items = []
    for _, rec in store.iter_all(config.NOTIFICATIONS_DIR):
        if rec.get("user_id") == user_id:
            items.append(public(rec))
    items.sort(key=lambda r: int(r["notification_id"]) if r["notification_id"].isdigit() else 0,
               reverse=True)
    return items


def unread_count(user_id: str) -> int:
    return sum(1 for n in list_for_user(user_id) if not n["read"])


def mark_read(notification_id: str, user_id: str) -> dict | None:
    record = get(notification_id)
    if record is None or record.get("user_id") != user_id:
        return None
    record["read"] = True
    save(record)
    return public(record)


def mark_all_read(user_id: str) -> int:
    count = 0
    for _, rec in store.iter_all(config.NOTIFICATIONS_DIR):
        if rec.get("user_id") == user_id and not rec.get("read"):
            rec["read"] = True
            save(rec)
            count += 1
    return count
