"""D5 Step5 评测日志测试（可见性精确语义按助教 Q7，2026-09-05）：

- public_cases=False：本人可见 score/counts、details 为空；其他用户 403（并记审计 403）
- public_cases=True：本人与所有登录用户可见完整 details
- 管理员始终可见完整日志；public_cases 不进题目对外字段且 CRUD 覆盖不丢失
- PUT log_visibility 权限/404；GET /api/logs/access/ 审计筛选与权限
"""
import time

import pytest
from fastapi.testclient import TestClient

from main import app
from app import config
from app.db import store
from app.services import submissions as sub_service

PASSWORD = "secret123"
AC_CODE = "a, b = map(int, input().split())\nprint(a + b)"


@pytest.fixture()
def client():
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD}).status_code == 200
        assert c.post("/api/reset/").status_code == 200
        assert c.post("/api/auth/login", json={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD}).status_code == 200
        for u in ("alice", "bob"):
            assert c.post("/api/users/", json={"username": u, "password": PASSWORD}).status_code == 200
        yield c


def _login(username):
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": username, "password": PASSWORD}).status_code == 200
    return c


def _add_problem(client, pid="P1"):
    body = {
        "id": pid, "title": "求和", "description": "d", "input_description": "i",
        "output_description": "o", "samples": [{"input": "1 2", "output": "3"}],
        "constraints": "c", "testcases": [{"input": "1 2", "output": "3"}],
        "time_limit": 1.0, "memory_limit": 128,
    }
    return client.post("/api/problems/", json=body)


def _wait_judged(sid, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rec = sub_service.get(sid)
        if rec is not None and rec["status"] != "pending":
            time.sleep(0.1)
            return rec
        time.sleep(0.05)
    raise AssertionError(f"judge timeout {sid}")


def _setup_submission(client, username="alice"):
    """建题 + 该用户 AC 提交，返回 sid。"""
    assert _add_problem(client).status_code == 200
    u = _login(username)
    sid = u.post("/api/submissions/", json={"problem_id": "P1", "language": "python", "code": AC_CODE}).json()["data"]["submission_id"]
    rec = _wait_judged(sid)
    assert rec["status"] == "success" and rec["score"] == 10
    return sid


# ---------- public_cases=False ----------

def test_owner_log_not_public_no_details(client):
    sid = _setup_submission(client, "alice")
    alice = _login("alice")
    r = alice.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 200
    data = r.json()["data"]
    # 本人可见 score/counts，但看不到测例明细 details（Q7）
    assert data["score"] == 10 and data["counts"] == 10
    assert data["details"] == []


def test_other_user_403_when_not_public_and_audited(client):
    sid = _setup_submission(client, "alice")
    bob = _login("bob")
    r = bob.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 403
    assert r.json()["msg"] == "permission denied"
    # 审计记录了这次被拒（status=403）
    entries = [e for _, e in store.iter_all(config.ACCESS_LOGS_DIR)]
    assert any(e["user_id"] == "2" and e["status"] == "403" and e["problem_id"] == "P1" for e in entries)


def test_admin_always_sees_full_details(client):
    sid = _setup_submission(client, "alice")
    r = client.get(f"/api/submissions/{sid}/log")  # admin
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["details"]) == 1
    d = data["details"][0]
    assert set(d.keys()) == {"id", "result", "time", "memory"}
    assert d["result"] == "AC"
    assert data["score"] == 10


# ---------- public_cases=True ----------

def test_public_cases_opens_details_to_all(client):
    sid = _setup_submission(client, "alice")
    assert client.put("/api/problems/P1/log_visibility", json={"public_cases": True}).status_code == 200
    # 其他用户与本人现在都可见完整 details
    bob = _login("bob")
    r = bob.get(f"/api/submissions/{sid}/log")
    assert r.status_code == 200
    assert len(r.json()["data"]["details"]) == 1
    alice = _login("alice")
    assert len(alice.get(f"/api/submissions/{sid}/log").json()["data"]["details"]) == 1


def test_public_cases_not_exposed_and_kept_on_update(client):
    sid = _setup_submission(client, "alice")
    assert client.put("/api/problems/P1/log_visibility", json={"public_cases": True}).status_code == 200
    # public_cases 不进题目对外字段
    data = client.get("/api/problems/P1").json()["data"]
    assert "public_cases" not in data
    # CRUD 覆盖题目不丢失 public_cases
    body = {
        "id": "P1", "title": "新标题", "description": "d", "input_description": "i",
        "output_description": "o", "samples": [{"input": "1 2", "output": "3"}],
        "constraints": "c", "testcases": [{"input": "1 2", "output": "3"}],
    }
    assert client.put("/api/problems/P1", json=body).status_code == 200
    bob = _login("bob")
    assert len(bob.get(f"/api/submissions/{sid}/log").json()["data"]["details"]) == 1  # 仍公开


def test_log_visibility_rules(client):
    assert _add_problem(client).status_code == 200
    # 非管理员 → 403
    bob = _login("bob")
    assert bob.put("/api/problems/P1/log_visibility", json={"public_cases": True}).status_code == 403
    # 题目不存在 → 404
    assert client.put("/api/problems/NOPE/log_visibility", json={"public_cases": True}).status_code == 404
    # body 缺省 → public_cases=False
    r = client.put("/api/problems/P1/log_visibility", json={})
    assert r.status_code == 200
    assert r.json()["data"] == {"problem_id": "P1", "public_cases": False}


# ---------- 审计查询 ----------

def test_access_audit_query_rules(client):
    sid = _setup_submission(client, "alice")
    bob = _login("bob")
    assert bob.get(f"/api/submissions/{sid}/log").status_code == 403
    assert client.get(f"/api/submissions/{sid}/log").status_code == 200  # admin 查看也记录
    # 一级条件至少其一（全空 400）
    assert client.get("/api/logs/access/").status_code == 400
    # 按 user_id / problem_id 过滤
    r = client.get("/api/logs/access/", params={"user_id": "2"})
    assert r.status_code == 200
    assert r.json()["data"] and all(e["user_id"] == "2" and e["status"] == "403" for e in r.json()["data"])
    r = client.get("/api/logs/access/", params={"problem_id": "P1"})
    assert r.status_code == 200
    assert any(e["action"] == "view_logs" for e in r.json()["data"])
    # 非管理员 → 403
    assert bob.get("/api/logs/access/", params={"problem_id": "P1"}).status_code == 403
    # 分页（page_size 有、page 无 → 第 1 页）
    assert client.get("/api/logs/access/", params={"problem_id": "P1", "page_size": 1}).status_code == 200


def test_log_missing_submission_404(client):
    alice = _login("alice")
    assert alice.get("/api/submissions/99999/log").status_code == 404
