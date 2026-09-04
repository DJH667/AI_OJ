"""语言接口（官方 Step2）：
- POST /api/languages/  动态注册新语言（登录用户；重名 400）
- GET  /api/languages/  查询支持语言列表（公开）→ {"name": ["python","cpp"]}
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.response import success
from app.services import languages as lang_service

router = APIRouter()


@router.post("/api/languages/")
async def register_language(body: lang_service.LanguageIn, current: dict = Depends(get_current_user)):
    data = lang_service.register(body)
    return success(msg="language registered", data=data)


@router.get("/api/languages/")
async def list_languages():
    return success(msg="success", data={"name": lang_service.all_names()})
