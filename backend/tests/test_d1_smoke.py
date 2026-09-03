"""D1 公共骨架冒烟测试：
- 初始管理员种子（存在性 / role / bcrypt 可验）
- POST /api/reset/（清空 + 重建 + 响应结构）
- 未知路径 404 统一响应格式
- 未预期异常 500 兜底统一格式（评审意见 P1，2026-09-03）
- 特殊字符 key 存储往返
"""
import asyncio

import httpx

from main import app
from app import config
from app.core.security import verify_password
from app.db import store
from app.db.seed import ensure_admin


async def _request(method: str, path: str, **kwargs) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.request(method, path, **kwargs)


def _run(coro) -> httpx.Response:
    return asyncio.run(coro)


def test_admin_seeded():
    store.clear_all()
    ensure_admin()
    data = store.load_json(config.USERS_DIR, config.ADMIN_USERNAME)
    assert data is not None
    assert data["username"] == config.ADMIN_USERNAME
    assert data["user_id"] == "0"
    assert data["role"] == "admin"
    # 密码必须为 bcrypt 哈希且可校验
    assert verify_password(config.ADMIN_PASSWORD, data["password"])
    assert data["password"] != config.ADMIN_PASSWORD


def test_reset_cleanup_and_reseed():
    store.clear_all()
    ensure_admin()
    # 制造脏数据
    store.save_json(config.USERS_DIR, "alice", {"username": "alice", "role": "user"})
    store.save_json(config.PROBLEMS_DIR, "p1", {"id": "p1", "title": "x"})

    r = _run(_request("POST", "/api/reset/"))
    assert r.status_code == 200
    assert r.json() == {"code": 200, "msg": "system reset successfully", "data": None}
    # 题目清空；用户只剩初始管理员
    assert store.list_keys(config.PROBLEMS_DIR) == []
    assert store.list_keys(config.USERS_DIR) == [config.ADMIN_USERNAME]


def test_unknown_path_404_unified():
    r = _run(_request("GET", "/api/no-such/"))
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == 404
    assert body["msg"]
    assert body["data"] is None


def test_unhandled_exception_500_unified():
    # 临时注册一个必抛异常的测试路由，验证兜底 handler 收敛为 JSON 500 且不泄露内部信息。
    # 注：Starlette 在纯 ASGI 传输(ASGITransport)下会把已处理的 500 异常 re-raise 给调用方，
    # 故此处用 TestClient(raise_server_exceptions=False) 取得真实响应体断言。
    from fastapi.testclient import TestClient

    def _boom():
        raise RuntimeError("secret-internal-detail")

    app.add_api_route("/api/_boom", _boom, methods=["GET"])
    try:
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/_boom")
        assert r.status_code == 500
        assert r.json() == {"code": 500, "msg": "internal server error", "data": None}
        assert "secret-internal-detail" not in r.text
        assert "Traceback" not in r.text
    finally:
        app.routes[:] = [rt for rt in app.routes if getattr(rt, "path", None) != "/api/_boom"]


def test_store_key_roundtrip_with_special_chars():
    # 题目 id 可含 / : 等字符，文件名字典必须可逆
    weird = "P:1001/a?b"
    store.save_json(config.PROBLEMS_DIR, weird, {"id": weird})
    assert store.load_json(config.PROBLEMS_DIR, weird) == {"id": weird}
    assert weird in store.list_keys(config.PROBLEMS_DIR)
    store.delete_json(config.PROBLEMS_DIR, weird)
    assert store.load_json(config.PROBLEMS_DIR, weird) is None
