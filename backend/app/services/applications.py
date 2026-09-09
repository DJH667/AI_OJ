"""题目修改/删除申请（polish 2026-09-08，用户反馈 2）。

普通用户对已有题目的修改（edit）与删除（delete）以"申请"形式提交，
由管理员审批：接纳（accept）→ 立即执行对应的题目操作；拒绝（reject）→ 仅标记。
- 全 JSON 存储：applications/{application_id}.json，id 为自增数字字符串；
- 同一用户对同一题目只允许一条 pending 申请（防刷）；
- reset 清空（config.APPLICATIONS_DIR 在 ALL_DATA_DIRS）。
"""
from datetime import datetime

from app import config
from app.core import messages
from app.core.exceptions import ApiError
from app.db import store

ACTIONS = ("edit", "delete")
STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def next_application_id() -> str:
    maximum = 0
    for key in store.list_keys(config.APPLICATIONS_DIR):
        try:
            maximum = max(maximum, int(key))
        except ValueError:
            continue
    return str(maximum + 1)


def get(application_id: str) -> dict | None:
    return store.load_json(config.APPLICATIONS_DIR, application_id)


def save(record: dict) -> None:
    store.save_json(config.APPLICATIONS_DIR, record["application_id"], record)


def public(record: dict) -> dict:
    """对外视图（payload 保留：编辑申请的修改内容；仅申请人/管理员可见整条记录）。"""
    return {
        "application_id": record.get("application_id"),
        "user_id": record.get("user_id"),
        "username": record.get("username"),
        "problem_id": record.get("problem_id"),
        "problem_title": record.get("problem_title", ""),
        "action": record.get("action"),
        "payload": record.get("payload"),
        "status": record.get("status"),
        "created_at": record.get("created_at"),
        "decided_by": record.get("decided_by"),
        "decision_note": record.get("decision_note", ""),
    }


def create(user: dict, problem_id: str, problem_title: str, action: str, payload: dict | None) -> dict:
    record = {
        "application_id": next_application_id(),
        "user_id": user["user_id"],
        "username": user["username"],
        "problem_id": problem_id,
        "problem_title": problem_title,
        "action": action,
        "payload": payload or None,
        "status": STATUS_PENDING,
        "created_at": _now_iso(),
        "decided_by": None,
        "decision_note": "",
    }
    save(record)
    return public(record)


def has_pending(user_id: str, problem_id: str) -> bool:
    for _, rec in store.iter_all(config.APPLICATIONS_DIR):
        if (rec.get("status") == STATUS_PENDING and rec.get("user_id") == user_id
                and rec.get("problem_id") == problem_id):
            return True
    return False


def list_records(status: str | None = None, user_id: str | None = None,
                 problem_id: str | None = None) -> list[dict]:
    items = []
    for _, rec in store.iter_all(config.APPLICATIONS_DIR):
        if status is not None and rec.get("status") != status:
            continue
        if user_id is not None and rec.get("user_id") != user_id:
            continue
        if problem_id is not None and rec.get("problem_id") != problem_id:
            continue
        items.append(public(rec))
    items.sort(key=lambda r: int(str(r["application_id"])) if str(r["application_id"]).isdigit() else 0,
               reverse=True)
    return items


def decide(application_id: str, decision: str, admin: dict) -> dict:
    """审批：accept → 执行对应题目操作；reject → 标记拒绝。

    执行失败（如题目已被删除、载荷非法）时自动标记为 rejected 并记录原因，
    保证申请队列不会卡死。审批结果写入信息中心通知申请人。
    """
    from app.services import notifications

    record = get(application_id)
    if record is None:
        raise ApiError(404, messages.APPLICATION_NOT_FOUND)
    if record.get("status") != STATUS_PENDING:
        raise ApiError(409, messages.APPLICATION_ALREADY_DECIDED)

    action_label = "修改" if record.get("action") == "edit" else "删除"
    problem_label = record.get("problem_title") or record.get("problem_id")

    if decision == "reject":
        record.update(status=STATUS_REJECTED, decided_by=admin.get("username"), decision_note="")
        save(record)
        notifications.create(record["user_id"], record["username"], "application",
                             "申请已拒绝", f"你对《{problem_label}》的{action_label}申请已被拒绝。")
        return public(record)

    from app.services import problems

    try:
        if record.get("action") == "edit":
            problems.update(record["problem_id"], problems.ProblemIn(**record.get("payload") or {}))
        else:  # delete
            problems.delete_cascade(record["problem_id"])
    except Exception as exc:
        # 执行失败 → 拒绝并记录安全原因（不泄露内部细节）
        note = str(getattr(exc, "msg", None) or "") or "apply failed"
        record.update(status=STATUS_REJECTED, decided_by=admin.get("username"), decision_note=note[:200])
        save(record)
        notifications.create(record["user_id"], record["username"], "application",
                             "申请已拒绝（执行失败）",
                             f"你对《{problem_label}》的{action_label}申请未能执行：{note[:120]}")
        return public(record)

    record.update(status=STATUS_ACCEPTED, decided_by=admin.get("username"))
    save(record)
    # 修改通过 → 带 problem_id 供前端跳转到对应题目；删除通过 → 题目已不存在，仅文本提醒
    notifications.create(record["user_id"], record["username"], "application",
                         "申请已通过", f"你对《{problem_label}》的{action_label}申请已通过。",
                         problem_id=record["problem_id"] if record.get("action") == "edit" else None)
    return public(record)
