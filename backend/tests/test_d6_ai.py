"""D6 AI 智能命题后端测试（mock 链路；硬核对拍需 Linux 执行 python3 子进程）：

- model-config：PUT/GET 脱敏（api_key 不回显）、计价字段
- 普通任务：创建(waiting) → 轮询 → completed + result(题目 JSON) + usage/cost
- 硬核任务：monkeypatch chat 返回含三代码的产出 → 对拍通过 → completed、testcases 为对拍集；
  缺少 meta 三代码 → review 标记（用尽重试）
- 纯文本语言兜底：产出含未注册语言 → failed + 可用列表
- 权限：未登录 401、越权 403、不存在 404、终态 cancel 409
"""
import json
import time

import pytest
from fastapi.testclient import TestClient

from main import app
from app import config
from app.services import ai_config, ai_tasks, llm_client

PASSWORD = "secret123"


@pytest.fixture(autouse=True)
def _clean_ai_configs():
    """model-config 是 per-user 系统配置（reset 不清），测试前后清空全部用户配置，保证走 mock。"""
    from app.db import store as _store

    for key in _store.list_keys(config.AI_CONFIGS_DIR):
        _store.delete_json(config.AI_CONFIGS_DIR, key)
    yield
    for key in _store.list_keys(config.AI_CONFIGS_DIR):
        _store.delete_json(config.AI_CONFIGS_DIR, key)

GEN = "import json\ncases = [{'input': '1 2', 'small': True}, {'input': '-5 3', 'small': True}, {'input': '0 0', 'small': True}]\nprint(json.dumps(cases))"
STD = "a, b = map(int, input().split())\nprint(a + b)"
BRUTE = "a, b = map(int, input().split())\nprint(a + b)"


def _fake_problem(**over):
    problem = {
        "id": "AI-SUM", "title": "AI Sum", "description": "输出 a+b",
        "input_description": "两个整数", "output_description": "一个整数",
        "samples": [{"input": "1 2", "output": "3"}], "constraints": "1e9",
        "testcases": [{"input": "1 2", "output": "3"}], "time_limit": 1.0,
        "memory_limit": 128, "difficulty_score": 2.0, "language": "python",
        "meta": {"generator": GEN, "std_solution": STD, "brute_solution": BRUTE},
    }
    problem.update(over)
    return problem


@pytest.fixture()
def client():
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD}).status_code == 200
        assert c.post("/api/reset/").status_code == 200
        assert c.post("/api/auth/login", json={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD}).status_code == 200
        for u in ("alice",):
            assert c.post("/api/users/", json={"username": u, "password": PASSWORD}).status_code == 200
        yield c


def _login(username):
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"username": username, "password": PASSWORD}).status_code == 200
    return c


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


# ---------- model-config ----------

def test_model_config_roundtrip_hides_key(client):
    # polish 2026-09-08：价格/汇率自动化——旧手填字段被忽略，单价按模型目录自动写入
    body = {"provider_url": "https://openrouter.ai/api/v1", "model": "deepseek-v4-flash",
            "api_key": "sk-secret-123", "input_price": 999, "output_price": 999,
            "price_unit": 1, "fx_rate": 0.1}
    r = client.put("/api/ai/model-config", json=body)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["api_key_configured"] is True
    assert "api_key" not in data and "sk-secret" not in r.text
    assert data["model"] == "deepseek-v4-flash"
    assert data["currency"] == "CNY" and data["fx_rate"] > 0
    assert data["input_price"] != 999 and data["output_price"] != 999  # 价格来自目录而非用户
    assert data["price_unit"] == 1_000_000
    # GET 同样脱敏
    data = client.get("/api/ai/model-config").json()["data"]
    assert data["api_key_configured"] is True and "api_key" not in data
    # 未登录 401
    anon = TestClient(app)
    assert anon.get("/api/ai/model-config").status_code == 401
    # reset 不清 model-config（per-user 系统配置，admin 的仍保留）
    client.post("/api/reset/")
    assert client.post("/api/auth/login", json={"username": config.ADMIN_USERNAME, "password": config.ADMIN_PASSWORD}).status_code == 200
    assert client.get("/api/ai/model-config").json()["data"]["api_key_configured"] is True


# ---------- 普通任务（mock）----------

def test_task_flow_normal_mock(client, monkeypatch):
    monkeypatch.setattr(llm_client, "chat", lambda messages, username, temperature=0.2: {
        "content": json.dumps(_fake_problem()), "usage": {"prompt_tokens": 100, "completion_tokens": 30}, "mock": True})
    r = client.post("/api/ai/problem-tasks/", json={"requirement": "一道求和题"})
    assert r.status_code == 200
    task_id = r.json()["data"]["task_id"]
    data = _wait_task(client, task_id)
    assert data["status"] == "completed"
    assert data["phase"] == "completed"
    assert data.get("started_at") and data.get("finished_at")
    assert data["result"]["id"] == "AI-SUM"
    assert data["usage"]["input_tokens"] == 100 and data["usage"]["cost"] >= 0
    assert data["usage"]["total_tokens"] == 130
    assert data["usage"]["currency"] == "CNY"
    # 语言结构化校验：未注册语言 400
    assert client.post("/api/ai/problem-tasks/", json={"requirement": "x", "language": "java"}).status_code == 400
    # 参考题不存在 404
    assert client.post("/api/ai/problem-tasks/", json={"requirement": "x", "problem_id": "NOPE"}).status_code == 404
    # 未登录 401
    anon = TestClient(app)
    assert anon.post("/api/ai/problem-tasks/", json={"requirement": "x"}).status_code == 401


