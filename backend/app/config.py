"""全局配置：数据目录、初始管理员等。

约定（见 reports/PROJECT_REQUIREMENTS.md §4）：
- 全 JSON 文件存储，运行期数据统一放在 backend/data/ 下（不进 git）；
- 初始管理员 admin/admintestpassword 由启动钩子创建；
- admin 的 user_id 固定为 "0"，普通用户自 "1" 起分配，
  以对齐 api.md 注册示例中首个注册用户 user_id 为 "1" 的语义。
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = BASE_DIR / "data"

PROBLEMS_DIR = DATA_DIR / "problems"        # 题目：每题一个 JSON
USERS_DIR = DATA_DIR / "users"              # 用户：每个用户名一个 JSON
SUBMISSIONS_DIR = DATA_DIR / "submissions"  # 提交：每条一个 JSON
LOGS_DIR = DATA_DIR / "logs"                # 评测日志目录
ACCESS_LOGS_DIR = LOGS_DIR / "access"       # 日志访问审计
SESSIONS_DIR = DATA_DIR / "sessions"        # 服务端 session（D2 使用）

# 需要在启动/测试前确保存在的子目录
ALL_DATA_DIRS = [
    PROBLEMS_DIR,
    USERS_DIR,
    SUBMISSIONS_DIR,
    LOGS_DIR,
    ACCESS_LOGS_DIR,
    SESSIONS_DIR,
]

# 初始管理员（api.md：系统启动自动创建；密码 17 位全小写，满足注册校验）
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admintestpassword"
ADMIN_USER_ID = "0"
