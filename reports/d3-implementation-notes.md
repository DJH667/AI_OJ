# D3（9.5 提前推进）实现说明与代码导读 —— Step1 题目管理 + Step2 评测主体

> 消化材料。需求基准见 PROJECT_REQUIREMENTS.md §5 Step1/Step2 与 §4。
> ⚠ **环境变化（重要）**：评测需真实执行 python3/g++，自 D3 起**开发/测试主环境迁移到 WSL Linux venv**
> （`wsl: ~/oj-venv`，仅装后端+测试依赖）；Windows `.venv` 保留（含 streamlit，供 D6 前端）。

## 1. 本次交付

| 模块 | 状态 |
|---|---|
| Step1 题目管理：Problem 模型 + CRUD 五接口（鉴权、409/400/404） | ✅ |
| Step1 详情默认字段补齐（str→""、list→[]、time_limit→3.0、memory_limit→128） | ✅ |
| Step1 删除级联 + **用户统计回退**（助教确认 2026-09-03） | ✅ |
| difficulty_score 隐藏字段（不进 API，仅服务端文件） | ✅（已测） |
| 示例题 2 道（backend/sample_problems/，含边界测例；maxn 带 difficulty_score） | ✅ |
| Step2 语言注册：内置 python/cpp + POST/GET /api/languages/（重名 400） | ✅ |
| Step2 评测：编译(C++)/运行/输出归一比对/AC·WA·RE·CE·TLE/score=通过×10 | ✅ |
| 异步评测（asyncio.create_task + to_thread）、429 单人单题、404 题/语言 | ✅ |
| submit_count（按提交）+ resolve_count（一题一次 AC）统计 | ✅ |
| pytest **40/40**（Linux WSL）+ WSL uvicorn 启动冒烟 | ✅ |

> D4 续作：内存监控（psutil → MLE 与真实 memory 值）、Step3（提交列表/详情/rejudge）。

## 2. 文件与职责（新增）

```
backend/app/services/
├── problems.py     # ProblemIn 模型、CRUD、to_public 默认补齐、delete_cascade（级联+回退）
├── languages.py    # 内置 python/cpp、注册、ensure_builtin_languages（启动/reset 重建）
├── submissions.py  # 提交记录数据层：自增 id、pending 创建、单人单题 429 计数、is_ac、按题删除+统计回退
└── judge.py        # 评测执行器：编译/逐测例运行/归一比对/状态机/score-counts/resolve 更新
backend/app/api/
├── problems.py     # 5 个题目接口（DELETE 仅管理员）
├── languages.py    # POST/GET 均需登录（权限回填：未登录不得查改任何资源；评审 2026-09-04 修正）
└── submissions.py  # POST 提交（429>404 顺序、异步评测调度）
backend/sample_problems/{aplusb,maxn}.json   # 示例题（版本库内，不自动导入）
backend/tests/test_d3_problems.py / test_d3_judge.py
```

## 3. 关键实现点

1. **评测在 Linux**：内置语言命令为 `python3 {src}` / `g++ {src} -o {exe}`；服务/测试跑在 WSL venv
   （`~/oj-venv`），subprocess 才能找到命令；error_info 不泄露临时目录（`oj_judge_*` 用完即删）。
2. **异步评测**：`POST` 里 `asyncio.create_task(asyncio.to_thread(judge.judge_submission, sid))`——API 立即返回 pending；
   评测同步逻辑在线程池执行（单用户串行足够）。⚠ 测试不能"POST 后再手动同步 judge 同一记录"（会与后台线程竞态写文件），须轮询等待完成。
3. **状态机**：submission 状态 pending/success/error（框架错如题目缺失→error+error_info 安全文案）；
   测例级 AC/WA/RE/CE/TLE（D4 补 MLE）；CE 不跑测例、score=0、counts=总测例×10；
   TLE=communicate 超时即 kill；RE=返回码非 0；非 AC~CE 归 UNK（OSError 等）。
