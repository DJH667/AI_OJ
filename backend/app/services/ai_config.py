"""AI 模型配置（R2，per-user）：每个用户自选 provider/model/api_key/计价，无需管理员。

- 存 data/ai_configs/{username}.json（reset 不清——用户配置非测试数据）；
- api_key 敏感：本地文件存储（data 已 gitignore）、不进日志/响应（对外仅 api_key_configured）；
- **计价币种 CNY**（用户判定 2026-09-07）：input_price/output_price 为所选模型在 OpenRouter
  公布的美元单价（USD / price_unit tokens）；费用按 fx_rate 折算为 CNY 展示。
  fx_rate 默认 7.2（2026-09 参考值），用户可在配置页**按当日汇率更新**（以中国人民银行公布的
  人民币汇率中间价为准），本项目不做外部行情自动拉取（验收环境网络不保证）。
"""
from app import config
from app.db import store

DEFAULT_PRICE_UNIT = 1_000_000
CURRENCY = "CNY"
DEFAULT_FX_RATE = 7.2  # USD→CNY，参考中国人民银行中间价（2026-09）；可在 model-config 更新


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
    """对外脱敏视图（不含 api_key）。"""
    cfg = _load(username)
    return {
        "provider_url": cfg.get("provider_url", ""),
        "model": cfg.get("model", ""),
        "api_key_configured": bool(cfg.get("api_key")),
        "input_price": cfg.get("input_price", 0.0),
        "output_price": cfg.get("output_price", 0.0),
        "price_unit": cfg.get("price_unit", DEFAULT_PRICE_UNIT),
        "fx_rate": cfg.get("fx_rate", DEFAULT_FX_RATE),
        "currency": CURRENCY,
    }


def update(username: str, body: dict) -> dict:
    """保存该用户配置（PUT /api/ai/model-config）。最小请求只需 provider_url/model/api_key。"""
    cfg = {
        "provider_url": body["provider_url"].rstrip("/"),
        "model": body["model"],
        "api_key": body["api_key"],
        "input_price": float(body.get("input_price") or 0.0),   # USD / price_unit（OpenRouter 定价）
        "output_price": float(body.get("output_price") or 0.0),
        "price_unit": int(body.get("price_unit") or DEFAULT_PRICE_UNIT),
        "fx_rate": float(body.get("fx_rate") or DEFAULT_FX_RATE),
        "currency": CURRENCY,
    }
    save(username, cfg)
    return to_public(username)


def estimate_cost(usage: dict, username: str) -> dict:
    """按该用户配置计价，返回 CNY 费用（USD 价 × fx_rate 折算）与用量。"""
    cfg = _load(username)
    unit = int(cfg.get("price_unit", DEFAULT_PRICE_UNIT)) or DEFAULT_PRICE_UNIT
    fx = float(cfg.get("fx_rate", DEFAULT_FX_RATE))
    inp = usage.get("prompt_tokens", 0)
    out = usage.get("completion_tokens", 0)
    usd = (inp / unit * float(cfg.get("input_price", 0.0))
           + out / unit * float(cfg.get("output_price", 0.0)))
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": inp + out,
        "cost": round(usd * fx, 4),
        "currency": CURRENCY,
        "fx_rate": fx,
    }
