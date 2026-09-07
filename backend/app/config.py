"""全局配置：数据目录、初始管理员等。

约定（见 reports/PROJECT_REQUIREMENTS.md §4）：
- 全 JSON 文件存储，运行期数据统一放在 backend/data/ 下（不进 git）；
- 初始管理员 admin/admintestpassword 由启动钩子创建；
- admin 的 user_id 固定为 "0"，普通用户自 "1" 起分配，
  以对齐 api.md 注册示例中首个注册用户 user_id 为 "1" 的语义。
"""
from pathlib import Path

import os

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DATA_DIR = BASE_DIR / "data"

PROBLEMS_DIR = DATA_DIR / "problems"        # 题目：每题一个 JSON
USERS_DIR = DATA_DIR / "users"              # 用户：每个用户名一个 JSON
SUBMISSIONS_DIR = DATA_DIR / "submissions"  # 提交：每条一个 JSON
LANGUAGES_DIR = DATA_DIR / "languages"      # 语言注册表：每种语言一个 JSON
LOGS_DIR = DATA_DIR / "logs"                # 评测日志目录
ACCESS_LOGS_DIR = LOGS_DIR / "access"       # 日志访问审计
ROLE_CHANGES_DIR = LOGS_DIR / "role_changes"  # 权限变更操作日志（Step4）
SESSIONS_DIR = DATA_DIR / "sessions"        # 服务端 session（D2 使用）
AI_TASKS_DIR = DATA_DIR / "ai_tasks"        # AI 命题任务（测试数据，reset 清空）
AI_CONFIGS_DIR = DATA_DIR / "ai_configs"    # AI 模型配置（per-user，系统配置，reset 不清）

# 版本库内的示例题（开发联调用，不自动导入；运行时题目库在 PROBLEMS_DIR）
SAMPLE_PROBLEMS_DIR = BASE_DIR / "sample_problems"

# 需要在启动/测试前确保存在的子目录
ALL_DATA_DIRS = [
    PROBLEMS_DIR,
    USERS_DIR,
    SUBMISSIONS_DIR,
    LANGUAGES_DIR,
    LOGS_DIR,
    ACCESS_LOGS_DIR,
    ROLE_CHANGES_DIR,
    SESSIONS_DIR,
    AI_TASKS_DIR,
]

# 初始管理员（api.md：系统启动自动创建；密码 17 位全小写，满足注册校验）
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admintestpassword"
ADMIN_USER_ID = "0"

# reset 鉴权开关：api.md 权限为"仅管理员（测试环境可不校验）"、异常含 401/403
# ⇒ 默认按仅管理员鉴权；若评测确需免登录调用，置 False 放宽（"测试环境可不校验"）。
RESET_REQUIRE_ADMIN = True

# 演示种子题（polish 2026-09-07，用户反馈 3）：启动时按 id 幂等导入内置示例题，
# 保证题库初始有 Hello World 与 A+B。测试环境用 OJ_SEED_DEMO=0 关闭（conftest.py），
# 且 TA 自动评测会先 reset，不受影响。
SEED_DEMO_PROBLEMS = os.environ.get("OJ_SEED_DEMO", "1") == "1"
DEMO_PROBLEM_SAMPLES = ["helloworld", "aplusb"]
