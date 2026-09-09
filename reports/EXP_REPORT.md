# 实验二技术报告 · 在线评测系统（OJ）

> 实验要求来源：https://dbg-course.github.io/python-docs/oj/ （程序设计训练 · Python 课程，2026 年秋季，总分 50 = 功能验收 40 + 代码规范 5 + 实验报告 5）
> 项目：`大作业-2/`（FastAPI 后端 + Streamlit 前端，人机协同开发）
> 本报告独立成文，可直接阅读；系统整体由 FastAPI 后端（REST API）与 Streamlit 前端组成，运行数据以 JSON 存于 `backend/data/`。文末附有待人工核对/补齐项清单。

---

## 一、项目概述

本实验的目标是构建一个**前后端分离的小型在线评测系统（OJ）**：后端只提供 REST API，前端通过 HTTP 调用后端完成全部业务；在此之上实现一个**进阶模块——大模型（LLM）智能命题**，使系统能根据命题需求自动生成题目与测试数据并衔接题目管理流程。

- 代码规模约 **2000 行级（实际 .py 合计约 5244 行）**，属"较大项目"体验，因此全程采用 **人机协同（Vibe Coding）** 开发，并配以严格的进度、评审与问答管理。
- 功能验收按官方 Step1–6 完成基础模块（30 分）与 AI 智能命题进阶模块（10 分）；代码规范与实验报告各 5 分。
- 项目结构：`backend/`（FastAPI，端口 8000）、`frontend/`（Streamlit，端口 8501）、`scripts/`（启动/冒烟）、`reports/`（面向用户的文档），运行期数据写入 `backend/data/`（JSON，已 gitignore）。

---

## 二、系统功能与设计（2 分）

### 2.1 系统总体架构

前后端分离，两个独立进程启动，中间以「REST API + JSON 响应 + 会话 Cookie」为唯一契约：

```
┌──────────────────────────────────────────────────────────┐
│  frontend/  Streamlit（进程 A，端口 8501）                │
│  app.py + api_client.py                                  │
│  · 不直连数据，一切操作经 HTTP 调后端 /api/*                │
│  · 登录态 = 后端会话 Cookie（不在页面硬编码用户身份）        │
└──────────────────────────────┬───────────────────────────┘
                               │  REST API /api/*
                               │  统一响应 {code, msg, data}
                               └───────────────────────────▼
┌──────────────────────────────────────────────────────────┐
│  backend/   FastAPI（进程 B，端口 8000）                  │
│  app/                                                    │
│    core/     统一响应、异常处理、bcrypt 安全、消息契约表    │
│    db/       全 JSON 存储层、初始管理员/示例题种子          │
│    api/      REST 路由（问题/用户/提交/日志/AI/申请/通知…） │
│    services/ 业务层（账号、会话、评测、日志、AI 流水线…）    │
│  main.py     FastAPI 入口（lifespan 建目录+种子）          │
└──────────────────────────────┬───────────────────────────┘
                               │  JSON 文件
                               ▼
        backend/data/  problems/ users/ submissions/ languages/
                      logs/(access/ role_changes/) sessions/ ai_tasks/
                      ai_configs/ applications/ notifications/ site_config.json
```

- **通信契约**：基础模块严格遵循 api.md——仅 REST API + `{code, msg, data}` + HTTP 状态码，**未新增 api.md 契约变体**；在此基础上按产品需求附加的扩展接口（题目修改/删除申请、通知中心、站点开关 `site-config`、submissions `scope=all` 等）均为独立新增路径，与 api.md 既有接口语义并存、互不干扰。
- **会话传递**：后端 `SessionMiddleware` 下发 Cookie（仅 uuid4 会话 id）；前端用统一 HTTP 客户端（httpx/requests 会话）保存并回传 Cookie。Streamlit 运行于服务进程，无浏览器 CORS 同源问题。
- **评测执行要求 Linux**（`python3`/`g++`）：后端与评测在 **WSL2/Ubuntu** 运行（venv `~/oj-venv`）；Windows `.venv` 含 streamlit 用于起前端，经 WSL2 localhost 转发访问后端。

