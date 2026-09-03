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
from app.api import reset as reset_api
from app.core.exceptions import register_exception_handlers
from app.db import store
from app.db.seed import ensure_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：建数据目录 + 创建初始管理员（幂等）
    store.ensure_dirs()
    ensure_admin()
    yield


def create_app() -> FastAPI:
    application = FastAPI(title="OJ Backend", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(application)
    application.include_router(reset_api.router)
    return application


app = create_app()
