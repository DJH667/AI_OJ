"""polish 2026-09-08：题目修改/删除申请（普通用户申请 → 管理员审批执行）。"""
import pytest
from fastapi.testclient import TestClient

from main import app
from app import config

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
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={
            "username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD,
        }).status_code == 200
        assert c.post("/api/reset/").status_code == 200
        assert c.post("/api/auth/login", json={
            "username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD,
        }).status_code == 200
        yield c


@pytest.fixture()
def bob():
    c = TestClient(app)
    assert c.post("/api/users/", json={"username": "bob", "password": PASSWORD}).status_code == 200
    assert c.post("/api/auth/login", json={"username": "bob", "password": PASSWORD}).status_code == 200
    return c


def test_apply_edit_flow(client, bob):
    assert client.post("/api/problems/", json=_pb("P1")).status_code == 200
    # 普通用户提交修改申请
    r = bob.post("/api/problems/P1/apply", json={
        "action": "edit", "payload": _pb("P1", title="新标题"),
    })
    assert r.status_code == 200
    aid = r.json()["data"]["application_id"]
    assert r.json()["data"]["status"] == "pending"
    # 同人同题重复 pending → 409
    assert bob.post("/api/problems/P1/apply", json={"action": "delete"}).status_code == 409
    # 未登录 401
    assert TestClient(app).get("/api/applications/").status_code == 401
    # 普通用户只能看自己的申请；审批 403
    assert bob.get("/api/applications/").json()["data"]["total"] == 1
    assert bob.put(f"/api/applications/{aid}", json={"decision": "accept"}).status_code == 403
    # 管理员看全部并接纳 → 立即执行修改
    data = client.get("/api/applications/").json()["data"]
    assert data["total"] == 1 and data["applications"][0]["application_id"] == aid
    r = client.put(f"/api/applications/{aid}", json={"decision": "accept"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "accepted"
    assert client.get("/api/problems/P1").json()["data"]["title"] == "新标题"
    # 已审批的申请再次审批 → 409
    assert client.put(f"/api/applications/{aid}", json={"decision": "reject"}).status_code == 409


def test_apply_delete_reject(client, bob):
    assert client.post("/api/problems/", json=_pb("P2")).status_code == 200
    r = bob.post("/api/problems/P2/apply", json={"action": "delete"})
    assert r.status_code == 200
    aid = r.json()["data"]["application_id"]
    r = client.put(f"/api/applications/{aid}", json={"decision": "reject"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "rejected"
    assert client.get("/api/problems/P2").status_code == 200  # 拒绝后题目仍在


def test_apply_delete_accept(client, bob):
    assert client.post("/api/problems/", json=_pb("P3")).status_code == 200
    r = bob.post("/api/problems/P3/apply", json={"action": "delete"})
    assert r.status_code == 200
    aid = r.json()["data"]["application_id"]
    r = client.put(f"/api/applications/{aid}", json={"decision": "accept"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "accepted"
    assert client.get("/api/problems/P3").status_code == 404  # 接纳后题目已删除


def test_apply_invalid_action_and_missing_problem(client, bob):
    assert client.post("/api/problems/", json=_pb("P4")).status_code == 200
    assert bob.post("/api/problems/P4/apply", json={"action": "rename"}).status_code == 400
    assert bob.post("/api/problems/NOPE/apply", json={"action": "delete"}).status_code == 404


def test_accept_edit_failed_marks_rejected(client, bob):
    # 申请后题目被删 → 接纳执行失败 → 自动拒绝并记录原因（队列不卡死）
    assert client.post("/api/problems/", json=_pb("P5")).status_code == 200
    r = bob.post("/api/problems/P5/apply", json={
        "action": "edit", "payload": _pb("P5", title="改"),
    })
    assert r.status_code == 200
    aid = r.json()["data"]["application_id"]
    assert client.delete("/api/problems/P5").status_code == 200
    r = client.put(f"/api/applications/{aid}", json={"decision": "accept"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "rejected"
    assert "not found" in r.json()["data"]["decision_note"]
