"""密码哈希（bcrypt）。

项目约定（api.md / 需求文档 §4.3）：密码必须 bcrypt 哈希存储，禁止明文落盘。
bcrypt 5.x 仍提供 hashpw/checkpw；对非法输入容错返回 False。
"""
import bcrypt


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False
