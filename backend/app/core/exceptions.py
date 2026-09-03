"""业务异常与全局异常处理。

约定（api.md）：
- 状态码语义：200 / 400 参数错误 / 401 未登录 / 403 权限不足或被 ban /
  404 资源不存在 / 409 状态冲突 / 429 频率超限 / 500 服务器异常；
- 业务层判定优先级：401 > 403 > 400 > 429 > 409 > 404 > 500
  （即先校验登录、再校验权限、再校验参数……后置位错误才可能命中前置位条件）；
- FastAPI 默认的 422 校验错误需转为 400；
- 所有错误响应统一 {"code": <http>, "msg": ..., "data": null} 且 HTTP 状态码一致；
- 未预期异常由兜底处理器收敛为 JSON 500（评审意见 P1，2026-09-03）。
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("oj")


class ApiError(Exception):
    """业务错误：抛出后由全局处理器转为统一 JSON 响应。"""

    def __init__(self, status_code: int, msg: str, data=None):
        self.status_code = status_code  # 与 HTTP 状态码一致
        self.msg = msg
        self.data = data
        super().__init__(msg)

    def payload(self) -> dict:
        return {"code": self.status_code, "msg": self.msg, "data": self.data}


def _error_payload(status_code: int, msg: str) -> dict:
    return {"code": status_code, "msg": msg, "data": None}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.payload())

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI 默认对参数/请求体校验失败返回 422，项目约定转为 400。
        return JSONResponse(status_code=400, content=_error_payload(400, "invalid request parameters"))

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # 路由不存在(404)等星雀异常同样收敛为统一结构。
        return JSONResponse(status_code=exc.status_code, content=_error_payload(exc.status_code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # 兜底：任何未预期异常统一收敛为 JSON 500，保证 {code,msg,data} 契约不被纯文本破坏；
        # 完整堆栈记入服务端日志，但绝不回显给客户端（防泄露路径/密钥）。
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content=_error_payload(500, "internal server error"))
