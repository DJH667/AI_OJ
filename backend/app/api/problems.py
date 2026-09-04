"""题目管理接口（官方 Step1）：
- GET    /api/problems/           题目列表 {id,title}（登录）
- POST   /api/problems/           新增（登录；409 id 已存在）
- PUT    /api/problems/{id}       编辑（登录；body id 须与路径一致）
- DELETE /api/problems/{id}       删除（仅管理员；级联清理 + 统计回退）
- GET    /api/problems/{id}       详情（登录；全字段 + 类型默认值）
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_admin
from app.core.response import success
from app.services import problems as problem_service

router = APIRouter()


@router.get("/api/problems/")
async def list_problems(current: dict = Depends(get_current_user)):
    items = [problem_service.summary(data) for data in problem_service.get_all()]
    return success(msg="success", data=items)


@router.post("/api/problems/")
async def add_problem(problem: problem_service.ProblemIn, current: dict = Depends(get_current_user)):
    data = problem_service.create(problem)
    return success(msg="add success", data=data)


@router.put("/api/problems/{problem_id}")
async def update_problem(problem_id: str, problem: problem_service.ProblemIn, current: dict = Depends(get_current_user)):
    data = problem_service.update(problem_id, problem)
    return success(msg="update success", data=data)


@router.delete("/api/problems/{problem_id}")
async def delete_problem(problem_id: str, admin: dict = Depends(require_admin)):
    problem_service.delete_cascade(problem_id)
    return success(msg="delete success", data={"id": problem_id})


@router.get("/api/problems/{problem_id}")
async def get_problem(problem_id: str, current: dict = Depends(get_current_user)):
    data = problem_service.get(problem_id)
    if data is None:
        from app.core.exceptions import ApiError
        from app.core.messages import PROBLEM_NOT_FOUND

        raise ApiError(404, PROBLEM_NOT_FOUND)
    return success(msg="success", data=problem_service.to_public(data))
