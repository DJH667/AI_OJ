"""题目管理服务（官方 Step1）。

字段契约严格遵循 api.md Step1 添加题目：
必填 id/title/description/input_description/output_description/samples/constraints/testcases；
可选 hint/source/tags/time_limit(float 默认 3)/memory_limit(int 默认 128)/author/difficulty。
- 全 JSON 存储：problems/{quote(id)}.json；
- GET 详情返回全部字段，缺失可选字段按"本类型默认值"补齐（str→""、list→[]，
  time_limit→3.0、memory_limit→128，见 api.md"默认字段需返回类型默认值"）；
- AI 私有字段 difficulty_score：仅由 save_internal 写入服务端文件，**不参与任何对外 API**
  （用户指示 2026-09-03，隐藏字段）。
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app import config
from app.core.exceptions import ApiError
from app.core.messages import (
    PROBLEM_ALREADY_EXISTS,
    PROBLEM_ID_MISMATCH,
    PROBLEM_NOT_FOUND,
)
from app.db import store


class Case(BaseModel):
    input: str
    output: str


class ProblemIn(BaseModel):
    """POST/PUT /api/problems/ 请求体（对外契约，不含 difficulty_score 回传）。

    polish 2026-09-07（方案 D）：可选接收 difficulty_score（0–10）作为难度先验提示
    （AI 产出预填），仅用于服务端私有难度计算，**任何响应不回传**。
    """

    id: str
    title: str
    description: str
    input_description: str
    output_description: str
    samples: List[Case]
    constraints: str
    testcases: List[Case]
    # 可选
    hint: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    time_limit: Optional[float] = Field(default=None, gt=0)
    memory_limit: Optional[int] = Field(default=None, gt=0)
    author: Optional[str] = None
    difficulty: Optional[str] = None
    # 私有先验提示（不回传；契约测试已验证响应不含该字段）
    difficulty_score: Optional[float] = Field(default=None, ge=0, le=10)


# GET 详情缺失可选字段的类型默认值
STR_DEFAULTS = {"hint": "", "source": "", "author": "", "difficulty": ""}
NUMERIC_DEFAULTS = {"time_limit": 3.0, "memory_limit": 128}

# ---- difficulty_score 方案 D（polish 2026-09-07，用户拍板）：先验 + 通过率后验加权 ----
# 先验来源优先级：difficulty_prior（存留）> 出题/AI 给出的 difficulty_score > 难度标签映射 > 默认 5.0；
# 后验 = 10 × (1 − 通过率)；α = PRIOR_HALF_LIFE / (PRIOR_HALF_LIFE + 提交数)，提交越多越收敛到后验。
DIFFICULTY_LABEL_PRIOR = {
    "入门": 1.0, "普及-": 2.0, "普及": 3.0, "普及+": 4.0,
    "提高": 5.5, "提高+": 7.0, "省选": 8.5, "NOI": 10.0,
}
DEFAULT_DIFFICULTY_PRIOR = 5.0
PRIOR_HALF_LIFE = 2  # 提交数达到该值时先验权重降至 1/2


def _clamp_score(value: float) -> float:
    return round(min(10.0, max(0.0, float(value))), 2)


def _label_prior(data: dict) -> float:
    label = (data.get("difficulty") or "").strip()
    return DIFFICULTY_LABEL_PRIOR.get(label, DEFAULT_DIFFICULTY_PRIOR)


def difficulty_stats(problem_id: str) -> tuple[int, int]:
    """该题 (总提交数, AC 提交数)。"""
    from app.services import submissions as submission_service

    total = ac = 0
    if config.SUBMISSIONS_DIR.exists():
        for _, rec in store.iter_all(config.SUBMISSIONS_DIR):
            if rec.get("problem_id") != problem_id:
                continue
            total += 1
            if submission_service.is_ac(rec):
                ac += 1
    return total, ac


def refresh_difficulty(problem_id: str) -> None:
    """方案 D：先验 + 通过率后验加权，写回私有键 difficulty_prior/difficulty_score。

    score = α·prior + (1−α)·posterior，其中 posterior = 10 × (1 − 通过率)、
    α = PRIOR_HALF_LIFE / (PRIOR_HALF_LIFE + 总提交数)；无提交时 score = prior。
    幂等；评测完成 / 题目 CRUD / 种子导入后调用。
    """
    data = get(problem_id)
    if data is None:
        return
    prior = data.get("difficulty_prior")
    if prior is None:
        prior = data.get("difficulty_score")
    if prior is None:
        prior = _label_prior(data)
    try:
        prior = _clamp_score(float(prior))
    except (TypeError, ValueError):
        prior = _clamp_score(_label_prior(data))
    total, ac = difficulty_stats(problem_id)
    if total:
        posterior = 10.0 * (1.0 - ac / total)
        alpha = PRIOR_HALF_LIFE / (PRIOR_HALF_LIFE + total)
        score = alpha * prior + (1.0 - alpha) * posterior
    else:
        score = prior
    data["difficulty_prior"] = prior
    data["difficulty_score"] = _clamp_score(score)
    save(problem_id, data)


def _to_storage(problem: ProblemIn) -> dict:
    """存储表示：仅保留提供的字段（None 剔除），id 与内容一致。"""
    data = problem.model_dump(exclude_none=True)
    return data


def get(problem_id: str) -> Optional[dict]:
    return store.load_json(config.PROBLEMS_DIR, problem_id)


def get_all() -> list[dict]:
    return [data for _, data in store.iter_all(config.PROBLEMS_DIR)]


def save(problem_id: str, data: dict) -> None:
    store.save_json(config.PROBLEMS_DIR, problem_id, data)


def create(problem: ProblemIn) -> dict:
    if get(problem.id) is not None:
        raise ApiError(409, PROBLEM_ALREADY_EXISTS)
    save(problem.id, _to_storage(problem))
    # 方案 D：新建即按先验（难度标签/AI 提示）初始化难度分
    refresh_difficulty(problem.id)
    return {"id": problem.id}


def update(problem_id: str, problem: ProblemIn) -> dict:
    if problem.id != problem_id:
        raise ApiError(400, PROBLEM_ID_MISMATCH)
    existing = get(problem_id)
    if existing is None:
        raise ApiError(404, PROBLEM_NOT_FOUND)
    data = _to_storage(problem)
    # 保留服务端私有键（public_cases 日志开关、difficulty_score/difficulty_prior 难度分）——CRUD 覆盖不应丢失
    for private in ("public_cases", "difficulty_score", "difficulty_prior"):
        if private in existing and private not in data:
            data[private] = existing[private]
    if problem.difficulty_score is not None:
        # 新的先验提示覆盖旧存留（refresh 将据此重算）
        data.pop("difficulty_prior", None)
    save(problem_id, data)
    refresh_difficulty(problem_id)
    return {"id": problem_id}


def get_public_cases(problem_id: str) -> bool:
    data = get(problem_id)
    return bool(data.get("public_cases", False)) if data else False


def set_public_cases(problem_id: str, value: bool) -> None:
    data = get(problem_id)
    if data is None:
        raise ApiError(404, PROBLEM_NOT_FOUND)
    data["public_cases"] = bool(value)
    save(problem_id, data)


def to_public(data: dict) -> dict:
    """对外详情视图：全字段 + 缺失可选字段补类型默认值；不含 difficulty_score 等私有键。
    评审 P3（2026-09-04）：内部文件（save_internal/示例题）缺必填键时用 get 兜底，避免 500。"""
    out = {
        "id": data.get("id", ""),
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "input_description": data.get("input_description", ""),
        "output_description": data.get("output_description", ""),
        "samples": data.get("samples", []),
        "constraints": data.get("constraints", ""),
        "testcases": data.get("testcases", []),
    }
    for key, default in STR_DEFAULTS.items():
        out[key] = data.get(key, default)
    for key, default in NUMERIC_DEFAULTS.items():
        out[key] = data.get(key, default)
    out["tags"] = data.get("tags", [])
    return out


def summary(data: dict) -> dict:
    """列表条目：{id, title}（api.md 契约字段，polish 后保留不变）。"""
    return {"id": data["id"], "title": data.get("title", "")}


def list_summaries() -> list[dict]:
    """列表视图（polish 2026-09-07，用户拍板）：契约字段 id/title 原样保留，
    另附展示字段 difficulty/tags/pass_rate。

    pass_rate = 该题 AC 提交数 / 该题总提交数，[0,1] 区间、保留 4 位小数；无提交记 0.0。
    """
    from app.services import submissions as submission_service

    total_by_pid: dict[str, int] = {}
    ac_by_pid: dict[str, int] = {}
    if config.SUBMISSIONS_DIR.exists():
        for _, rec in store.iter_all(config.SUBMISSIONS_DIR):
            pid = rec.get("problem_id")
            if not pid:
                continue
            total_by_pid[pid] = total_by_pid.get(pid, 0) + 1
            if submission_service.is_ac(rec):
                ac_by_pid[pid] = ac_by_pid.get(pid, 0) + 1

    items = []
    for data in get_all():
        pid = str(data["id"])
        total = total_by_pid.get(pid, 0)
        ac = ac_by_pid.get(pid, 0)
        items.append({
            **summary(data),
            "difficulty": data.get("difficulty", ""),
            "tags": data.get("tags", []),
            "pass_rate": round(ac / total, 4) if total else 0.0,
        })
    return items


def delete_cascade(problem_id: str) -> None:
    """删除题目及级联清理（api.md + 助教确认 2026-09-02/09-03）：
    testcases（随题目文件）→ 该题 submissions → 回退相关用户 submit/resolve_count
    → access 审计中该 problem_id 的记录 → 删除题目文件。"""
    from app.services import submissions as submission_service

    if get(problem_id) is None:
        raise ApiError(404, PROBLEM_NOT_FOUND)
    submission_service.delete_all_for_problem(problem_id)
    for key, log in store.iter_all(config.ACCESS_LOGS_DIR):
        if log.get("problem_id") == problem_id:
            store.delete_json(config.ACCESS_LOGS_DIR, key)
    store.delete_json(config.PROBLEMS_DIR, problem_id)


def save_internal(data: dict) -> None:
    """服务端内部写入（示例题导入 / AI 模块使用；可含 difficulty_score 私有键，不校验对外契约）。"""
    problem_id = str(data["id"])
    save(problem_id, data)


def load_sample(name: str) -> dict:
    """从版本库 sample_problems/ 读取示例题 JSON。"""
    path: Path = config.SAMPLE_PROBLEMS_DIR / f"{name}.json"
    import json

    return json.loads(path.read_text(encoding="utf-8"))
