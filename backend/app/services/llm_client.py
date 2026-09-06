"""LLM 调用（OpenAI 兼容；OpenRouter /api/v1 亦兼容）+ 本地 mock。

- 真实调用：POST {provider_url}/chat/completions，Bearer api_key；读取 content 与 usage；
- mock：未配置 key/配置时返回固定"题目 JSON"（模拟 usage），用于打通全流程（无 key 演示）；
- 系统要求（R4）：模型返回 usage（prompt/completion tokens），费用由 ai_config.estimate_cost 计算。
"""
import json

import httpx

from app.services import ai_config

MOCK_USAGE = {"prompt_tokens": 1200, "completion_tokens": 350}


class LLMError(Exception):
    """LLM 调用/解析失败（安全消息）。"""


def _mock_content() -> str:
    """本地 mock 产出：一道 A+B 变体题的结构化 JSON（含 samples/testcases/私有字段示意）。

    真实模型在 prompt 约束下返回同构 JSON（见 ai_pipeline 的 system prompt）。
    """
    return json.dumps({
        "id": "AI-MOCK-SUM",
        "title": "Mock Sum Problem",
        "description": "给定两个整数 a 和 b，输出 a+b。",
        "input_description": "一行两个整数。",
        "output_description": "一个整数。",
        "samples": [{"input": "1 2", "output": "3"}],
        "constraints": "|a|,|b| <= 10^9",
        "testcases": [{"input": "1 2", "output": "3"}, {"input": "0 0", "output": "0"}],
        "time_limit": 1.0,
        "memory_limit": 128,
        "difficulty_score": 2.0,
        "language": "python",
        "meta": {
            "std_solution": "a, b = map(int, input().split())\nprint(a + b)",
            "brute_solution": None,
            "generator": None,
            "note": "mock 产出：对拍三代码由真实模型在硬核模式提供",
        },
    })


def chat(messages: list[dict], temperature: float = 0.2) -> dict:
    """调用模型，返回 {"content": str, "usage": {...}, "mock": bool}。"""
    cfg = ai_config.get_raw()
    if not cfg.get("api_key"):
        return {"content": _mock_content(), "usage": dict(MOCK_USAGE), "mock": True}
    url = f"{cfg['provider_url']}/chat/completions"
    payload = {"model": cfg["model"], "messages": messages, "temperature": temperature}
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=120.0)
        resp.raise_for_status()
        body = resp.json()
    except Exception as exc:  # httpx/网络/非 2xx
        raise LLMError("model request failed") from exc
    try:
        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("unexpected model response") from exc
    return {"content": content, "usage": usage, "mock": False}
