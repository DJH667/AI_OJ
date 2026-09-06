"""AI 智能命题接口（Advance；等价路径已在文档说明）：
- PUT /api/ai/model-config     模型配置（登录用户；api_key 存储脱敏、回显不含）
- GET /api/ai/model-config     查询配置（脱敏）
- POST /api/ai/problem-tasks/  创建命题任务（登录；language/problem_id 可选校验）
- GET  /api/ai/problem-tasks/{id}  查询任务（创建者或管理员；含 progress/usage/对拍状态）
- PUT  /api/ai/problem-tasks/{id}/cancel  中断任务（创建者或管理员；终态 409）
任务状态：waiting / running / completed / interrupted / failed；硬核对拍用尽 → completed + review=True。
"""
import threading

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core import messages
from app.core.exceptions import ApiError
from app.core.response import success
from app.services import ai_config, ai_pipeline, ai_tasks, languages, problems

router = APIRouter()


class ModelConfigBody(BaseModel):
    provider_url: str
    model: str
    api_key: str
    input_price: float | None = Field(default=None, ge=0)
    output_price: float | None = Field(default=None, ge=0)
    price_unit: int | None = Field(default=None, ge=1)


@router.put("/api/ai/model-config")
async def update_model_config(body: ModelConfigBody, current: dict = Depends(get_current_user)):
    data = ai_config.update(body.model_dump())
    return success(msg="model config updated", data=data)


@router.get("/api/ai/model-config")
async def get_model_config(current: dict = Depends(get_current_user)):
    return success(msg="success", data=ai_config.to_public())


class TaskBody(BaseModel):
    requirement: str = Field(min_length=1)
    language: str | None = None
    problem_id: str | None = None
    hardcore: bool = False
    retry_limit: int = Field(default=2, ge=0, le=10)


@router.post("/api/ai/problem-tasks/")
async def create_task(body: TaskBody, current: dict = Depends(get_current_user)):
    if body.language is not None and languages.get(body.language) is None:
        raise ApiError(400, f"{messages.LANGUAGE_NOT_FOUND}: {body.language}")
    if body.problem_id is not None and problems.get(body.problem_id) is None:
        raise ApiError(404, messages.PROBLEM_NOT_FOUND)
    task = ai_tasks.create(current, body.requirement, body.language, body.problem_id,
                           body.hardcore, body.retry_limit)
    threading.Thread(target=ai_pipeline.run_task, args=(task["task_id"],), daemon=True).start()
    return success(msg="task created", data={"task_id": task["task_id"], "status": task["status"]})


def _task_or_403(task_id: str, current: dict) -> dict:
    task = ai_tasks.get(task_id)
    if task is None:
        raise ApiError(404, messages.AI_TASK_NOT_FOUND)
    if current["role"] != "admin" and task.get("user_id") != current["user_id"]:
        raise ApiError(403, messages.PERMISSION_DENIED)
    return task


@router.get("/api/ai/problem-tasks/{task_id}")
async def get_task(task_id: str, current: dict = Depends(get_current_user)):
    task = _task_or_403(task_id, current)
    data = {k: task.get(k) for k in (
        "task_id", "status", "progress", "requirement", "language", "problem_id",
        "hardcore", "attempts", "result", "review", "review_note", "usage", "error",
        "created_at", "updated_at",
    )}
    return success(msg="success", data=data)


@router.put("/api/ai/problem-tasks/{task_id}/cancel")
async def cancel_task(task_id: str, current: dict = Depends(get_current_user)):
    task = _task_or_403(task_id, current)
    if task["status"] in (ai_tasks.STATUS_COMPLETED, ai_tasks.STATUS_INTERRUPTED, ai_tasks.STATUS_FAILED):
        raise ApiError(409, messages.AI_TASK_ENDED)
    task["cancel_requested"] = True
    ai_tasks.set_status(task, ai_tasks.STATUS_INTERRUPTED, "用户请求中断")
    return success(msg="task cancelled", data={"task_id": task_id, "status": ai_tasks.STATUS_INTERRUPTED})
