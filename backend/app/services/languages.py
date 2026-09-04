"""语言注册表服务（官方 Step2）。

- 内置 python/cpp，命令为 Linux 语义（python3 / g++，评测在 Linux 环境执行）；
- 动态注册语言持久化到 data/languages/{name}.json（POST /api/languages/，登录用户）；
- reset 重置回内置集（用户指示 2026-09-03：注册新语言的接口能力始终保留）。
命令模板中 {src}/{exe} 需替换为路径（api.md 强调：./test.cpp 是路径、test.cpp 不是）。
"""
from pydantic import BaseModel, Field

from app import config
from app.core.exceptions import ApiError
from app.core.messages import LANGUAGE_ALREADY_EXISTS
from app.db import store

BUILTIN_LANGUAGES = [
    {
        "name": "python",
        "file_ext": ".py",
        "run_cmd": "python3 {src}",
    },
    {
        "name": "cpp",
        "file_ext": ".cpp",
        "compile_cmd": "g++ {src} -o {exe}",
        "run_cmd": "{exe}",
    },
]


class LanguageIn(BaseModel):
    name: str
    file_ext: str
    compile_cmd: str | None = None
    run_cmd: str
    time_limit: float | None = Field(default=None, gt=0)
    memory_limit: int | None = Field(default=None, gt=0)


def ensure_builtin_languages() -> None:
    """幂等：补齐内置语言（启动 / reset 后调用）。"""
    store.ensure_dirs()
    for lang in BUILTIN_LANGUAGES:
        if store.load_json(config.LANGUAGES_DIR, lang["name"]) is None:
            store.save_json(config.LANGUAGES_DIR, lang["name"], lang)


def get(name: str) -> dict | None:
    return store.load_json(config.LANGUAGES_DIR, name)


def all_names() -> list[str]:
    return sorted(store.list_keys(config.LANGUAGES_DIR))


def register(lang: LanguageIn) -> dict:
    data = lang.model_dump(exclude_none=True)
    if get(lang.name) is not None:
        raise ApiError(400, LANGUAGE_ALREADY_EXISTS)
    store.save_json(config.LANGUAGES_DIR, lang.name, data)
    return {"name": lang.name}
