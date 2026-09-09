"""LLM 调用（OpenAI 兼容；OpenRouter / DeepSeek 官方均兼容）+ 本地 mock。

- 真实调用：优先流式 POST {provider_url}/chat/completions（stream + stream_options.include_usage），
  按 chunk 估算已生成 token 并回调 on_progress；结束优先取服务端 usage，缺失时用估算兜底；
  流式失败（如个别兼容层不支持 stream_options）回退非流式调用；
- mock：未配置 key 时返回固定"题目 JSON"（模拟 usage），用于打通全流程（无 key 演示）；
- 系统要求（R4）：模型返回 usage（prompt/completion tokens），费用由 ai_config.estimate_cost 计算。
"""
import json
import time

import httpx

from app.services import ai_config

MOCK_USAGE = {"prompt_tokens": 1200, "completion_tokens": 350}


class LLMError(Exception):
    """LLM 调用/解析失败（安全消息）。"""


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数：CJK 字符约 1 token/字，其它字符约 0.25 token/字符。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return int(cjk + other / 4) or 1


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


def _chat_stream(cfg: dict, messages: list[dict], payload: dict, on_progress) -> dict:
    provider_url = cfg.get("provider_url")
    url = f"{provider_url}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    prompt_est = _estimate_tokens(json.dumps(messages, ensure_ascii=False))
    content_parts: list[str] = []
    usage = None
    last_emit = 0.0
    with httpx.stream("POST", url, json=payload, headers=headers, timeout=180.0) as resp:
        if resp.status_code >= 400:
            resp.read()
            raise LLMError(f"model request failed: HTTP {resp.status_code}")
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("data: "):
                data = line[6:].strip()
            elif line.strip() == "data:":
                data = ""
            else:
                continue
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or []
            delta = choices[0].get("delta", {}) if choices else {}
            piece = delta.get("content") or delta.get("reasoning_content") or ""
            if piece:
                content_parts.append(piece)
            if chunk.get("usage"):
                usage = chunk.get("usage")
            if on_progress is not None:
                now = time.monotonic()
                if now - last_emit >= 1.0:
                    last_emit = now
                    on_progress({
                        "prompt_tokens": prompt_est,
                        "completion_tokens": _estimate_tokens("".join(content_parts)),
                    })
    content = "".join(content_parts)
    if not usage:
        usage = {"prompt_tokens": prompt_est, "completion_tokens": _estimate_tokens(content)}
    return {"content": content, "usage": usage}


def _chat_once(cfg: dict, messages: list[dict], payload: dict) -> dict:
    provider_url = cfg.get("provider_url")
    url = f"{provider_url}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['api_key']}"}
    resp = httpx.post(url, json=payload, headers=headers, timeout=120.0)
    resp.raise_for_status()
    body = resp.json()
    try:
        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("unexpected model response") from exc
    return {"content": content, "usage": usage}


def chat(messages: list[dict], username: str, temperature: float = 0.2, on_progress=None) -> dict:
    """调用该用户配置的模型，返回 {"content", "usage", "mock"}；未配置 key 走本地 mock。

    on_progress(est_usage) 在流式生成期间每约 1 秒回调一次，供任务层实时落盘估算 token。
    """
    cfg = ai_config.get_raw(username)
    if not cfg.get("api_key"):
        return {"content": _mock_content(), "usage": dict(MOCK_USAGE), "mock": True}
    # P3 容错（评审 9.7）：半截配置（缺 url/model）转 LLMError 而非 KeyError
    if not cfg.get("provider_url") or not cfg.get("model"):
        raise LLMError("model config incomplete: provider_url and model required")
    payload = {"model": cfg.get("model"), "messages": messages, "temperature": temperature}
    try:
        stream_payload = {
            **payload,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        return {**_chat_stream(cfg, messages, stream_payload, on_progress), "mock": False}
    except LLMError as stream_exc:
        # 个别兼容层可能不支持 stream_options：回退非流式，失败则抛流式错误
        try:
            return {**_chat_once(cfg, messages, payload), "mock": False}
        except Exception:
            raise stream_exc
    except Exception as exc:  # httpx/网络错误
        raise LLMError("model request failed") from exc
