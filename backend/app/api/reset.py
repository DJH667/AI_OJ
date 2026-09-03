"""POST /api/reset/ —— 系统重置（测试支持接口）。

api.md：清空测试产生的用户、题目和提交数据，退出当前登录状态，
并重新创建初始管理员账户。权限"仅管理员（测试环境可不校验）"——
本项目按"测试环境不校验"处理（自动评测会直接调用），
D2 接入服务端 session 后，此处同时清空 sessions 目录实现"退出登录"。
"""
from fastapi import APIRouter

from app.core.response import success
from app.db import store
from app.db.seed import ensure_admin

router = APIRouter()


@router.post("/api/reset/")
async def reset_system():
    store.clear_all()          # 用户/题目/提交/日志/会话全部清空
    ensure_admin()             # 重建初始管理员
    return success(msg="system reset successfully")
