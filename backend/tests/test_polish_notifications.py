"""polish 2026-09-09：信息中心通知（AI 生题完成 + 申请审批结果）。"""
import json
import time

import pytest
from fastapi.testclient import TestClient

from main import app
from app import config
from app.services import llm_client

PASSWORD = "secret123"


def _pb(pid: str = "P1"):
    return {
        "id": pid,
        "title": "求和",
        "description": "计算两个数的和",
        "input_description": "两个整数",
        "output_description": "一个整数",
        "samples": [{"input": "1 2", "output": "3"}],
        "constraints": "范围 1e9",
        "testcases": [{"input": "1 2", "output": "3"}],
    }


def _fake_problem():
    return {
        "id": "AI-SUM", "title": "AI 求和", "description": "求和",
        "input_description": "两个整数", "output_description": "一个整数",
        "samples": [{"input": "1 2", "output": "3"}],
        "constraints": "范围 1e9",
        "testcases": [{"input": "1 2", "output": "3"}],
        "time_limit": 1.0, "memory_limit": 128, "difficulty_score": 2.0, "language": "python",
    }


def _wait_task(c, task_id, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = c.get(f"/api/ai/problem-tasks/{task_id}")
        assert r.status_code == 200
        data = r.json()["data"]
        if data["status"] not in ("waiting", "running"):
            return data
        time.sleep(0.05)
    raise AssertionError(f"task timeout {task_id}")


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
    with TestClient(app) as c:
        assert c.post("/api/users/", json={"username": "bob", "password": PASSWORD}).status_code == 200
        assert c.post("/api/auth/login", json={"username": "bob", "password": PASSWORD}).status_code == 200
        yield c


def test_ai_done_notification_and_read(client, bob, monkeypatch):
    monkeypatch.setattr(llm_client, "chat",
                        lambda messages, username, temperature=0.2, on_progress=None: {
                            "content": json.dumps(_fake_problem()),
                            "usage": {"prompt_tokens": 10, "completion_tokens": 5}, "mock": True})
    r = bob.post("/api/ai/problem-tasks/", json={"requirement": "一道求和题", "language": "python"})
    assert r.status_code == 200
    _wait_task(bob, r.json()["data"]["task_id"])

    data = bob.get("/api/notifications/").json()["data"]
    assert data["unread"] >= 1
    note = data["notifications"][0]
    assert note["kind"] == "ai_task" and note["task_id"] == r.json()["data"]["task_id"]
    # 未读数接口
    assert bob.get("/api/notifications/unread-count").json()["data"]["unread"] >= 1
    # 单条已读
    assert bob.put(f"/api/notifications/{note['notification_id']}/read").status_code == 200
    assert bob.get("/api/notifications/unread-count").json()["data"]["unread"] < data["unread"]
    # 他人不能读我的通知
    assert client.put(f"/api/notifications/{note['notification_id']}/read").status_code == 404


def test_application_result_notification(client, bob):
    assert client.post("/api/problems/", json=_pb("P1")).status_code == 200
    r = bob.post("/api/problems/P1/apply", json={"action": "edit", "payload": _pb("P1")})
    aid = r.json()["data"]["application_id"]
    assert client.put(f"/api/applications/{aid}", json={"decision": "accept"}).status_code == 200

    data = bob.get("/api/notifications/").json()["data"]
    app_notes = [n for n in data["notifications"] if n["kind"] == "application"]
    assert app_notes and app_notes[0]["problem_id"] == "P1"
    assert "通过" in app_notes[0]["title"]
