"""站点配置（polish 2026-09-09，全量检查 #4）：允许普通用户编辑题目 开关。

- 存 data/site_config.json（系统级配置，reset 不清）；
- 默认 allow_user_edit=True（与 api.md"普通登录用户可 PUT 修改题目"一致）；
- 管理员可经 /api/site-config 调整；关闭后普通用户 PUT /api/problems/{id} 返回 403，
  前端编辑入口同步禁用（仅影响"编辑已有题"，新增题目不受影响）。
"""
from app import config
from app.db import store

CONFIG_KEY = "site-config"

DEFAULTS = {"allow_user_edit": True}


def _load() -> dict:
    data = store.load_json(config.DATA_DIR, CONFIG_KEY)
    merged = dict(DEFAULTS)
    if data:
        merged.update(data)
    return merged


def get() -> dict:
    return _load()


def set_allow_user_edit(value: bool) -> dict:
    store.ensure_dirs()
    cfg = _load()
    cfg["allow_user_edit"] = bool(value)
    store.save_json(config.DATA_DIR, CONFIG_KEY, cfg)
    return cfg
