"""全站统一 msg 契约。

评审意见 P1/P3（2026-09-03）：避免散点英文/中文混用导致前端提示不一致。
api.md 示例 msg 为英文风格（如 "problem not found"），本表统一英文简洁文案；
各业务模块 raise ApiError 时一律引用本表。
"""

# 通用
INVALID_PARAMETERS = "invalid request parameters"
NOT_LOGGED_IN = "not logged in"
PERMISSION_DENIED = "permission denied"

# 用户 / 认证
INVALID_USERNAME = "invalid username"
INVALID_PASSWORD = "invalid password"
USERNAME_ALREADY_EXISTS = "username already exists"
INVALID_CREDENTIALS = "username or password error"
USER_BANNED = "user is banned"
USER_NOT_FOUND = "user not found"
INVALID_ROLE = "invalid role"

# 分页
PAGE_SIZE_REQUIRED = "page_size is required when page is provided"
INVALID_PAGINATION = "invalid pagination parameters"
