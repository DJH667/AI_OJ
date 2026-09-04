"""D3 Step2 评测主体测试（Linux 环境执行，需 python3/g++）：

语言注册/列表、提交 404/429、评测结果状态机
（AC/WA/CE/RE/TLE、输出归一、score/counts、submit/resolve 统计）。
注意：本文件用例需真实执行用户代码，仅在 Linux（WSL venv）下可全绿；
提交后由后台异步评测，用例轮询等待完成，避免与评测线程竞态。
"""
import time

import pytest
from fastapi.testclient import TestClient

from main import app
from app import config
from app.db import store
from app.services import judge, submissions as sub_service

PASSWORD = "secret123"
AC_CODE = "a, b = map(int, input().split())\nprint(a + b)"


@pytest.fixture()
def client():
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD}).status_code == 200
        assert c.post("/api/reset/").status_code == 200
        assert c.post("/api/auth/login", json={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD}).status_code == 200
        assert c.post("/api/users/", json={"username": "coder", "password": PASSWORD}).status_code == 200
        assert c.post("/api/auth/login", json={"username": "coder", "password": PASSWORD}).status_code == 200
        yield c


DEFAULT_TESTCASES = [
    {"input": "1 2", "output": "3"},
    {"input": "-5 3", "output": "-2"},
    {"input": "0 0", "output": "0"},
    {"input": "1000000000 1000000000", "output": "2000000000"},
    {"input": "-1 -1", "output": "-2"},
]


def _add_problem(client, pid="P1", testcases=None, time_limit=1.0):
    body = {
        "id": pid,
        "title": "测试题",
        "description": "desc",
        "input_description": "in",
        "output_description": "out",
        "samples": [{"input": "1 2", "output": "3"}],
        "constraints": "c",
        "testcases": testcases if testcases is not None else DEFAULT_TESTCASES,
        "time_limit": time_limit,
        "memory_limit": 128,
    }
    return client.post("/api/problems/", json=body)


def _submit(client, pid, language, code):
    return client.post("/api/submissions/", json={"problem_id": pid, "language": language, "code": code})


