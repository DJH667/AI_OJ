"""AI 模型配置（R2，per-user）：每个用户自选 provider/model/api_key，无需管理员。

- 存 data/ai_configs/{username}.json（reset 不清——用户配置非测试数据）；
- api_key 敏感：本地文件存储（data 已 gitignore）、不进日志/响应（对外仅 api_key_configured）；
- **计价自动化（polish 2026-09-08，用户反馈）**：input_price/output_price/price_unit 不再由
  用户填写，保存配置时按所选模型从 ai_catalog（OpenRouter 真实目录，离线内置表兜底）自动写入；
  fx_rate 在计费/回显时由 ai_catalog.get_fx_rate() 自动获取（Frankfurter/ECB，离线内置参考值兜底）；
  费用 = token/1M × 模型真实单价(USD) × 自动汇率，CNY 展示。
"""
from app import config
from app.db import store
from app.services import ai_catalog

CURRENCY = ai_catalog.CURRENCY
DEFAULT_PRICE_UNIT = ai_catalog.PRICE_UNIT


def _load(username: str) -> dict:
    data = store.load_json(config.AI_CONFIGS_DIR, username)
    return data if data else {}


def save(username: str, cfg: dict) -> None:
    store.ensure_dirs()
    store.save_json(config.AI_CONFIGS_DIR, username, cfg)


def get_raw(username: str) -> dict:
    """完整配置（含 key，仅供服务端请求与内部使用）。"""
    return _load(username)


def is_configured(username: str) -> bool:
    cfg = _load(username)
    return bool(cfg.get("provider_url") and cfg.get("model") and cfg.get("api_key"))


def to_public(username: str) -> dict:
    """对外脱敏视图（不含 api_key；单价/汇率为自动获取的真实数据）。"""
    cfg = _load(username)
    fx = ai_catalog.get_fx_rate()
    return {
        "provider_url": cfg.get("provider_url", ""),
        "model": cfg.get("model", ""),
        "api_key_configured": bool(cfg.get("api_key")),
        "input_price": cfg.get("input_price", 0.0),
        "output_price": cfg.get("output_price", 0.0),
        "price_unit": cfg.get("price_unit", DEFAULT_PRICE_UNIT),
        "catalog_source": cfg.get("catalog_source", ""),
        "fx_rate": fx["rate"],
        "fx_source": fx["source"],
        "currency": CURRENCY,
    }


def update(username: str, body: dict) -> dict:
    """保存该用户配置（PUT /api/ai/model-config）。

    只接收 provider_url/model/api_key；单价按所选模型从目录自动写入
    （目录未知的模型记 0.0 并标 catalog_source=unknown，计费时再按目录兜底）。
    """
    model = str(body["model"]).strip()
    catalog_items, source = ai_catalog.fetch_catalog()
    pricing = next((m for m in catalog_items if m["id"] == model), None)
    # Key 为空且已有配置时保持原 Key，避免前端刷新后用户未重填而误清空
    api_key = body["api_key"]
    if not api_key:
        existing_key = _load(username).get("api_key")
        if existing_key:
            api_key = existing_key
    cfg = {
        "provider_url": str(body["provider_url"]).strip().rstrip("/"),
        "model": model,
        "api_key": api_key,
        "input_price": pricing["input_price"] if pricing else 0.0,
        "output_price": pricing["output_price"] if pricing else 0.0,
        "price_unit": ai_catalog.PRICE_UNIT,
        "catalog_source": source if pricing else "unknown",
        "currency": CURRENCY,
    }
    save(username, cfg)
    return to_public(username)


def estimate_cost(usage: dict, username: str) -> dict:
    """按所选模型真实单价与自动汇率计价，返回 CNY 费用与用量。"""
    cfg = _load(username)
    model = cfg.get("model", "")
    pricing = ai_catalog.find_model(model)
    if pricing:
        inp_price, out_price = pricing["input_price"], pricing["output_price"]
    else:
        inp_price = float(cfg.get("input_price", 0.0))
        out_price = float(cfg.get("output_price", 0.0))
    unit = int(cfg.get("price_unit", DEFAULT_PRICE_UNIT)) or DEFAULT_PRICE_UNIT
    fx = ai_catalog.get_fx_rate()
    inp = usage.get("prompt_tokens", 0)
    out = usage.get("completion_tokens", 0)
    usd = inp / unit * inp_price + out / unit * out_price
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": inp + out,
        "cost": round(usd * fx["rate"], 4),
        "currency": CURRENCY,
        "fx_rate": fx["rate"],
        "fx_source": fx["source"],
    }
