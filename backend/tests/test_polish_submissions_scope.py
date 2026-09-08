"""polish 2026-09-08：GET /api/submissions/?scope=all（仅管理员全量查询）。"""
import pytest
from fastapi.testclient import TestClient

from main import app
from app import config

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


def test_scope_all_admin_only(client, bob):
    # 管理员可全量（空题库/空提交也 200）
    assert client.get("/api/submissions/", params={"scope": "all"}).status_code == 200
    # 普通用户 scope=all → 403
    assert bob.get("/api/submissions/", params={"scope": "all"}).status_code == 403
    # 契约保持：无一级条件且无 scope → 400
    assert client.get("/api/submissions/").status_code == 400


def test_scope_all_returns_everyones_submissions(client, bob):
    assert client.post("/api/problems/", json=_pb("P1")).status_code == 200
    langs = client.get("/api/languages/").json()["data"]["name"]
    lang = langs[0] if langs else "python"
    assert client.post("/api/submissions/", json={
        "problem_id": "P1", "language": lang, "code": "print(1)",
    }).status_code == 200
    assert bob.post("/api/submissions/", json={
        "problem_id": "P1", "language": lang, "code": "print(1)",
    }).status_code == 200
    data = client.get("/api/submissions/", params={"scope": "all"}).json()["data"]
    assert {s["submission_id"] for s in data["submissions"]} and len(data["submissions"]) == 2
    # 指定题目 + scope=all 同样可用
    data2 = client.get("/api/submissions/", params={
        "scope": "all", "problem_id": "P1",
    }).json()["data"]
    assert len(data2["submissions"]) == 2