### 2.2 主要功能

| 模块 | 功能 |
|---|---|
| **题目管理（Step1）** | 题目列表/详情/新增/编辑/删除；详情默认字段补齐（str→""、list→[]、time→3.0、mem→128）；删除仅管理员并**级联删除**（testcases、submissions、judge log、access 审计）且**回退用户统计** |
| **评测控制（Step2）** | 语言注册（内置 python/cpp + 动态注册）、语言列表；提交后**异步评测**；编译(C++)/运行/输出归一比对；AC·WA·TLE·MLE·RE·CE·UNK；计分 score=通过测例×10、counts=总测例×10；429 单人单题限频 |
| **评测管理（Step3）** | 提交列表（一级条件 user_id/problem_id 至少其一、status/page 分页、可见性、pending/error 摘要裁剪）；提交详情；rejudge（仅管理员、覆盖重跑） |
| **用户管理（Step4）** | 注册/登录/登出；用户信息与列表；role 变更（admin/user/banned，记录权限操作日志）；创建管理员；**banned 即时失效** |
| **评测日志（Step5）** | 提交日志（`public_cases` 三态可见性）；`log_visibility` 开关；access 审计日志（action=`view_logs`，user_id/problem_id 至少其一） |
| **前端交互（Step6）** | 用户组 / 题目组 / 评测提交组三页；登录态持久化；管理员用户管理与申请审批；结果轮询与状态徽章；**语言管理页（注册新语言）**；**信息中心**（AI 生题/申请审批通知，侧边栏未读角标）；**AI 命题监控页** |
| **AI 智能命题（进阶）** | model-config（per-user，真实调用 OpenRouter/DeepSeek 官方/千问官方或本地 mock，单价/汇率自动获取）；结构化表单 + 纯文本两种输入；任务状态机 + 每 2s 轮询进度（阶段/已用时间/Token/费用）+ cancel 真实中断；**流式 token 估算**（生成中每秒落盘）；硬核三代码对拍；产出预填题目新增/编辑表单；**题目编号由平台分配** |

### 2.3 技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| 后端框架 | **FastAPI**（`async def`，uvicorn） | 异步接口为官方硬性要求；原生 Pydantic 校验 + OpenAPI |
| 数据校验 | Pydantic | 字段校验、422→400 收敛 |
| 鉴权 | Starlette `SessionMiddleware` + 服务端 session（uuid4）+ **bcrypt** 密码哈希 | Step4 教学强调服务端可立即失效；密码不回显 |
| 存储 | **全 JSON 文件**（`data/` 目录化，题目一题一 JSON） | 规模小、结构透明、便于讲解；reset 删目录重建即清空 |
| 前端 | **Streamlit**（Python） | 官方指定，不要求 JS/HTML/CSS |
| 评测执行 | subprocess + **psutil** 内存/超时监控；WSL2/Ubuntu | 限时 kill→TLE、限内存 kill→MLE、记录真实峰值 |
| 测试 | pytest（WSL Linux 全量） | 覆盖接口、鉴权、评测、边界 |
| AI 接入 | OpenAI 兼容客户端（OpenRouter `/api/v1`、DeepSeek 官方、千问官方）+ 本地 **mock** 兜底 | 无 key 阶段打通流程，key 到位后仅替换 client；计价按每 1M tokens 单价 |
| 版本控制 | git（Conventional Commits）+ 双会话并行开发 | 人机协同、功能与打磨并行 |

### 2.4 模块划分（目录树）

