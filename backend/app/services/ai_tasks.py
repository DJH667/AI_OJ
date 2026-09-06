"""AI 命题任务数据层：状态机 + 持久化（data/ai_tasks/）。

状态：waiting → running → completed | interrupted | failed；
硬核对拍用尽重试后：status=completed 且 review=True（需人工复核，题目不入库）。
"""
from datetime import datetime

from app import config
from app.db import store

STATUS_WAITING = "waiting"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_INTERRUPTED = "interrupted"
STATUS_FAILED = "failed"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def next_task_id() -> str:
    maximum = 0
    for key in store.list_keys(config.AI_TASKS_DIR):
        if key.startswith("ai-task-"):
            try:
                maximum = max(maximum, int(key.split("-")[-1]))
            except ValueError:
                continue
    return f"ai-task-{maximum + 1}"


def create(user: dict, requirement: str, language: str | None, problem_id: str | None,
           hardcore: bool, retry_limit: int) -> dict:
    task_id = next_task_id()
    task = {
        "task_id": task_id,
        "user_id": user["user_id"],
        "username": user["username"],
        "status": STATUS_WAITING,
        "progress": "等待中",
        "requirement": requirement,
        "language": language,
        "problem_id": problem_id,
        "hardcore": hardcore,
        "retry_limit": retry_limit,
        "attempts": 0,
        "result": None,
        "review": False,       # 需人工复核标记（对拍用尽/普通产出需人审）
        "review_note": "",
        "usage": None,
        "error": "",
        "cancel_requested": False,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    save(task)
    return task


def save(task: dict) -> None:
    task["updated_at"] = _now_iso()
    store.save_json(config.AI_TASKS_DIR, task["task_id"], task)


def get(task_id: str) -> dict | None:
    return store.load_json(config.AI_TASKS_DIR, task_id)


def set_status(task: dict, status: str, progress: str | None = None) -> None:
    task["status"] = status
    if progress is not None:
        task["progress"] = progress
    save(task)
