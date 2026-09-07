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


def ensure_demo_problems() -> None:
    """polish（2026-09-07）：启动时按 id 幂等导入内置示例题（Hello World + A+B）。

    - 仅当 config.SEED_DEMO_PROBLEMS 为真时执行（测试经 OJ_SEED_DEMO=0 关闭）；
    - 按题目 id 检查，缺失才写入——用户删除后重启后端可恢复初始题库；
    - reset 会清空题库且不回种（重启后端即恢复）。
    """
    if not config.SEED_DEMO_PROBLEMS:
        return
    from app.services import problems as problem_service

    for name in config.DEMO_PROBLEM_SAMPLES:
        data = problem_service.load_sample(name)
        if problem_service.get(data.get("id")) is None:
            problem_service.save_internal(data)
            # 方案 D：种入即按难度标签初始化先验难度分
            problem_service.refresh_difficulty(data.get("id"))