def _wait_judged(sid, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rec = sub_service.get(sid)
        if rec is not None and rec["status"] != "pending":
            time.sleep(0.1)  # 让统计更新（resolve_count）完成
            return rec
        time.sleep(0.05)
    raise AssertionError(f"judge timeout for submission {sid}")


# ---------- 语言 ----------

def test_languages_builtin_and_list(client):
    r = client.get("/api/languages/")
    assert r.status_code == 200
    assert set(r.json()["data"]["name"]) >= {"python", "cpp"}


def test_register_language_rules(client):
    body = {"name": "go", "file_ext": ".go", "run_cmd": "go run {src}"}
    r = client.post("/api/languages/", json=body)
    assert r.status_code == 200
    assert r.json()["data"] == {"name": "go"}
    assert "go" in client.get("/api/languages/").json()["data"]["name"]
    assert client.post("/api/languages/", json=body).status_code == 400
    assert client.post("/api/languages/", json=body).json()["msg"] == "language already exists"
    anon = TestClient(app)
    assert anon.post("/api/languages/", json=body).status_code == 401


# ---------- 提交与评测 ----------

def test_submit_ac_python(client):
    assert _add_problem(client, "P1").status_code == 200
    r = _submit(client, "P1", "python", AC_CODE)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "pending"
    record = _wait_judged(data["submission_id"])
    assert record["status"] == "success"
    assert record["score"] == 50 and record["counts"] == 50  # 5 测例 × 10
    assert len(record["details"]) == 5
    assert all(d["result"] == "AC" for d in record["details"])
    assert record["compile_info"] is None
    assert record["run_info"]["result"] == "finished"
    user = store.load_json(config.USERS_DIR, "coder")
    assert user["submit_count"] == 1 and user["resolve_count"] == 1


def test_submit_wa_and_resolve_once(client):
    assert _add_problem(client, "P1").status_code == 200
    # 全错的代码（任何输入都输出 999，无测例命中）
    r = _submit(client, "P1", "python", "print(999)")
    rec = _wait_judged(r.json()["data"]["submission_id"])
    assert rec["status"] == "success"
    assert rec["score"] == 0 and rec["details"][0]["result"] == "WA"
    # 第二次 AC → resolve 只计一次
    r = _submit(client, "P1", "python", AC_CODE)
    _wait_judged(r.json()["data"]["submission_id"])
    user = store.load_json(config.USERS_DIR, "coder")
    assert user["submit_count"] == 2
    assert user["resolve_count"] == 1


def test_output_normalization_trailing_spaces(client):
    tcs = [{"input": "1 2", "output": "3 \n\n"}]
    assert _add_problem(client, "P1", testcases=tcs).status_code == 200
    rec = _wait_judged(_submit(client, "P1", "python", AC_CODE).json()["data"]["submission_id"])
    assert rec["details"][0]["result"] == "AC"


def test_compile_error_cpp(client):
    assert _add_problem(client, "P1").status_code == 200
    r = _submit(client, "P1", "cpp", "int main() { return")  # 语法错误
    rec = _wait_judged(r.json()["data"]["submission_id"])
    assert rec["status"] == "success"
    assert rec["compile_info"]["result"] == "compile error"
    assert rec["score"] == 0
    assert rec["details"] == []


def test_compile_ok_cpp_ac(client):
    assert _add_problem(client, "P1").status_code == 200
    cpp = "#include <iostream>\nint main(){long long a,b;std::cin>>a>>b;std::cout<<a+b;}"
    r = _submit(client, "P1", "cpp", cpp)
    rec = _wait_judged(r.json()["data"]["submission_id"])
    assert rec["compile_info"]["result"] == "success"
    assert rec["status"] == "success"
    assert rec["score"] == 50
    assert all(d["result"] == "AC" for d in rec["details"])


def test_runtime_error_python(client):
    assert _add_problem(client, "P1").status_code == 200
    r = _submit(client, "P1", "python", "raise RuntimeError('boom')")
    rec = _wait_judged(r.json()["data"]["submission_id"])
    assert rec["status"] == "success"
    assert rec["details"][0]["result"] == "RE"


def test_time_limit_tle(client):
    tcs = [{"input": "", "output": "0"}]
    assert _add_problem(client, "P1", testcases=tcs, time_limit=0.2).status_code == 200
    r = _submit(client, "P1", "python", "while True:\n    pass")
    rec = _wait_judged(r.json()["data"]["submission_id"])
    assert rec["status"] == "success"
    assert rec["details"][0]["result"] == "TLE"
    assert rec["score"] == 0


def test_submit_404_and_rate_limit(client):
    assert _add_problem(client, "P1").status_code == 200
    assert _submit(client, "NOPE", "python", AC_CODE).status_code == 404
    assert _submit(client, "P1", "brainfuck", AC_CODE).status_code == 404
    codes = [_submit(client, "P1", "python", AC_CODE).status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429
    # 换题不触发（429 按单人单题）
    assert _add_problem(client, "P2").status_code == 200
    assert _submit(client, "P2", "python", AC_CODE).status_code == 200


def test_judge_missing_problem_error(client):
    # 手工构造指向不存在题目的提交（不经 API，避免与后台评测线程竞争）→ status error、不泄露路径
    coder = store.load_json(config.USERS_DIR, "coder")
    rec = sub_service.new_pending(coder, "GHOST", "python", AC_CODE)
    sub_service.save(rec)
    judge.judge_submission(rec["submission_id"])
    final = sub_service.get(rec["submission_id"])
    assert final["status"] == "error"
    assert final["error_info"] == "problem not found"
    assert "tmp" not in final["error_info"] and "/mnt" not in final["error_info"]