4. **输出比对**：每行 `rstrip()`、去末尾空行、末尾换行忽略（api.md）；`print(999)` 全错用例验证 WA。
5. **计分与统计**：score=通过测例×10、counts=总测例×10；提交即 submit_count+1（POST）；
   某题首次全 AC（status=success 且 score==counts>0）→ resolve_count+1（judge 完成后）。
6. **429（单人单题）**：窗口 60s，同一 user_id+problem_id 的提交记录数 ≥3 → 第 4 次 429；
   判定先于 404（异常顺序 429>404）；换题不触发。
7. **删除级联+统计回退**（problems.delete_cascade）：删该题 submissions 时聚合每用户
   {提交数, 是否有 AC} → submit_count 相减、resolve_count AC 过减 1（均 max(0,·)）；
   access 审计中该 problem_id 记录一并清理。
8. **详情默认字段**：POST/PUT 未提供的可选字段，GET 详情补类型默认值
   （str→""、list→[]、time_limit→3.0、memory_limit→128，api.md"默认字段需返回类型默认值"）。
9. **difficulty_score 隐藏**：CRUD 请求模型不含该字段（pydantic 默认忽略多余键）；GET/列表不回传；
   仅 `save_internal`（示例题导入/AI 侧）可写入题目文件（决策 dec-7b47335beaa64320 + 用户指示）。
10. **示例题**在版本库 `backend/sample_problems/`，不自动导入（避免与评测建题 id 冲突）；
    联调时用 problems.load_sample 或手动导入。

## 4. 自测（已执行，Linux WSL）

```bash
wsl ~/oj-venv/bin/python -m pytest tests -q    # 40 passed（D1 5 + D2 15 + D3 problems 7 + judge 13）
# WSL uvicorn 启动冒烟：reset 未登录 401、未知路径 404 均正确
```

## 5. 遗留 / D4 预告

- psutil 内存监控 → MLE 与测例真实 memory 值（现 memory=0 占位）；详情 time 精确化。
- Step3：GET /api/submissions/（列表筛选/可见性/摘要裁剪）、GET …/{id}、PUT …/rejudge。
- 真实 HTTP 端到端冒烟（uvicorn+curl 提交后轮询）放到 Step3 查询接口就绪后做。
- 评测任务已加**全局串行锁**（api/submissions.py `JUDGE_LOCK`，评审 P1 2026-09-04），统计读-改-写安全；reset 由评测脚本在提交前调用，与评测无并发窗口。

## 6. 评审意见处理（2026-09-04，comments/2026-09-04-review-b51ba75.md）

| 意见 | 处理 |
|---|---|
| reset Q1（自动评测先登录 admin） | ✅ 已确认：保持管理员鉴权 + `RESET_REQUIRE_ADMIN` 开关，无需调整（ta-qa-pending Q1 回填） |
| P1 并发竞态（resolve/submit 读改写非原子） | ✅ `api/submissions.py` 加全局 `asyncio.Lock`（`_judge_serial`），评测任务排队串行 |
| P2 `GET /api/languages/` 顺序 | ✅ `all_names` 按内置顺序返回 `["python","cpp"]`（与 api.md 示例一致） |
| P2 `GET /api/languages/` 未鉴权 | ✅ 补 `Depends(get_current_user)`（权限回填：未登录不得查改任何资源） |
| P2 CE 的 submission 状态归属 | ✅ CE → status=error（用户判定 2026-09-05：编译失败即未通过评测；compile_info 保留、score/counts=0，judge 与测试已更新） |
| P3 `_normalize` 死代码 | ✅ 修复（`while lines and lines[-1] == ""`） |
| P3 编译绝对路径泄露 /tmp | ✅ 编译与运行 `cwd=临时目录` + 相对路径 `./main.ext`，g++ 报错不再带临时目录前缀 |
| P3 `to_public` 缺必填键 500 / `validate_raw` 死代码 | ✅ `to_public` 全 `get` 兜底；`validate_raw` 删除 |
