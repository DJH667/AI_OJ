"""AI 模型目录与汇率（polish 2026-09-08，用户反馈）：单价/汇率自动化，不再暴露给用户手填。

- 模型目录：实时拉取 OpenRouter 公开接口 GET /api/v1/models（无需 key），
  解析 pricing（USD/token）× 1M → USD/1M tokens；失败回退内置常用模型表（source=builtin）；
  内置表同时含 DeepSeek 官方直连模型（deepseek-v4-flash/deepseek-v4-pro，
  2026-09 起 deepseek-chat/deepseek-reasoner 已弃用），
  供 provider_url=https://api.deepseek.com 场景下拉选择与计价；
- 汇率：Frankfurter（ECB，免费无 key）USD→CNY；失败回退内置参考值（source=builtin）；
  2026 年 Frankfurter 域名迁移 api.frankfurter.app → api.frankfurter.dev/v1（旧域 301），
  两域依次尝试；失败/降级走短 TTL 自动重试，不再把一次网络失败缓存 12 小时；
- 内存缓存：目录 1h（失败 5min 重试）、汇率 12h（失败 5min 重试）；
- find_model 只查缓存/内置表（不主动联网），供计费路径使用，避免后台任务卡网络。
"""
import time

import httpx

PRICE_UNIT = 1_000_000  # 计价单位：每百万 tokens
CURRENCY = "CNY"
DEFAULT_FX_RATE = 7.2  # USD→CNY 内置参考值（仅网络不可用时兜底，2026-09 参考）

# 内置常用模型（USD/1M tokens；供离线降级与官方直连模型选择）
# DeepSeek 官方直连价格为官网 CNY 价按兜底汇率 7.2 折算的 USD 估算，
# 离线时与内置汇率 7.2 相乘后恰好还原官网 CNY 价，计价自洽。
BUILTIN_MODELS = [
    {"id": "deepseek-v4-flash", "name": "DeepSeek V4 Flash（官方直连）",
     "description": "DeepSeek 官方 API 快模型（provider_url 填 https://api.deepseek.com，官方 key）",
     "context_length": 131072,
     "input_price": 0.2083, "output_price": 0.625, "price_unit": PRICE_UNIT},
    {"id": "deepseek-v4-pro", "name": "DeepSeek V4 Pro（官方直连）",
     "description": "DeepSeek 官方 API 旗舰模型（provider_url 填 https://api.deepseek.com，官方 key）",
     "context_length": 131072,
     "input_price": 0.625, "output_price": 1.875, "price_unit": PRICE_UNIT},
    {"id": "deepseek-v4-flash-vision-exp", "name": "DeepSeek V4 Flash Vision（实验，官方直连）",
     "description": "DeepSeek 官方视觉实验模型（支持图片输入；provider_url 填 https://api.deepseek.com）",
     "context_length": 131072,
     "input_price": 0.2083, "output_price": 0.625, "price_unit": PRICE_UNIT},
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
CATALOG_FAIL_RETRY = 300  # 拉取失败/降级时 5 分钟后重试（不再把失败缓存 1h）

_fx_cache: dict | None = None
_fx_fetched_at = 0.0
FX_TTL = 12 * 3600
FX_FAIL_RETRY = 300  # 拉取失败/降级时 5 分钟后重试（不再把失败缓存 12h）


def _merge_builtin(items: list[dict]) -> tuple[list[dict], bool]:
    """把内置表（含 DeepSeek 官方直连模型）并入实时目录，返回 (合并结果, 是否有补充)。"""
    merged = {m["id"]: m for m in items}
    added = False
    for m in BUILTIN_MODELS:
        if m["id"] not in merged:
            merged[m["id"]] = dict(m)
            added = True
    return list(merged.values()), added


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
    """模型目录 + 来源（openrouter / openrouter+builtin / builtin）；TTL 内走缓存，失败走短 TTL 重试。"""
    global _catalog_cache, _catalog_source, _catalog_fetched_at
    now = time.time()
    if not force and _catalog_cache is not None:
        ttl = CATALOG_TTL if _catalog_source.startswith("openrouter") else CATALOG_FAIL_RETRY
        if now - _catalog_fetched_at < ttl:
            return _catalog_cache, _catalog_source
    try:
        items = _fetch_openrouter_models()
        if items:
            items, added = _merge_builtin(items)
            items.sort(key=lambda m: (m["input_price"] + m["output_price"], m["id"]))
            _catalog_cache = items
            _catalog_source = "openrouter+builtin" if added else "openrouter"
            _catalog_fetched_at = now
            return items, _catalog_source
    except Exception:
        pass
    _catalog_cache = [dict(m) for m in BUILTIN_MODELS]
    _catalog_source, _catalog_fetched_at = "builtin", now
    return _catalog_cache, _catalog_source


def find_model(model_id: str) -> dict | None:
    """按 id 查缓存目录 + 内置表（不主动联网，供计费路径使用）。"""
    items = _catalog_cache if _catalog_cache is not None else []
    for m in list(items) + [dict(m) for m in BUILTIN_MODELS]:
        if m.get("id") == model_id:
            return m
    return None


def _fetch_fx_frankfurter() -> float:
    """USD→CNY：Frankfurter 新域（/v1/）优先，旧域兜底（2026 迁移，旧域 301）。"""
    last_error: Exception | None = None
    for url in ("https://api.frankfurter.dev/v1/latest", "https://api.frankfurter.app/latest"):
        try:
            resp = httpx.get(url, params={"from": "USD", "to": "CNY"}, timeout=10.0)
            resp.raise_for_status()
            rate = float(resp.json()["rates"]["CNY"])
            if rate > 0:
                return rate
        except Exception as exc:  # noqa: BLE001 双域依次尝试
            last_error = exc
    raise RuntimeError("fx fetch failed") from last_error


def get_fx_rate(force: bool = False) -> dict:
    """USD→CNY 汇率 + 来源（frankfurter/builtin）；成功缓存 12h，失败降级 5min 后自动重试。"""
    global _fx_cache, _fx_fetched_at
    now = time.time()
    if not force and _fx_cache is not None:
        ttl = FX_TTL if _fx_cache.get("source") == "frankfurter" else FX_FAIL_RETRY
        if now - _fx_fetched_at < ttl:
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
