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
async def list_languages(current: dict = Depends(get_current_user)):
    # 权限回填（Step4 页面）：未登录用户不得对任何资源增删查改 → Step1–3 查接口亦需登录
    return success(msg="success", data={"name": lang_service.all_names()})
