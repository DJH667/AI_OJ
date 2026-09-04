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

# 题目
PROBLEM_NOT_FOUND = "problem not found"
PROBLEM_ALREADY_EXISTS = "problem already exists"
PROBLEM_ID_MISMATCH = "problem id in body does not match url"
INVALID_PROBLEM_FIELDS = "invalid problem fields"

# 语言
LANGUAGE_NOT_FOUND = "language not found"
LANGUAGE_ALREADY_EXISTS = "language already exists"

# 评测
RATE_LIMITED = "submission rate limit exceeded, at most 3 per minute per problem"
INVALID_LANGUAGE = "unsupported language"
JUDGE_FAILED = "judge task failed"
