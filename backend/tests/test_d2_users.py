"""D2 用户系统（官方 Step4）测试。

覆盖：注册校验（长度/重名/422→400 实测）、登录/登出、banned 再登录 403、
banned 已登录会话立即失效、详情权限（本人/管理员/越权 403/404）、
role 变更（非法 400/非管理员 403/操作日志）、用户列表分页语义、创建管理员、reset 清会话。
"""
import pytest
from fastapi.testclient import TestClient

from main import app
from app import config
from app.db import store

PASSWORD = "secret123"


@pytest.fixture()
def client():
    """每个测试独立：全新 TestClient + reset 恢复初始环境（仅剩 admin）。"""
    with TestClient(app) as c:
        r = c.post("/api/reset/")
        assert r.status_code == 200
        yield c


def _register(c, username, password=PASSWORD):
    return c.post("/api/users/", json={"username": username, "password": password})


def _login(c, username, password=PASSWORD):
    return c.post("/api/auth/login", json={"username": username, "password": password})


def _admin_client():
    """返回已登录 admin 的独立 client（不 reset——避免清掉主 client 已注册的用户）。"""
    from app.db.seed import ensure_admin

    ensure_admin()
    c = TestClient(app)
    r = _login(c, config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
    assert r.status_code == 200
    return c


# ---------- 注册 ----------

def test_register_ok(client):
    r = _register(client, "alice")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 200
    assert body["msg"] == "register success"
    data = body["data"]
    assert data["user_id"] == "1"          # admin 占 0，首个普通用户从 1 起
    assert data["username"] == "alice"
    assert data["role"] == "user"
    assert data["submit_count"] == 0 and data["resolve_count"] == 0
    assert data["join_time"]
    # 落盘且不含明文密码
    stored = store.load_json(config.USERS_DIR, "alice")
    assert stored is not None and stored["password"] != PASSWORD


def test_register_duplicate_400(client):
    assert _register(client, "alice").status_code == 200
    r = _register(client, "alice")
    assert r.status_code == 400
    assert r.json()["code"] == 400 and r.json()["msg"] == "username already exists"


def test_register_username_length_400(client):
    # pydantic 校验触发 RequestValidationError → 统一转 400（评审 P2 补测 422→400）
    r = _register(client, "ab")
    assert r.status_code == 400
    assert r.json()["code"] == 400
    r = _register(client, "u" * 41)
    assert r.status_code == 400


def test_register_password_too_short_400(client):
    r = _register(client, "alice", password="12345")
    assert r.status_code == 400
    assert r.json()["code"] == 400


# ---------- 登录 / 登出 / 会话 ----------

def test_login_ok_and_get_self(client):
    _register(client, "alice")
    r = _login(client, "alice")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data == {"user_id": "1", "username": "alice", "role": "user"}
    # 会话 cookie 已下发
    assert any(k.startswith("oj_session") for k in client.cookies.keys())
    # 本人可查详情，响应不含 password
    r = client.get("/api/users/1")
    assert r.status_code == 200
    assert r.json()["data"]["username"] == "alice"
    assert "password" not in r.json()["data"]


def test_login_wrong_credentials_401(client):
    _register(client, "alice")
    assert _login(client, "alice", password="wrong-pass").status_code == 401
    assert _login(client, "ghost-user").status_code == 401


def test_logout_invalidates_session(client):
    _register(client, "alice")
    assert _login(client, "alice").status_code == 200
    r = client.post("/api/auth/logout")
    assert r.status_code == 200
    assert r.json() == {"code": 200, "msg": "logout success", "data": None}
    # 登出后旧会话失效
    assert client.get("/api/users/1").status_code == 401


def test_protected_route_requires_login(client):
    assert client.get("/api/users/1").status_code == 401


# ---------- banned 语义 ----------

def test_banned_login_rejected_403_and_session_invalidated_immediately():
    with TestClient(app) as c_user, TestClient(app) as c_admin:
        assert c_user.post("/api/reset/").status_code == 200
        assert _register(c_user, "alice").status_code == 200
        assert _login(c_user, "alice").status_code == 200
        assert _login(c_admin, config.ADMIN_USERNAME, config.ADMIN_PASSWORD).status_code == 200
        assert c_user.get("/api/users/1").status_code == 200

        # admin 将 alice 设为 banned
        r = c_admin.put("/api/users/1/role", json={"role": "banned"})
        assert r.status_code == 200
        # 已登录会话下一次请求即 403（实时查库，决策 dec-0f895a1ddd678090）
        r = c_user.get("/api/users/1")
        assert r.status_code == 403
        assert r.json()["code"] == 403 and r.json()["msg"] == "user is banned"
        # banned 再登录同样被拒 403
        assert _login(c_user, "alice").status_code == 403


# ---------- 详情权限 ----------

def test_get_user_permission_rules(client):
    _register(client, "alice")
    _register(client, "bob")
    _login(client, "alice")
    # 普通用户查他人 → 403（不泄露存在性）
    r = client.get("/api/users/2")
    assert r.status_code == 403
    # admin 可查他人；查不存在 → 404
    admin = _admin_client()
    assert admin.get("/api/users/2").status_code == 200
    r = admin.get("/api/users/999")
    assert r.status_code == 404
    assert r.json()["msg"] == "user not found"


# ---------- role 变更 ----------

def test_role_change_log_and_validation(client):
    _register(client, "alice")
    _register(client, "bob")
    admin = _admin_client()
    r = admin.put("/api/users/1/role", json={"role": "banned"})
    assert r.status_code == 200
    assert r.json()["data"] == {"user_id": "1", "role": "banned"}
    # 操作日志已落盘
    keys = store.list_keys(config.ROLE_CHANGES_DIR)
    assert keys, "role change log should exist"
    log = store.load_json(config.ROLE_CHANGES_DIR, keys[-1])
    assert log["target_user_id"] == "1"
    assert log["new_role"] == "banned"
    assert log["operator_username"] == config.ADMIN_USERNAME
    # 非法 role → 400
    r = admin.put("/api/users/2/role", json={"role": "superuser"})
    assert r.status_code == 400
    assert r.json()["msg"] == "invalid role"
    # 普通用户（bob）无权变更 → 403
    _login(client, "bob")
    r = client.put("/api/users/1/role", json={"role": "user"})
    assert r.status_code == 403


def test_role_change_nonexistent_user_404(client):
    admin = _admin_client()
    r = admin.put("/api/users/999/role", json={"role": "admin"})
    assert r.status_code == 404


# ---------- 用户列表分页 ----------

def test_users_list_pagination_and_permission(client):
    _register(client, "alice")
    _register(client, "bob")
    # 普通用户无权访问列表
    _login(client, "alice")
    assert client.get("/api/users/").status_code == 403
    admin = _admin_client()
    # 全量（admin + alice + bob）
    r = admin.get("/api/users/")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 3 and len(data["users"]) == 3
    # page + page_size 组合
    r = admin.get("/api/users/", params={"page": 1, "page_size": 2})
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 3 and len(r.json()["data"]["users"]) == 2
    # page 有、page_size 无 → 400
    r = admin.get("/api/users/", params={"page": 2})
    assert r.status_code == 400
    assert r.json()["msg"] == "page_size is required when page is provided"
    # page_size 有、page 无 → 取第 1 页
    r = admin.get("/api/users/", params={"page_size": 2})
    assert r.status_code == 200
    assert len(r.json()["data"]["users"]) == 2
    # 非法分页参数
    assert admin.get("/api/users/", params={"page": 0, "page_size": 2}).status_code == 400
    assert admin.get("/api/users/", params={"page": 1, "page_size": 0}).status_code == 400


# ---------- 创建管理员 / reset ----------

def test_create_admin(client):
    admin = _admin_client()
    r = admin.post("/api/users/admin", json={"username": "boss", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["data"]["username"] == "boss"
    # 新管理员可登录并执行管理操作
    boss = TestClient(app)
    assert _login(boss, "boss", PASSWORD).status_code == 200
    _register(client, "alice")
    assert boss.put("/api/users/1/role", json={"role": "banned"}).status_code == 200
    # 重名 → 400
    assert admin.post("/api/users/admin", json={"username": "boss", "password": PASSWORD}).status_code == 400
    # 非管理员（bob）→ 403
    _register(client, "bob")
    _login(client, "bob")
    r = client.post("/api/users/admin", json={"username": "x1", "password": PASSWORD})
    assert r.status_code == 403


def test_reset_clears_sessions(client):
    _register(client, "alice")
    _login(client, "alice")
    assert client.get("/api/users/1").status_code == 200
    # reset 清空用户/会话（接口本身不鉴权）
    assert client.post("/api/reset/").status_code == 200
    # 旧会话立即失效
    assert client.get("/api/users/1").status_code == 401