# ---------- 硬核：对拍通过 ----------

def test_task_hardcore_verify_passes(client, monkeypatch):
    monkeypatch.setattr(llm_client, "chat", lambda messages, username, temperature=0.2: {
        "content": json.dumps(_fake_problem()), "usage": {"prompt_tokens": 200, "completion_tokens": 60}, "mock": True})
    r = client.post("/api/ai/problem-tasks/", json={"requirement": "a+b 题", "hardcore": True, "retry_limit": 1})
    task_id = r.json()["data"]["task_id"]
    data = _wait_task(client, task_id, timeout=30.0)
    assert data["status"] == "completed"
    assert data["review"] is False
    # testcases 为对拍生成集（3 条，均与标答/暴力一致）
    assert len(data["result"]["testcases"]) == 3
    assert all(tc["output"].strip() in ("3", "-2", "0") for tc in data["result"]["testcases"])


# ---------- 硬核：缺 meta 三代码 → 复核 ----------

def test_task_hardcore_review_when_verify_fails(client, monkeypatch):
    bad = _fake_problem()
    bad["meta"] = {"note": "no codes"}  # 缺 generator/std/brute → verify 必失败
    monkeypatch.setattr(llm_client, "chat", lambda messages, username, temperature=0.2: {
        "content": json.dumps(bad), "usage": {"prompt_tokens": 50, "completion_tokens": 10}, "mock": True})
    r = client.post("/api/ai/problem-tasks/", json={"requirement": "x", "hardcore": True, "retry_limit": 1})
    task_id = r.json()["data"]["task_id"]
    data = _wait_task(client, task_id, timeout=30.0)
    # 首次失败 + 1 次重试仍失败 → completed + review
    assert data["status"] == "completed"
    assert data["review"] is True
    assert "hardcore mode requires" in data["review_note"]
    assert data["result"] is None  # 题目不入库


# ---------- 纯文本语言兜底 ----------

def test_task_language_not_supported_fails(client, monkeypatch):
    p = _fake_problem(language="java")  # 结构化未带 language → 走产出兜底校验
    monkeypatch.setattr(llm_client, "chat", lambda messages, username, temperature=0.2: {
        "content": json.dumps(p), "usage": {"prompt_tokens": 30, "completion_tokens": 5}, "mock": True})
    r = client.post("/api/ai/problem-tasks/", json={"requirement": "x"})
    task_id = r.json()["data"]["task_id"]
    data = _wait_task(client, task_id)
    assert data["status"] == "failed"
    assert "language not supported: java" in data["error"]


# ---------- 权限 / 中断 ----------

def test_task_permissions_and_cancel(client):
    task_id = "ai-task-999"
    assert client.get(f"/api/ai/problem-tasks/{task_id}").status_code == 404
    alice = _login("alice")
    # 创建者 alice
    r = alice.post("/api/ai/problem-tasks/", json={"requirement": "x"})
    assert r.status_code == 200
    tid = r.json()["data"]["task_id"]
    # 他人（bob 未建，用 admin 之外的第三个用户？这里 alice 创建，admin 可见；普通他人=需第三人）
    # 简化：admin 可查任意任务
    assert client.get(f"/api/ai/problem-tasks/{tid}").status_code == 200
    # 已完成任务 cancel → 409
    _wait_task(client, tid)
    assert client.put(f"/api/ai/problem-tasks/{tid}/cancel").status_code == 409
    # 越权：注册 bob 查 alice 任务 → 403
    client.post("/api/users/", json={"username": "bob", "password": PASSWORD})
    bob = _login("bob")
    assert bob.get(f"/api/ai/problem-tasks/{tid}").status_code == 403
    assert bob.put(f"/api/ai/problem-tasks/{tid}/cancel").status_code == 403
    # model-config per-user（用户判定 2026-09-07）：普通用户可配置自己的模型/key（非全局管理员）
    assert bob.put("/api/ai/model-config", json={"provider_url": "x", "model": "y", "api_key": "k"}).status_code == 200
    assert bob.get("/api/ai/model-config").json()["data"]["api_key_configured"] is True
    # 隔离：bob 配置不影响 admin（admin 未配置自己的）
    assert client.get("/api/ai/model-config").json()["data"]["api_key_configured"] is False


