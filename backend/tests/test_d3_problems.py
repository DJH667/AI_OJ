"""D3 Step1 题目管理测试：
CRUD 五接口、权限（登录/仅管理员删除）、409/400/404、
详情默认字段补齐、difficulty_score 隐藏字段不回传、级联删除+统计回退（助教确认口径）。
"""
import pytest
from fastapi.testclient import TestClient

from main import app
from app import config
from app.db import store
from app.services import submissions as sub_service

PASSWORD = "secret123"


def _pb(pid: str = "P1", **over):
    body = {
        "id": pid,
        "title": "求和",
        "description": "计算两个数的和",
        "input_description": "两个整数",
        "output_description": "一个整数",
        "samples": [{"input": "1 2", "output": "3"}],
        "constraints": "范围 1e9",
        "testcases": [{"input": "1 2", "output": "3"}],
    }
    body.update(over)
    return body


@pytest.fixture()
def client():
    """已登录 admin 的干净环境（注册普通用户用）。"""
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD}).status_code == 200
        assert c.post("/api/reset/").status_code == 200
        assert c.post("/api/auth/login", json={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD}).status_code == 200
        yield c


def test_add_list_get_defaults(client):
    # 未提供可选字段 → 详情按类型默认值补齐
    r = client.post("/api/problems/", json=_pb("P1"))
    assert r.status_code == 200
    assert r.json() == {"code": 200, "msg": "add success", "data": {"id": "P1"}}
    # 列表
    r = client.get("/api/problems/")
    assert r.status_code == 200
    assert r.json()["data"] == [{"id": "P1", "title": "求和"}]
    # 详情：可选字段默认
    r = client.get("/api/problems/P1")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["id"] == "P1"
    assert data["hint"] == "" and data["source"] == "" and data["author"] == "" and data["difficulty"] == ""
    assert data["tags"] == []
    assert data["time_limit"] == 3.0 and data["memory_limit"] == 128
    assert data["testcases"] == [{"input": "1 2", "output": "3"}]


def test_duplicate_id_409(client):
    assert client.post("/api/problems/", json=_pb("P1")).status_code == 200
    r = client.post("/api/problems/", json=_pb("P1", title="另一个"))
    assert r.status_code == 409
    assert r.json()["code"] == 409 and r.json()["msg"] == "problem already exists"


def test_get_missing_404_and_requires_login(client):
    r = client.get("/api/problems/NOPE")
    assert r.status_code == 404
    assert r.json()["msg"] == "problem not found"
    # 未登录不可访问
    anon = TestClient(app)
    assert anon.get("/api/problems/").status_code == 401
    assert anon.post("/api/problems/", json=_pb()).status_code == 401


def test_invalid_body_400(client):
    r = client.post("/api/problems/", json={"id": "P1"})  # 缺必填字段 → 422 转 400
    assert r.status_code == 400
    assert r.json()["code"] == 400


def test_update_rules(client):
    assert client.post("/api/problems/", json=_pb("P1")).status_code == 200
    # body id 与路径不一致 → 400
    r = client.put("/api/problems/P1", json=_pb("P2", title="改名"))
    assert r.status_code == 400
    assert r.json()["msg"] == "problem id in body does not match url"
    # 正常更新覆盖
    r = client.put("/api/problems/P1", json=_pb("P1", title="新标题", hint="h"))
    assert r.status_code == 200
    assert client.get("/api/problems/P1").json()["data"]["title"] == "新标题"
    # 更新不存在的题 → 404
    assert client.put("/api/problems/XX", json=_pb("XX")).status_code == 404


def test_delete_requires_admin_and_removes(client):
    assert client.post("/api/problems/", json=_pb("P1")).status_code == 200
    # 普通用户注册登录后 DELETE → 403
    assert client.post("/api/users/", json={"username": "alice", "password": PASSWORD}).status_code == 200
    user = TestClient(app)
    assert user.post("/api/auth/login", json={"username": "alice", "password": PASSWORD}).status_code == 200
    assert user.delete("/api/problems/P1").status_code == 403
    # admin 删除成功
    r = client.delete("/api/problems/P1")
    assert r.status_code == 200
    assert r.json()["msg"] == "delete success"
    assert client.get("/api/problems/P1").status_code == 404
    # 删除不存在的题 → 404
    assert client.delete("/api/problems/P1").status_code == 404


def test_private_difficulty_score_not_in_api(client):
    # 对外契约不接收也不回传 difficulty_score（服务端私有隐藏字段）
    r = client.post("/api/problems/", json=_pb("P1", difficulty_score=5.0, time_limit=1.0))
    assert r.status_code == 200  # 额外字段被忽略，不报错
    data = client.get("/api/problems/P1").json()["data"]
    assert "difficulty_score" not in data
    # 列表也不含
    assert "difficulty_score" not in str(client.get("/api/problems/").json()["data"])


def test_cascade_delete_rolls_back_user_stats(client):
    # 注册用户并造提交数据（alice: P1×2 其中 1 AC + P2×1 AC；bob: P1×1 pending）
    assert client.post("/api/users/", json={"username": "alice", "password": PASSWORD}).status_code == 200
    assert client.post("/api/users/", json={"username": "bob", "password": PASSWORD}).status_code == 200
    assert client.post("/api/problems/", json=_pb("P1")).status_code == 200
    assert client.post("/api/problems/", json=_pb("P2")).status_code == 200
    alice = store.load_json(config.USERS_DIR, "alice")
    bob = store.load_json(config.USERS_DIR, "bob")
    alice["submit_count"], alice["resolve_count"] = 3, 2
    bob["submit_count"], bob["resolve_count"] = 1, 0

    def _mk(username, problem, status, score, counts):
        user = store.load_json(config.USERS_DIR, username)
        rec = sub_service.new_pending(user, problem, "python", "code")
        rec.update(status=status, score=score, counts=counts)
        store.save_json(config.SUBMISSIONS_DIR, rec["submission_id"], rec)

    _mk("alice", "P1", "success", 10, 10)   # AC
    _mk("alice", "P1", "success", 0, 10)    # WA
    _mk("alice", "P2", "success", 10, 10)   # AC（不受删除影响）
    _mk("bob", "P1", "pending", 0, 0)
    store.save_json(config.USERS_DIR, "alice", alice)
    store.save_json(config.USERS_DIR, "bob", bob)

    # admin 删除 P1 → 级联 + 回退统计
    assert client.delete("/api/problems/P1").status_code == 200
    alice = store.load_json(config.USERS_DIR, "alice")
    bob = store.load_json(config.USERS_DIR, "bob")
    assert alice["submit_count"] == 1 and alice["resolve_count"] == 1  # 仅剩 P2 贡献
    assert bob["submit_count"] == 0 and bob["resolve_count"] == 0
    # P1 提交已清空，P2 提交保留
    remaining = [rec for _, rec in store.iter_all(config.SUBMISSIONS_DIR)]
    assert all(rec["problem_id"] != "P1" for rec in remaining)
    assert any(rec["problem_id"] == "P2" for rec in remaining)
