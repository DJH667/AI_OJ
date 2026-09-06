"""AI 模型配置（R2）：provider_url/model/api_key + 计价字段。

- 存 data/ai_config.json（系统配置：reset 不清空）；
- api_key 属敏感信息：本地文件存储（data 目录已 gitignore、不进日志/响应），
  查询/回显一律脱敏（api_key_configured: bool）；
- 计价：input_price/output_price 每 price_unit tokens（OpenRouter 默认按 1M tokens 计价），
  页面须注明计价依据（OpenRouter 模型页）。
"""
from app import config
from app.db import store

CONFIG_KEY = "ai-model-config"

DEFAULT_PRICE_UNIT = 1_000_000
CURRENCY = "USD"


def _load() -> dict:
    data = store.load_json(config.DATA_DIR, CONFIG_KEY)
    return data if data else {}


def save(cfg: dict) -> None:
    store.save_json(config.DATA_DIR, CONFIG_KEY, cfg)


def get_raw() -> dict:
    """完整配置（含 key，仅供服务端请求与内部使用）。"""
    return _load()


def is_configured() -> bool:
    cfg = _load()
    return bool(cfg.get("provider_url") and cfg.get("model") and cfg.get("api_key"))


def to_public() -> dict:
    """对外脱敏视图（不含 api_key）。"""
    cfg = _load()
    return {
        "provider_url": cfg.get("provider_url", ""),
        "model": cfg.get("model", ""),
        "api_key_configured": bool(cfg.get("api_key")),
        "input_price": cfg.get("input_price", 0.0),
        "output_price": cfg.get("output_price", 0.0),
        "price_unit": cfg.get("price_unit", DEFAULT_PRICE_UNIT),
    }


def update(body: dict) -> dict:
    """保存配置（PUT /api/ai/model-config）。body 已含 provider_url/model/api_key/计价字段。"""
    store.ensure_dirs()
    cfg = {
        "provider_url": body["provider_url"].rstrip("/"),
        "model": body["model"],
        "api_key": body["api_key"],
        "input_price": float(body.get("input_price", 0.0)),
        "output_price": float(body.get("output_price", 0.0)),
        "price_unit": int(body.get("price_unit", DEFAULT_PRICE_UNIT)),
    }
    save(cfg)
    return to_public()


def estimate_cost(usage: dict) -> dict:
    """按配置单价计算费用：输入token/单位×输入单价 + 输出token/单位×输出单价。"""
    cfg = _load()
    unit = int(cfg.get("price_unit", DEFAULT_PRICE_UNIT)) or DEFAULT_PRICE_UNIT
    inp = usage.get("prompt_tokens", 0)
    out = usage.get("completion_tokens", 0)
    cost = (inp / unit * float(cfg.get("input_price", 0.0))
            + out / unit * float(cfg.get("output_price", 0.0)))
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": inp + out,
        "cost": round(cost, 6),
        "currency": CURRENCY,
    }
