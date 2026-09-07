"""Streamlit 前端统一 API client（前后端分离：经 REST + Session cookie 与 FastAPI 后端交互）。

- httpx.Client 实例置于 st.session_state，Cookie 自动保持登录会话；
- 所有请求解析 {code, msg, data}；业务失败抛 ApiClientError(msg)，供页面友好提示；
- base_url 可在侧栏/环境配置（默认 http://127.0.0.1:8000，后端跑在 WSL 时同机可达）。
"""
import os

import httpx
import streamlit as st

DEFAULT_BASE = os.environ.get("OJ_BACKEND_URL", "http://127.0.0.1:8000")


class ApiClientError(Exception):
    """后端返回非 2xx 或 code != HTTP 状态码时的业务错误。"""


class ApiClient:
    def __init__(self, base_url: str = DEFAULT_BASE):
        self.base = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base, timeout=60.0)

    # ---- 会话 ----
    def login(self, username: str, password: str) -> dict:
        return self._request("POST", "/api/auth/login", json={"username": username, "password": password})

    def logout(self) -> None:
        try:
            self._request("POST", "/api/auth/logout")
        except ApiClientError:
            pass

    def register(self, username: str, password: str) -> dict:
        return self._request("POST", "/api/users/", json={"username": username, "password": password})

    def me(self, user_id: str) -> dict:
        return self._request("GET", f"/api/users/{user_id}")

    def whoami(self, user_id: str) -> dict | None:
        """登录态下取当前用户（未登录返回 None，不做异常提示）。"""
        try:
            return self.me(user_id)
        except ApiClientError:
            return None

    # ---- 通用请求 ----
    def _request(self, method: str, path: str, **kwargs) -> dict:
        resp = self._http.request(method, path, **kwargs)
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code >= 400:
            msg = (body or {}).get("msg") or f"HTTP {resp.status_code}"
            raise ApiClientError(f"{resp.status_code}: {msg}")
        data = (body or {}).get("data")
        return data if data is not None else {}

    # ---- 资源接口（按页面按需扩展）----
    def get(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | None = None) -> dict:
        return self._request("POST", path, json=json or {})

    def put(self, path: str, json: dict | None = None) -> dict:
        return self._request("PUT", path, json=json or {})

    def delete(self, path: str) -> dict:
        return self._request("DELETE", path)


def get_client() -> ApiClient:
    if "api_client" not in st.session_state:
        st.session_state["api_client"] = ApiClient()
    return st.session_state["api_client"]
