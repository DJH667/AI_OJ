"""FastAPI 应用入口。

启动：在 backend/ 目录下执行
    ../.venv/Scripts/python.exe -m uvicorn main:app --port 8000   (Windows)
    ../.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000  (WSL/Linux)

前后端分离（需求文档 §1.1）：本应用仅提供 REST API；
前端 Streamlit 独立进程经 HTTP 调用（端口 8501）。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import config  # noqa: F401  确保配置模块可导入（供交互式调试）
from app.api import auth as auth_api
from app.api import languages as languages_api
from app.api import logs as logs_api
from app.api import problems as problems_api
from app.api import reset as reset_api
from app.api import submissions as submissions_api
from app.api import users as users_api
from app.core.exceptions import register_exception_handlers
from app.db import store
from app.db.seed import ensure_admin
from app.services import languages as lang_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：建数据目录 + 初始管理员 + 内置语言（均幂等）
    store.ensure_dirs()
    ensure_admin()
    lang_service.ensure_builtin_languages()
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="OJ Backend", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(application)
    application.include_router(reset_api.router)
    application.include_router(auth_api.router)
    application.include_router(users_api.router)
    application.include_router(problems_api.router)
    application.include_router(languages_api.router)
    application.include_router(submissions_api.router)
    application.include_router(logs_api.router)
    return application


app = create_app()
