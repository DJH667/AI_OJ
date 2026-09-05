"""D4 测试：Step2 收尾（psutil → MLE/真实 memory）+ Step3 评测管理。

- MLE：python 大内存分配超题目 memory_limit → MLE（真实评测，Linux）
- 列表：一级条件至少其一/可见性（普通用户仅自己）/status 过滤/摘要裁剪/分页语义
- 详情：本人或管理员、404、pending 结构
- rejudge：仅管理员、覆盖回 pending 并重评
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


def _drain_judges(timeout: float = 25.0) -> None:
    """等待后台评测收敛：pending 消失或 pending 集稳定 3s（跳过手工构造的伪 pending）。
    评审发现 #1（2026-09-05）flaky 修复。"""
    deadline = time.monotonic() + timeout
    last_pending = None
    stable_since = None

    def _pending() -> list[str]:
        return sorted(
            r["submission_id"] for _, r in store.iter_all(config.SUBMISSIONS_DIR) if r.get("status") == "pending"
        )

    while time.monotonic() < deadline:
        current = _pending()
        if not current:
            time.sleep(0.1)
            if not _pending():
                return
            continue
        if current == last_pending:
            if stable_since is None:
                stable_since = time.monotonic()
            elif time.monotonic() - stable_since > 3.0:
                return
        else:
            stable_since = None
        last_pending = current
        time.sleep(0.1)
    raise AssertionError("background judge tasks did not converge")


@pytest.fixture()
def client():
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD}).status_code == 200
        assert c.post("/api/reset/").status_code == 200
        assert c.post("/api/auth/login", json={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD}).status_code == 200
        for u in ("alice", "bob", "coder"):
            assert c.post("/api/users/", json={"username": u, "password": PASSWORD}).status_code == 200
        yield c
        _drain_judges()


def _login(username):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200
    return c


def _add_problem(client, pid, **over):
    body = {
        "id": pid, "title": "t", "description": "d", "input_description": "i",
        "output_description": "o", "samples": [{"input": "1", "output": "1"}],
        "constraints": "c", "testcases": [{"input": "1 2", "output": "3"}],
        "time_limit": 1.0, "memory_limit": 128,
    }
    body.update(over)
    return client.post("/api/problems/", json=body)


def _submit(client, pid, code, language="python"):
    return client.post("/api/submissions/", json={"problem_id": pid, "language": language, "code": code})