```
大作业-2/
├── backend/                       # FastAPI 后端（端口 8000）
│   ├── app/
│   │   ├── main.py                # 入口：lifespan 建目录+种子 admin/示例题、挂异常与路由
│   │   ├── config.py              # 数据目录/初始管理员/RESET_REQUIRE_ADMIN 等全局配置
│   │   ├── core/                  # response 统一成功体 / exceptions 异常+422→400+500 兜底
│   │   │                         # security bcrypt / messages 全站 msg 契约表
│   │   ├── db/                    # store 全 JSON 存储(percent-encode+原子写) / seed 幂等建管理员
│   │   ├── api/                   # 路由层：deps 鉴权依赖 / auth / users / problems
│   │   │                         # languages / submissions / logs / reset / ai / applications / notifications / site
│   │   └── services/              # 业务层：sessions / users / problems / languages
│   │                             #   submissions / judge / runner / pagination / logs
│   │                             #   ai_config / llm_client / ai_tasks / ai_verify / ai_pipeline
│   │                             #   applications / notifications / ai_catalog / site_config
│   ├── sample_problems/           # 示例题 P1000/P1001（版本库内，幂等种入）
│   ├── tests/                     # pytest 用例（d1–d6 + polish 扩展）
│   └── conftest.py
├── frontend/                      # Streamlit 前端（端口 8501）
│   ├── app.py                     # 三组页面 + AI 命题页
│   └── api_client.py              # 统一 HTTP 客户端（Session Cookie、code/msg 展示）
├── scripts/                       # start-backend.sh / app_smoke.py
├── reports/                       # 面向用户文档（需求/进度/各阶段说明/评审/问答/报告素材）
├── start.cmd / stop.cmd           # 一键启动/停止（WSL 起后端→前端→开浏览器）
└── requirements.txt
```

> 说明：后端业务集中在 `services/`（薄 API 只做编排），`api/deps.py` 提供 `get_current_user`/`require_admin` 供 Step1–3 复用；`services/runner.py` 抽离语言无关的编译/运行原语，被 `judge.py` 与 `ai_verify.py` 共用。

---

## 三、关键实现与难点（2 分）

> 以下按"功能 vs 难点"从各阶段实现说明提炼，每一点都给出**做法**与**为何这样处理**。

### 3.1 评测器与资源限制（Step2，全项目技术难点核心）

评测正确性会传导到 Step3/5 与整体演示，故优先实现。

- **流程**：取题目 → 取用户代码与语言 → 编译（C++ 先编、Python 直接运行）→ 逐测例运行、限时/限内存 → 比对输出 → 生成结构化 `compile_info/run_info/error_info`。
- **输出归一比对**：每行 `rstrip()`、去掉末尾空行、忽略末尾多余换行（api.md），避免"空格/换行"差异误判；程序不得输出多余提示语。
- **状态机**：submission 状态 `pending/success/error`；测例状态 `AC/WA/TLE/MLE/RE/CE/UNK`，非 AC~CE 一律归 `UNK`；**CE 的 submission 状态 = error**（编译失败即未通过，`compile_info` 保留、score/counts=0、不跑测例）。
- **计分**：一个测试点 10 分，`score=通过测例数×10`、`counts=测例总数×10`。
- **资源限制生效链**：题目显式 `time_limit/memory_limit` → 否则回退语言注册默认值 → 再缺省按 api.md 兜底 3s/128MB。
- **内存监控（难点）**：监控线程每 20ms 用 `psutil.Process(pid).memory_info().rss` 采样，超限即 `proc.kill()` → MLE，同时记录峰值 RSS 供 `details.memory`；超时 kill 优先归 TLE。实测验证：`memory_limit=16MB` + `bytearray(64MB)` → 真实 MLE 且 memory>0。
- **异步评测（难点）**：`POST` 里 `asyncio.create_task(asyncio.to_thread(judge_submission, sid))`——API 立即返回 pending，同步逻辑在线程池执行（单用户串行足够）。⚠ 测试不能"POST 后再手动同步 judge 同一记录"（会与后台线程竞态写文件），须轮询等待。
- **并发安全**：评测任务加**全局串行锁** `JUDGE_LOCK`，统计"读-改-写"原子，避免并发竞态。
- **信息脱敏**：`error_info` 不泄露服务器路径/临时目录与密钥；编译与运行 `cwd=临时目录` + 相对路径 `./main.ext`，g++ 报错不再带临时目录前缀。

### 3.2 Session 鉴权与 banned 即时失效（Step4，全部鉴权前提）

