"""AI 模型目录与汇率（polish 2026-09-08，用户反馈）：单价/汇率自动化，不再暴露给用户手填。

- 模型目录：实时拉取 OpenRouter 公开接口 GET /api/v1/models（无需 key），
  解析 pricing（USD/token）× 1M → USD/1M tokens；失败回退内置常用模型表（source=builtin）；
- 汇率：Frankfurter（ECB，免费无 key）USD→CNY；失败回退内置参考值（source=builtin）；
- 内存缓存：目录 1h、汇率 12h；验收环境网络不保证，两条链路均有降级；
- find_model 只查缓存（不主动联网），供计费路径使用，避免后台任务卡网络。
"""
import time

import httpx

PRICE_UNIT = 1_000_000  # 计价单位：每百万 tokens
CURRENCY = "CNY"
DEFAULT_FX_RATE = 7.2  # USD→CNY 内置参考值（仅网络不可用时兜底，2026-09 参考）

# 内置常用模型（OpenRouter 公开定价，USD/1M tokens；供离线降级）
BUILTIN_MODELS = [
    {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat (V3)",
     "description": "DeepSeek-V3 对话模型", "context_length": 65536,
     "input_price": 0.27, "output_price": 1.10, "price_unit": PRICE_UNIT},
    {"id": "openai/gpt-4o-mini", "name": "GPT-4o mini",
     "description": "OpenAI 轻量多模态模型", "context_length": 128000,
     "input_price": 0.15, "output_price": 0.60, "price_unit": PRICE_UNIT},
    {"id": "openai/gpt-4o", "name": "GPT-4o",
     "description": "OpenAI 旗舰多模态模型", "context_length": 128000,
     "input_price": 2.50, "output_price": 10.00, "price_unit": PRICE_UNIT},
    {"id": "anthropic/claude-3.5-haiku", "name": "Claude 3.5 Haiku",
     "description": "Anthropic 快速轻量模型", "context_length": 200000,
     "input_price": 0.80, "output_price": 4.00, "price_unit": PRICE_UNIT},
]

_catalog_cache: list[dict] | None = None
_catalog_source = "builtin"
_catalog_fetched_at = 0.0
CATALOG_TTL = 3600

_fx_cache: dict | None = None
_fx_fetched_at = 0.0
FX_TTL = 12 * 3600


def _parse_openrouter_payload(payload: dict) -> list[dict]:
    """解析 OpenRouter /models 响应（pricing: USD/token → USD/1M tokens）。"""
    items: list[dict] = []
    for m in payload.get("data", []):
        pricing = m.get("pricing") or {}
        try:
            inp = float(pricing.get("prompt") or 0) * PRICE_UNIT
            out = float(pricing.get("completion") or 0) * PRICE_UNIT
        except (TypeError, ValueError):
            continue
        if inp <= 0 and out <= 0:
            continue  # 过滤无明确计价的模型
        try:
            ctx = int(m.get("context_length") or 0)
        except (TypeError, ValueError):
            ctx = 0
        items.append({
            "id": str(m.get("id", "")),
            "name": str(m.get("name") or m.get("id", "")),
            "description": str(m.get("description") or "")[:200],
            "context_length": ctx,
            "input_price": round(inp, 4),
            "output_price": round(out, 4),
            "price_unit": PRICE_UNIT,
        })
    return items


def _fetch_openrouter_models() -> list[dict]:
    """拉取并解析 OpenRouter 模型目录。"""
    resp = httpx.get("https://openrouter.ai/api/v1/models", timeout=10.0)
    resp.raise_for_status()
    return _parse_openrouter_payload(resp.json())


def fetch_catalog(force: bool = False) -> tuple[list[dict], str]:
    """模型目录 + 来源（openrouter/builtin）；TTL 内走缓存。"""
    global _catalog_cache, _catalog_source, _catalog_fetched_at
    now = time.time()
    if not force and _catalog_cache is not None and now - _catalog_fetched_at < CATALOG_TTL:
        return _catalog_cache, _catalog_source
    try:
        items = _fetch_openrouter_models()
        if items:
            items.sort(key=lambda m: (m["input_price"] + m["output_price"], m["id"]))
            _catalog_cache, _catalog_source, _catalog_fetched_at = items, "openrouter", now
            return items, "openrouter"
    except Exception:
        pass
    _catalog_cache = [dict(m) for m in BUILTIN_MODELS]
    _catalog_source, _catalog_fetched_at = "builtin", now
    return _catalog_cache, _catalog_source


def find_model(model_id: str) -> dict | None:
    """按 id 查缓存目录（不主动联网，供计费路径使用）。"""
    items = _catalog_cache if _catalog_cache is not None else [dict(m) for m in BUILTIN_MODELS]
    for m in items:
        if m.get("id") == model_id:
            return m
    return None


def _fetch_fx_frankfurter() -> float:
    resp = httpx.get("https://api.frankfurter.app/latest",
                     params={"from": "USD", "to": "CNY"}, timeout=10.0)
    resp.raise_for_status()
    rate = float(resp.json()["rates"]["CNY"])
    if rate <= 0:
        raise ValueError("invalid fx rate")
    return rate


def get_fx_rate(force: bool = False) -> dict:
    """USD→CNY 汇率 + 来源（frankfurter/builtin）；TTL 内走缓存。"""
    global _fx_cache, _fx_fetched_at
    now = time.time()
    if not force and _fx_cache is not None and now - _fx_fetched_at < FX_TTL:
        return dict(_fx_cache)
    try:
        rate = _fetch_fx_frankfurter()
        _fx_cache = {
            "rate": round(rate, 4),
            "source": "frankfurter",
            "date": time.strftime("%Y-%m-%d", time.localtime()),
        }
    except Exception:
        _fx_cache = {"rate": DEFAULT_FX_RATE, "source": "builtin", "date": ""}
    _fx_fetched_at = now
    return dict(_fx_cache)
