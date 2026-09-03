"""统一成功响应 helper。

项目约定（api.md）：所有接口 JSON 必须含 code 且与 HTTP 状态码一致。
成功场景 HTTP 200，返回 {"code": 200, "msg": ..., "data": ...}。
错误场景由路由 raise ApiError（见 exceptions.py），统一由异常处理器输出。
"""
from typing import Any


def success(msg: str = "success", data: Any = None) -> dict:
    """返回成功响应体。默认 data 为 None（序列化为 null，与 api.md 错误示例一致）。"""
    return {"code": 200, "msg": msg, "data": data}
