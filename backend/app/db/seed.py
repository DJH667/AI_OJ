"""启动种子：确保初始管理员存在。

api.md：系统启动自动创建初始管理员 admin/admintestpassword。
reset 清空用户后同样需要重建，故 ensure_admin 幂等、被 reset 复用。
"""
from datetime import datetime

from app import config
from app.core.security import hash_password
from app.db import store


def ensure_admin() -> None:
    store.ensure_dirs()
    if store.load_json(config.USERS_DIR, config.ADMIN_USERNAME) is not None:
        return
    store.save_json(config.USERS_DIR, config.ADMIN_USERNAME, {
        "user_id": config.ADMIN_USER_ID,
        "username": config.ADMIN_USERNAME,
        "password": hash_password(config.ADMIN_PASSWORD),
        "role": "admin",
        "join_time": datetime.now().strftime("%Y-%m-%d"),
        "submit_count": 0,
        "resolve_count": 0,
    })
