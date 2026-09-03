"""用户服务：注册、查询、权限变更、分页列表、操作日志。

存储约定（reports/PROJECT_REQUIREMENTS.md §4）：users 以 username 为文件名 key，
内容含 user_id/username/password(bcrypt)/role/join_time/submit_count/resolve_count。
admin 的 user_id 固定 "0"，普通用户从 "1" 起按最大 user_id+1 自增。
"""
from datetime import datetime

from app import config
from app.core import messages
from app.core.exceptions import ApiError
from app.core.security import hash_password, verify_password
from app.db import store

USERNAME_MIN = 3
USERNAME_MAX = 40
PASSWORD_MIN = 6
VALID_ROLES = ("admin", "user", "banned")

# 对外可见字段（永不含 password）
PUBLIC_FIELDS = ("user_id", "username", "join_time", "role", "submit_count", "resolve_count")


def _public(user: dict) -> dict:
    return {k: user[k] for k in PUBLIC_FIELDS if k in user}


def to_public(user: dict) -> dict:
    """对外安全视图（不含 password）。"""
    return _public(user)


def _now_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_by_username(username: str) -> dict | None:
    return store.load_json(config.USERS_DIR, username)


def get_by_user_id(user_id: str) -> dict | None:
    for _, user in store.iter_all(config.USERS_DIR):
        if user.get("user_id") == user_id:
            return user
    return None


def next_user_id() -> str:
    maximum = 0
    for _, user in store.iter_all(config.USERS_DIR):
        try:
            maximum = max(maximum, int(user["user_id"]))
        except (KeyError, TypeError, ValueError):
            continue
    return str(maximum + 1)


def register(username: str, password: str) -> dict:
    username = username.strip()
    if not (USERNAME_MIN <= len(username) <= USERNAME_MAX):
        raise ApiError(400, messages.INVALID_USERNAME)
    if len(password) < PASSWORD_MIN:
        raise ApiError(400, messages.INVALID_PASSWORD)
    if get_by_username(username) is not None:
        raise ApiError(400, messages.USERNAME_ALREADY_EXISTS)
    user = {
        "user_id": next_user_id(),
        "username": username,
        "password": hash_password(password),
        "role": "user",
        "join_time": _now_date(),
        "submit_count": 0,
        "resolve_count": 0,
    }
    store.save_json(config.USERS_DIR, username, user)
    return _public(user)


def authenticate(username: str, password: str) -> dict:
    """登录校验：成功返回用户；失败抛 401/403（按 api.md：401 凭据错、403 被禁用）。"""
    username = username.strip()
    user = get_by_username(username)
    if user is None or not verify_password(password, user["password"]):
        raise ApiError(401, messages.INVALID_CREDENTIALS)
    if user["role"] == "banned":
        raise ApiError(403, messages.USER_BANNED)
    return user


def list_users(page: int | None, page_size: int | None) -> tuple[int, list[dict]]:
    """用户列表（分页语义与 submissions 一致），返回 (total, 当前页用户)。"""
    page, page_size = _normalize_pagination(page, page_size)
    all_users = [u for _, u in store.iter_all(config.USERS_DIR)]
    all_users.sort(key=lambda u: int(u["user_id"]) if u["user_id"].isdigit() else 0)
    total = len(all_users)
    if page_size is None:
        return total, [_public(u) for u in all_users]
    start = (page - 1) * page_size
    return total, [_public(u) for u in all_users[start:start + page_size]]


def change_role(operator: dict, target_user_id: str, new_role: str) -> dict:
    if new_role not in VALID_ROLES:
        raise ApiError(400, messages.INVALID_ROLE)
    target = get_by_user_id(target_user_id)
    if target is None:
        raise ApiError(404, messages.USER_NOT_FOUND)
    old_role = target["role"]
    target["role"] = new_role
    store.save_json(config.USERS_DIR, target["username"], target)
    _log_role_change(operator, target, old_role, new_role)
    return {"user_id": target["user_id"], "role": target["role"]}


def _log_role_change(operator: dict, target: dict, old_role: str, new_role: str) -> None:
    """记录权限操作日志（Step4 要求），与 Step5 的 access 审计（action=view_logs）是两回事。"""
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    store.save_json(config.ROLE_CHANGES_DIR, f"{stamp}-{target['user_id']}", {
        "operator_user_id": operator["user_id"],
        "operator_username": operator["username"],
        "target_user_id": target["user_id"],
        "target_username": target["username"],
        "old_role": old_role,
        "new_role": new_role,
        "time": datetime.now().isoformat(timespec="seconds"),
    })


def _normalize_pagination(page: int | None, page_size: int | None) -> tuple[int | None, int | None]:
    """分页语义（api.md，与 GET /api/submissions/ 一致）：
    - page 有值但 page_size 为空 → 参数错误（400）；
    - page 空但 page_size 有值 → 取第 1 页；
    - 两者皆空 → 全部数据（返回 page=None, page_size=None）。
    """
    if page is not None and page_size is None:
        raise ApiError(400, messages.PAGE_SIZE_REQUIRED)
    if page is not None and page < 1:
        raise ApiError(400, messages.INVALID_PAGINATION)
    if page_size is not None and page_size < 1:
        raise ApiError(400, messages.INVALID_PAGINATION)
    if page is None and page_size is not None:
        page = 1
    return page, page_size