- 登录 → `uuid4().hex` 生成 sid → 会话 JSON 存 `data/sessions/{sid}.json`（含 `expires_at`，TTL 7 天）→ 响应 `Set-Cookie: oj_session=...; HttpOnly; SameSite=Lax`。**Cookie 里只有随机 id，没有明文身份**；登出删除服务端文件即失效（JWT 无法做到，Step4 页面教学强调）。
- **权限依赖**：`get_current_user` 读 cookie → 查 session → **实时按 username 查库取用户** → 无/失效会话 401 → 用户不存在 401 → `role=banned` 403。`require_admin` 在其上再校验角色。
- **banned 即时失效（自定语义）**：因为每次请求都实时查库，admin 把用户设 banned 后，该用户已登录会话的**下一次请求即返回 403**（官方未定义，本项目按用户决策定为立即失效，并在文档说明）。
- **异常优先级**：401 > 403 > 400 > 429 > 409 > 404 > 500，作为业务层依赖/服务里的判定顺序（先鉴权后校验）；异常处理器只负责把 `ApiError` 或框架校验错误格式化。

### 3.3 统计实时重算（submit_count / resolve_count）

- 口径（api.md 注释 + 助教确认）：`submit_count` **按提交算**（一题可多次）；`resolve_count` **按题目 AC 算**（一题最多一次）。
- **实时重算（用户判定 2026-09-05）**：每次评测完成（含 rejudge）后调用 `recompute_stats`——`submit_count=该用户现存提交记录数`（pending/error/CE 均计入，**rejudge 不额外 +1**）；`resolve_count=AC 过的题目去重数`。重评使唯一 AC 变失败 → resolve 实时回退（幂等重算，judge 串行锁内执行，无读改写竞态）。
- **删除题目回退（难点）**：D3 的 `delete_cascade` 对每题有提交的用户聚合 `{提交数, 是否有 AC}` → `submit_count` 相减、`resolve_count` AC 过则减 1（均 `max(0,·)`）；同时级联删除 testcases、该题全部 submissions 与 judge log、access 审计中该 problem_id 记录。

### 3.4 AI 对拍引擎（进阶难点，硬核模式）

硬核模式（默认关）开启后执行**三代码对拍闭环**，保证测试数据无错误。

- **model-config**：**per-user**（`data/ai_configs/{username}.json`，reset 不清）；`api_key` 脱敏存（对外视图仅 `api_key_configured: bool`，任何响应/日志不含明文）。
- **任务状态机**：`waiting/running/completed/interrupted/failed` + `review`（需人工复核）标记，持久化 `data/ai_tasks/`。
- **对拍引擎**（兼容所有已注册语言，经 `runner.py` 共用编译/运行原语）：数据生成器产**多档规模数据**（小/中/大，按期望复杂度推导，使 O(N²) 类中小点可过、大点 TLE → 部分分梯度）→ 标答算 expected → 小规模点用暴力对照验证 → 通过采纳；不一致/异常 → 生成**错误摘要回传 AI 重试**（≤retry_limit）→ 用尽：completed + **review** + 错误摘要（**题目不入库**）。
- **重试闭环**：硬核首次失败后，把 VerifyError 摘要作为 user 反馈追加再请求；`retry_limit`（默认 2 → 最多 3 次调用）。
- **语言双层防护**：结构化输入 API 层校验未注册语言 → 400；纯文本产出 `language ∉ 已注册` → 任务 failed + 清晰原因与可用列表（prompt 先要求模型遇未注册语言直接产出"语言不支持"）。
- **计费（R4）**：`estimate_cost = 输入token/单位×input_price + 输出token/单位×output_price`；多轮调用 token 累计后统一计费；单价按所选模型从 OpenRouter 实时目录/内置表自动取得，单位 1_000_000（每 1M tokens）；`fx_rate` 由 Frankfurter（ECB）**自动拉取**（失败回退内置参考值 7.2，5 分钟后自动重试），折算 **CNY** 展示；mock 也走同一 usage/cost 结构。**自定义模型**（不在目录中）可在配置页选填 `input_price/output_price`（USD/1M），留空则费用估算显示「未知」（不冒充 0 价）。**生成期间按流式 chunk 估算 token 并约每秒落盘**，前端轮询可见 token/费用实时增长，结束后以服务端 usage 为准。
- **中断**：`cancel_requested` 标志 + 执行阶段 `_guard_interrupted`（写状态前读最新任务、中断不再被覆盖）；cancel 置 interrupted，对已完成任务返回 409。
- **私有字段**：题目采纳后落库 `difficulty_score` + `ai_meta`（语言/生成器/标答/暴力代码/重试次数），仅服务端存储、**不进任何对外 API**（题目 CRUD 不收发）。