def _wait_judged(sid, timeout=20.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rec = sub_service.get(sid)
        if rec is not None and rec["status"] != "pending":
            time.sleep(0.1)
            return rec
        time.sleep(0.05)
    raise AssertionError(f"judge timeout {sid}")


def _mk(username, pid, status, score=10, counts=10):
    """直接在存储层构造提交记录（避免逐条真实评测耗时）。"""
    user = store.load_json(config.USERS_DIR, username)
    rec = sub_service.new_pending(user, pid, "python", "code")
    rec.update(status=status, score=score, counts=counts)
    sub_service.save(rec)
    return rec["submission_id"]


# ---------- MLE（Step2 收尾）----------

def test_memory_limit_mle(client):
    assert _add_problem(client, "MEM", testcases=[{"input": "0", "output": "0"}], time_limit=5.0, memory_limit=16).status_code == 200
    code = "x = bytearray(64 * 1024 * 1024)\nprint(len(x))"
    sid = _submit(client, "MEM", code).json()["data"]["submission_id"]
    rec = _wait_judged(sid)
    assert rec["status"] == "success"
    assert rec["score"] == 0
    assert rec["details"][0]["result"] == "MLE"
    assert rec["details"][0]["memory"] > 0  # 已记录真实峰值（MB）


# ---------- Step3 列表 ----------

def _build_list_data(client):
    assert _add_problem(client, "P1").status_code == 200
    assert _add_problem(client, "P2").status_code == 200
    s1 = _mk("alice", "P1", "success", 30, 30)   # alice P1 AC
    s2 = _mk("alice", "P1", "pending")           # alice P1 pending
    s3 = _mk("alice", "P2", "success", 0, 20)    # alice P2 WA
    s4 = _mk("bob", "P1", "success", 10, 10)     # bob P1 AC
    return s1, s2, s3, s4


def test_list_filters_and_pagination(client):
    s1, s2, s3, s4 = _build_list_data(client)
    # 一级条件至少其一：全空 → 400
    r = client.get("/api/submissions/")
    assert r.status_code == 400
    assert r.json()["msg"] == "at least one of user_id/problem_id is required"
    # admin ?problem_id=P1 → alice×2 + bob×1 = 3；按提交倒序
    r = client.get("/api/submissions/", params={"problem_id": "P1"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 3
    ids = [x["submission_id"] for x in data["submissions"]]
    assert ids == sorted(ids, reverse=True)
    # pending 条目仅 id+status；success 条目含 score/counts
    pend = [x for x in data["submissions"] if x["status"] == "pending"]
    assert len(pend) == 1 and set(pend[0].keys()) == {"submission_id", "status"}
    ok = [x for x in data["submissions"] if x["status"] == "success"]
    assert ok and all({"submission_id", "status", "score", "counts"} <= set(x.keys()) for x in ok)
    # 组合与 status 过滤（user_id 为数字 ID，如 alice=1、bob=2）
    assert client.get("/api/submissions/", params={"user_id": "1"}).json()["data"]["total"] == 3
    assert client.get("/api/submissions/", params={"user_id": "1", "problem_id": "P1"}).json()["data"]["total"] == 2
    assert client.get("/api/submissions/", params={"problem_id": "P1", "status": "success"}).json()["data"]["total"] == 2
    # 分页语义
    r = client.get("/api/submissions/", params={"problem_id": "P1", "page": 1, "page_size": 2})
    assert r.status_code == 200 and r.json()["data"]["total"] == 3 and len(r.json()["data"]["submissions"]) == 2
    assert client.get("/api/submissions/", params={"problem_id": "P1", "page": 2}).status_code == 400
    assert client.get("/api/submissions/", params={"problem_id": "P1", "page_size": 2}).status_code == 200
    # 未登录 401
    anon = TestClient(app)
    assert anon.get("/api/submissions/", params={"problem_id": "P1"}).status_code == 401


def test_list_visibility_user_only_own(client):
    _build_list_data(client)
    bob = _login("bob")  # bob user_id="2"
    # 普通用户 ?problem_id=P1 → 仅自己的记录（1 条，而非全站 3 条）
    r = bob.get("/api/submissions/", params={"problem_id": "P1"})
    assert r.status_code == 200 and r.json()["data"]["total"] == 1
    # ?user_id=自己（"2"）OK；?user_id=他人（"1"）→ 403
    assert bob.get("/api/submissions/", params={"user_id": "2"}).json()["data"]["total"] == 1
    r = bob.get("/api/submissions/", params={"user_id": "1"})
    assert r.status_code == 403


# ---------- Step3 详情 ----------

def test_detail_permission_and_structure(client):
    s1, s2, _, _ = _build_list_data(client)
    alice = _login("alice")
    # 本人
    r = alice.get(f"/api/submissions/{s1}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["user_id"] == "1" and data["problem_id"] == "P1" and data["language"] == "python"
    assert data["status"] == "success" and data["score"] == 30 and data["counts"] == 30
    assert "compile_info" in data and "code" in data and "error_info" in data
    # pending：至少 id+status，未产生字段可为 null
    r = alice.get(f"/api/submissions/{s2}")
    assert r.json()["data"]["status"] == "pending"
    assert r.json()["data"]["compile_info"] is None
    # 他人 403 / admin 200 / 不存在 404 / 未登录 401
    bob = _login("bob")
    assert bob.get(f"/api/submissions/{s1}").status_code == 403
    assert client.get(f"/api/submissions/{s1}").status_code == 200  # admin
    assert alice.get("/api/submissions/9999").status_code == 404
    anon = TestClient(app)
    assert anon.get(f"/api/submissions/{s1}").status_code == 401


# ---------- Step3 rejudge ----------

def test_rejudge_rules(client):
    assert _add_problem(client, "RJ").status_code == 200
    # 先构造一条真实失败提交再重评成功：直接提交一条 pending 前先给错误代码
    sid = _submit(client, "RJ", "print(999)").json()["data"]["submission_id"]
    rec = _wait_judged(sid)
    assert rec["score"] == 0
    # 非管理员 → 403
    alice = _login("alice")
    assert alice.put(f"/api/submissions/{sid}/rejudge").status_code == 403
    # 管理员 rejudge → 覆盖回 pending 并重新评测（这次代码已定 WA，改为构造 AC 场景）
    # 用 coder 的 AC 提交进行 rejudge（同一条记录，代码不变仍 WA）：
    r = client.put(f"/api/submissions/{sid}/rejudge")
    assert r.status_code == 200
    assert r.json()["msg"] == "rejudge started"
    assert r.json()["data"] == {"submission_id": sid, "status": "pending"}
    rec2 = _wait_judged(sid)
    assert rec2["status"] == "success"
    # 不存在 → 404
    assert client.put("/api/submissions/9999/rejudge").status_code == 404


def test_rejudge_overwrites_and_reruns_ok(client):
    # 题目正确代码 AC 后：把记录改为 pending 重评仍 AC（覆盖语义）
    testcases = [
        {"input": "1 2", "output": "3"},
        {"input": "-5 3", "output": "-2"},
        {"input": "0 0", "output": "0"},
        {"input": "10 20", "output": "30"},
        {"input": "-1 -1", "output": "-2"},
    ]
    assert _add_problem(client, "RJ", testcases=testcases).status_code == 200
    sid = _submit(client, "RJ", AC_CODE).json()["data"]["submission_id"]
    rec = _wait_judged(sid)
    assert rec["score"] == 50
    # 管理员 rejudge → 覆盖为 pending → 自动重跑 → 仍 AC 50
    assert client.put(f"/api/submissions/{sid}/rejudge").status_code == 200
    rec2 = _wait_judged(sid)
    assert rec2["score"] == 50 and len(rec2["details"]) == 5


def test_rejudge_updates_stats_realtime(client):
    """Q6（2026-09-05 用户判定）：rejudge 后实时重算该用户统计——
    唯一 AC 提交被重评失败 → resolve_count 回退、submit_count 不变。"""
    testcases = [
        {"input": "1 2", "output": "3"},
        {"input": "-5 3", "output": "-2"},
        {"input": "0 0", "output": "0"},
        {"input": "10 20", "output": "30"},
        {"input": "-1 -1", "output": "-2"},
    ]
    assert _add_problem(client, "P1", testcases=testcases).status_code == 200
    coder = _login("coder")
    sid = _submit(coder, "P1", AC_CODE).json()["data"]["submission_id"]
    rec = _wait_judged(sid)
    assert rec["status"] == "success" and rec["score"] == 50

    def _stats():
        u = store.load_json(config.USERS_DIR, "coder")
        return u["submit_count"], u["resolve_count"]

    assert _stats() == (1, 1)
    # 修改题目使原代码不再通过（期望输出改为 999）
    body = {
        "id": "P1", "title": "测试题", "description": "d", "input_description": "i",
        "output_description": "o", "samples": [{"input": "1 2", "output": "3"}],
        "constraints": "c", "testcases": [{"input": "1 2", "output": "999"}],
        "time_limit": 1.0, "memory_limit": 128,
    }
    assert client.put("/api/problems/P1", json=body).status_code == 200
    # rejudge → 覆盖重跑 → WA → resolve 回退
    assert client.put(f"/api/submissions/{sid}/rejudge").status_code == 200
    rec2 = _wait_judged(sid)
    assert rec2["status"] == "success" and rec2["score"] == 0
    assert _stats() == (1, 0)  # submit 不变、resolve 实时回退