def test_model_config_minimal_request_ok(client):
    """P1（评审 9.7）：只传必填三字段的最小配置不 500。"""
    r = client.put("/api/ai/model-config", json={
        "provider_url": "https://openrouter.ai/api/v1", "model": "m", "api_key": "k",
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["input_price"] == 0.0 and data["output_price"] == 0.0
    assert data["price_unit"] == 1_000_000
    assert data["api_key_configured"] is True


def test_task_normal_cancel_effective(client, monkeypatch):
    """P1（评审 9.7）：普通任务在运行中被 cancel → 最终 interrupted（不被 completed 覆盖）。"""
    import time as _t

    def _slow_chat(messages, username, temperature=0.2):
        _t.sleep(0.6)
        return {"content": json.dumps(_fake_problem()), "usage": {"prompt_tokens": 10, "completion_tokens": 5}, "mock": True}

    monkeypatch.setattr(llm_client, "chat", _slow_chat)
    r = client.post("/api/ai/problem-tasks/", json={"requirement": "慢速任务"})
    tid = r.json()["data"]["task_id"]
    _t.sleep(0.2)  # 任务已在 running（chat 中）
    r = client.put(f"/api/ai/problem-tasks/{tid}/cancel")
    assert r.status_code == 200
    deadline = _t.monotonic() + 10
    while _t.monotonic() < deadline:
        data = client.get(f"/api/ai/problem-tasks/{tid}").json()["data"]
        if data["status"] in ("interrupted", "completed", "failed"):
            break
        _t.sleep(0.05)
    assert data["status"] == "interrupted"  # 不被 completed 覆盖


# ---------- AI 模型目录与汇率（polish 2026-09-08：自动化真实数据） ----------

def test_ai_catalog_live_parse(client, monkeypatch):
    from app.services import ai_catalog

    # 解析单测：OpenRouter pricing（USD/token）→ USD/1M tokens
    items = ai_catalog._parse_openrouter_payload({"data": [{
        "id": "test/model-a", "name": "Model A", "description": "desc",
        "context_length": 32000, "pricing": {"prompt": "0.0000003", "completion": "0.0000015"},
    }, {
        "id": "test/free-model", "name": "Free", "pricing": {"prompt": 0, "completion": 0},
    }]})
    assert len(items) == 1  # 无计价模型被过滤
    assert items[0]["input_price"] == 0.3 and items[0]["output_price"] == 1.5
    assert items[0]["price_unit"] == 1_000_000

    monkeypatch.setattr(ai_catalog, "_fetch_openrouter_models", lambda: items)
    monkeypatch.setattr(ai_catalog, "_fetch_fx_frankfurter", lambda: 7.14)
    catalog_items, source = ai_catalog.fetch_catalog(force=True)
    # polish 2026-09-08：实时目录合并内置补充（DeepSeek 官方直连模型）
    assert source == "openrouter+builtin"
    by_id = {m["id"]: m for m in catalog_items}
    assert by_id["test/model-a"]["input_price"] == 0.3 and by_id["test/model-a"]["output_price"] == 1.5
    assert by_id["deepseek-v4-flash"]["input_price"] == 0.2083  # 官方直连模型已并入
    fx = ai_catalog.get_fx_rate(force=True)
    assert fx["rate"] == 7.14 and fx["source"] == "frankfurter"
    # API 层
    data = client.get("/api/ai/models").json()["data"]
    assert data["source"] == "openrouter+builtin"
    assert "test/model-a" in {m["id"] for m in data["models"]}
    data = client.get("/api/ai/fx-rate").json()["data"]
    assert data["rate"] == 7.14 and data["source"] == "frankfurter"
    # 保存配置时单价按目录自动写入（不再由用户提供）
    r = client.put("/api/ai/model-config", json={
        "provider_url": "https://openrouter.ai/api/v1", "model": "test/model-a", "api_key": "k",
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["input_price"] == 0.3 and data["output_price"] == 1.5
    assert data["catalog_source"] == "openrouter+builtin"


def test_ai_catalog_builtin_fallback(client, monkeypatch):
    from app.services import ai_catalog

    def _no_net():
        raise RuntimeError("no network")

    monkeypatch.setattr(ai_catalog, "_fetch_openrouter_models", _no_net)
    monkeypatch.setattr(ai_catalog, "_fetch_fx_frankfurter", _no_net)
    items, source = ai_catalog.fetch_catalog(force=True)
    assert source == "builtin"
    assert any(m["id"] == "deepseek-v4-flash" for m in items)
    assert all({"id", "name", "input_price", "output_price", "price_unit"} <= set(m) for m in items)
    fx = ai_catalog.get_fx_rate(force=True)
    assert fx["rate"] == 7.2 and fx["source"] == "builtin"
    # 离线时配置接口仍可用，价格为内置目录价
    r = client.put("/api/ai/model-config", json={
        "provider_url": "https://openrouter.ai/api/v1", "model": "deepseek-v4-flash", "api_key": "k",
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["catalog_source"] == "builtin"
    assert data["input_price"] == 0.2083 and data["output_price"] == 0.625