### 3.5 其他关键实现

- **统一响应/异常**：成功 `success()` → `{code:200,...}`；业务 `raise ApiError(status_code, msg)` → 全局处理器输出同结构 JSON 且 HTTP 状态码一致；FastAPI 默认 422 经 `RequestValidationError` 转为 **400**；未匹配路由 404 收敛为 `{code:404,...}`；500 兜底处理器只记日志、不回显堆栈。
- **日志可见性三态（Step5，助教 Q7 精确语义）**：`public_cases=False`——本人可见 score/counts 但 **details 为空**，其他登录用户 403；`public_cases=True`——本人与所有登录用户可见完整 details；管理员始终完整；日志公开**不等于**开放用户代码/编译信息等 Step2/3 详情。
- **access 审计**：仅记录"已鉴权且资源存在"的 log 访问（200 与 403 都记，status 存字符串），未登录/不存在/参数错误不记；`user_id/problem_id` 至少其一，全空 400；action 统一 `view_logs`。
- **全 JSON 存储**：key（题目 id、用户名等）经 `urllib.parse.quote` 百分号编码作文件名，防 `/ : * ?` 等非法字符与路径注入；`save_json` 用 tmp + `os.replace` **原子写**，Windows 上遇并发读锁（如 AI 任务轮询读）做退避重试；损坏 JSON 记 warning（与"不存在"区分）。
- **分页语义**：抽公共模块 `services/pagination.normalize_page`（page 有 size 无=400、size 有 page 无=第 1 页、全空=全部、<1=400），users/submissions 复用。
- **iOS/Windows 与 WSL 双环境**：venv 为 Windows 原生；WSL 内 `curl 127.0.0.1` 连不上 Windows 侧进程，需 `/mnt/c/Windows/System32/curl.exe` 或绑 `0.0.0.0` 后访问宿主 IP；评测命令（g++/python3/资源限制）在 WSL Ubuntu 验证。

---

## 四、成果展示（1 分）

### 4.1 系统效果（功能走查）

- **登录/注册**：未登录全画幅居中卡片，注册成功自动登录并进入题库；刷新自动恢复登录态。
- **题库**：分页圆角卡片（编号、难度、标签、通过率条），按编号/标题搜索，点击进入详情。
- **题目详情**：左侧题面（描述/输入输出/样例/约束/提示），右侧栏提交代码（语言选择 + 大文本框 + "提交评测"）、近 3 次提交自动刷新、查询提交记录入口。
- **查询提交记录**：按题目/状态筛选、时间倒序、自动刷新；判定徽章按得分区分（全对=通过、部分对=部分通过、0 分=未通过）；错误细分（CE/评测错误）。
- **题目管理**：搜索、编辑/删除图标、新增题目、**语言管理**（注册新语言，见下）与 AI 命题入口；普通用户改/删走**申请-审批流**（管理员审批），管理员直接改/删；管理员可在「个人 → 站点设置」关闭"允许普通用户编辑题目"（默认开，关闭后编辑入口与申请均被拒绝）。
- **个人**：信息卡（右侧未读消息数）+ 查询入口 + **信息中心**（AI 生题完成/申请审批结果通知，可跳转任务或题目，单条/全部已读）；侧边栏「个人」带未读角标；管理员可用户管理与申请审批。
- **AI 命题**：模型配置（per-user，下拉选模型自动带单价/汇率，Key 已配置不回显）、结构化表单 + 纯文本两种输入、硬核开关与重试调节、任务页每 2s 轮询显示阶段/已用时间/Token/费用（CNY）、cancel 中断、产出预填题目新增/编辑、对拍用尽进入"需人工复核 + 错误摘要"；**AI 监控页**集中查看全部任务。
- **语言管理**：列出已注册语言；任意登录用户可注册新语言（name/file_ext/run_cmd 必填，compile_cmd 与 time/memory_limit 可选，命令模板 {src}/{exe} 自动替换为路径），注册后立即可用于提交评测与 AI 命题语言下拉。

### 4.2 边界测试结果（覆盖关键边界，pytest 在 WSL Linux 全量执行）

| 场景 | 结果 |
|---|---|
| 全量回归 | Windows 本地全量 **84 passed + 2 skipped**（仅 cpp 编译评测与 MLE 峰值评测在 win32 显式跳过，属 WSL-only）；WSL Linux 全量数据见文末附录 |
| MLE 真实评测 | 题目 `memory_limit=16MB` + `python bytearray(64MB)` → 实测 MLE 且 memory>0 |
| 越权 | 普通用户访问他人提交详情 / 删除题目 → 403；未登录 → 401 |
| 限频 | 同一用户同一题 1 分钟第 4 次提交 → 429 |
| 冲突 | 题目 id 已存在 → 409；用户名已存在 → 400；校验失败 → 400（非 422） |
| 资源不存在 | 题目/用户/提交不存在 → 404 |
| banned 即时失效 | 将用户设 banned 后其已登录会话下一次请求 → 403 |
| 日志可见性三态 | 未公开：本人无 details/他人 403；公开：全员 details；管理员恒完整 |
| 统计口径 | rejudge 不新增 submit_count；AC 变失败 resolve_count 实时回退 |

**MLE 样例 JSON 摘录**（真实评测结果样例）：

```json
{
  "submission_id": "1",
  "status": "success",
  "score": 0,
  "counts": 10,
  "details": [
    { "id": 1, "result": "MLE", "time": 0.083, "memory": 23.6 }
  ]
}
```

> 说明：`status=success` 表示"评测完成"，不等同于 AC（0 分即未通过）；`score/counts` 计分口径为每测例 10 分。**完整界面截图待采集**（见文末附录），上述 JSON 摘录与边界用例结果均可复现。

### 4.3 演示脚本摘要（约 10 分钟，双通道）

- 通道 A（基础）：登录 admin → 注册 alice → 提交正确代码 AC / 错误代码部分分 / 死循环 TLE / 大内存 MLE → 日志可见性对比 → 越权 403 → banned 即时失效 → reset 复原。
- 通道 B（AI 命题）：模型配置（mock 或真实 key + 选择模型）→ 结构化表单（语言 python、考点排序、难度 6、复杂度 O(n log n)、硬核重试 2）→ 生成 → 采纳预填 → 保存 → 提交 O(n log n) AC vs O(n²) 暴力**中小点过/大点 TLE → 部分分**。

---

## 五、AI 使用说明（0 分，硬性必写）

> 本项目**全程人机协同（Vibe Coding）**开发，符合"使用 AI 辅助必须在报告中提交 AI 使用说明"的要求。以下工具链、工作流与分工均为实际执行情况；**各文件 AI 生成比例为待核对初稿**，见 5.3 与文末附录。

### 5.1 工具链

| 用途 | 工具 |
|---|---|
| 协作 AI | 对话式编码智能体（生成/修改代码、撰写文档、评审、排期、问答归档） |
| 版本控制 | git，Conventional Commits（`feat/fix/docs/test/chore`）；GitLab/GitHub 作业仓库 |
| 后端运行 | Windows `.venv`（含 streamlit）/ WSL `~/oj-venv`；uvicorn |
| 前端 | Streamlit（`streamlit run frontend/app.py`） |
| 评测执行 | WSL2/Ubuntu（python3 / g++），psutil 资源监控 |
| 测试 | pytest（WSL Linux 全量）；`scripts/app_smoke.py` 真实 HTTP 冒烟 |
| 文档/评审 | `reports/`（需求/进度/各阶段说明/评审台账/问答清单/报告素材） |

### 5.2 工作流（人机协同闭环）

1. **需求对齐**：AI 通读课程官方全部页面，产出需求分析文档（含每个歧义点的用户决策记录）与分日进度计划。
2. **分日实施**：按官方 Step + 内部依赖排期（Step4→Step1/2→Step3→Step5→Step6→AI），每日完成一个主题；每阶段 AI 产出一份《实现说明 + 代码导读 + 自测清单》供用户自行消化。
3. **评审迭代**：每轮 AI 自查 + 用户提供的外部评审意见，按 P1/P2/P3 分级登记到评审台账并回填处理状态；每轮评审意见另归档到 `comments/` 目录。
4. **助教问答归档**：把 api.md 的歧义点整理成待确认清单，携带原文词句向助教提问，拿到答复后回填到需求文档的"已确认决策"一节（如 429 单人单题、access 筛选、CE 归属、日志可见性三态、统计实时重算）。
5. **双通道并行打磨**：基础骨架由 AI 协作会话完成（D1–D6）；`polish/` 与若干高级功能（题目申请/删除审批、通知中心、千问直连、AI 监控页、流式 token 估算、hint 分离、Cookie 修复、Windows 并发写退避等）由用户的**另一会话**完成并合并入库——"打磨功能纳入验收与报告口径，不深改"。AI 负责维护评审台账与测试稳定性记录。
6. **风险预案**：进度与评审记录中保留"时间吃紧则 AI 收缩为 R1–R4 + 硬核单轮对拍（保底约 4–5 分），基础与报告不挤占"等预案。

### 5.3 Vibe Coding 代码比例（待核对初稿）

协作 AI 主要承担**骨架、接口实现、文档与评审**；**polish 打磨与若干高级交互**由用户另一会话编写。下表基于模块特征与各阶段实现说明记录的分工给出**估计比例**，需用户用实际协作记录核定（见文末附录）。

| 模块 / 文件 | 主要产出方 | 初步估计 AI 生成占比 |
|---|---|---|
| `backend/app/db/` `core/`（存储/响应/异常/安全/msg） | 协作 AI | 高（约 90%） |
| `backend/app/services/`（sessions/users/problems/judge/runner/…） | 协作 AI | 高（约 90%） |
| `backend/app/api/`（鉴权依赖与 REST 路由） | 协作 AI | 高（约 90%） |
| `backend/app/services/ai_*` + `llm_client`（AI 后端） | 协作 AI | 高（约 90%） |
| `backend/app/api/applications.py` `notifications.py` `ai_catalog.py` 等 | 用户另一会话 | 低（约 10–30%） |
| `frontend/app.py` `api_client.py`（页面主体） | 协作 AI | 中高（约 70%） |
| `polish/` 前端打磨 + 高级交互 | 用户另一会话 | 低（约 10–25%） |
| `reports/`（需求/进度/实现说明/评审/问答） | 协作 AI + 用户审阅 | 高（约 90%，内容经用户核对） |
| 测试用例（`backend/tests/`） | 协作 AI | 高（约 90%） |

> 这些比例是**初稿/估计**：AI 生成代码后由用户审阅、修改、运行验证后再纳入，故"AI 生成占比"不等于"最终代码归属"；如需精确数字，可按各文件 git blame 行数统计核定。

---

## 六、总结与建议

### 6.1 收获

1. **前后端分离 + 严格契约**：以 REST API + `{code,msg,data}` + HTTP 状态码为唯一契约，理解了"前后端以接口为准、权限在后端"的分层思想。
2. **异步与并发**：`asyncio.create_task` 实现异步评测，评测任务经 `threading.Lock`（`JUDGE_LOCK`，线程池 `to_thread` 内）串行化，理解"API 立即返回 pending、后台执行"与测试必须轮询等待的取舍。
3. **评测器正确性**：编译/运行/资源限制/输出归一比对/状态机/计分的完整链路，以及 MLE 的内存监控实现。
4. **鉴权与安全**：服务端 Session 的"可立即失效"优势、banned 即时失效、bcrypt 与敏感信息脱敏。
5. **统计口径与一致性**：submit/resolve_count 的实时重算、删除级联回退、rejudge 语义，理解"数据与统计一致性"的维护成本。
6. **LLM 编排与务实降级**：从 prompt/解析/对拍/重试/计费的完整 AI 流程，到"无 key 用 mock 打通、有 key 无缝切换真实调用"的工程化思路。

### 6.2 改进建议

1. **官方 Step 顺序与内部依赖不完全一致**（先鉴权、再评测），需自定开发序；建议官方在评分细则中附依赖图。
2. **测试稳定性**：WSL 全量偶发**环境级顺序 flaky**——AI 用例在 TestClient 高频轮询场景下偶报 `OSError [Errno 61]`/404（单测与子集复跑全部通过，9.9 尝试"后台任务收敛 fixture"后失败率未降，判定为 TestClient/anyio portal 时序问题而非业务缺陷）。标准执行口径：验收前全量跑 2 轮，出现失败即对失败用例 `pytest --lf`/单文件复跑确认（评测后台任务收敛 `_drain_judges` 已生效于 judge 类用例）。
3. **素材收集滞后**：报告截图与边界结果应随开发"顺手采集"，而非临近截止突击（本次已建立素材归档机制但截图仍待补）。
4. **并发写与集中状态**：全 JSON 存储在单用户串行下够用，但多用户并发/多进程时需引入锁或数据库；内存/超时采样间隔与并发开销需平衡。
5. **AI 依赖外部 key**：真实联调依赖模型 key；**汇率已实现自动拉取（Frankfurter/ECB，离线内置参考值兜底）**，后续可继续扩展更多厂商目录与官方直连模型。

### 6.3 时间投入（按实际投入整理）

| 日期 | 事项 | 等效 |
|---|---|---|
| 9.2 | 铺环境（venv/依赖/目录骨架）+ 需求分析 | — |
| 9.3 | D1 公共骨架 + D2 用户系统（Step4） | 2 个计划日 |
| 9.4–9.5 | D3 Step1+Step2 主体、D4 Step2 收尾(MLE)+Step3 | 2 个计划日 |
| 9.6 | D5 Step5 + AI 对齐 | 1 个计划日 + AI 对齐 |
| 9.7 | D6a Step6 前端主体 | 合并 D6+D7 |
| 9.8 | D7a 联调收尾 + 全量回归 + AI 后端（Phase2） | — |
| 9.9 | AI 前端 + 对拍联调 + 报告成稿 | — |
| 9.10 | 演练 + 最终 commit + 报告 PDF | 验收日 |

> 工作日每日约 3h、周末每日约 4–6h；用户反馈"一天可做两天的事"，按加速节奏重排后基础部分按期完成，AI 模块与报告在 9.9 冲刺。

---

## 附录：待人工核对/补齐项

1. **AI 使用比例表（5.3）**：为估计初稿，需用户用各文件 git blame/实际协作记录核定（评分点不单独计分，但硬性要求写明）。
2. **界面截图**：完整界面截图（登录/题库/详情/提交/日志三态/AI 命题/越权提示/AC vs 部分分梯度）待采集后插入本报告 §4.1/§4.2（MLE 样例 JSON 摘录已在 §4.2 给出）。
3. **测试全量数**：Windows 本地全量为 **84 passed + 2 skipped**（2026-09-09 实测，skip 为 WSL-only 的 cpp/MLE 用例）；WSL Linux 全量需在验收前按「连续 2 轮全绿、失败用例 `--lf`/单文件复跑确认」的标准执行，并用实际数字替换（9.9 现状：WSL 全量约 86 用例，AI 用例存在上述环境级偶发 flaky，见 §6.2 第 2 条）。
4. **PDF 生成**：当前环境无 pandoc/markdown+weasyprint 等转换工具，本报告为 Markdown。可在安装后执行：
   ```bash
   pip install markdown weasyprint
   pandoc reports/EXP_REPORT.md -o reports/EXP_REPORT.pdf   # 或使用支持 md→pdf 的编辑器
   ```
   或直接用 Typora/Pandoc 等工具导出。
