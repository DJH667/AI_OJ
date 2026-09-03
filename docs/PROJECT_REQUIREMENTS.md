# 实验二：在线评测系统（OJ）—— 需求分析文档 v2

> 来源：https://dbg-course.github.io/python-docs/oj/（程序设计训练 · Python 课程，2026 年秋季）
> 本文档为通读全部页面（实验概述、Step1–6、Advance、API 文档、评分标准、FAQ、仓库拉取教程）后的需求总结，供开发与验收对照使用。
> v2（2026-09-02）：对照官网 2026-09-01 版页面逐页复核修订；修订点已在各节标注 ⚠。

---

## 1. 项目概述

- **目标**：构建一个小型但功能完整的 Online Judge（OJ）系统，分阶段实现系统设计、API 开发、异步评测、权限控制和前后端交互；进阶模块在此基础上引入大语言模型（AI 智能命题）。
- **总分**：50 分 = 实验功能验收 40（基础 30 + 进阶 10）+ 代码规范 5 + 实验报告 5。最终按比例缩放计入总评（本作业占总评 30%）。
- **代码规模**：约 2000 行，属"较大项目"体验，需做好进度管理。

### 1.1 系统架构与前后端分离（官方 Step6 任务 4 明示要求）

官方原文："前后端分离架构下，所有数据流转均依赖 API，需保证参数、路径、状态码一致。应确保所有前端操作均通过 REST API 与后端交互，并严格遵循 API 文档中的接口规范。"

- **两个独立应用（独立进程启动）**：
  - 后端：FastAPI（`async def`），只提供 REST API（`/api/*`：Step1–5 业务接口 + AI `/api/ai/*`）；存储、鉴权、评测、日志全部在后端。
  - 前端：Streamlit（`streamlit run app.py`），不直连存储/数据库、不做鉴权决策；一切操作经 HTTP 调后端 API。
- **通信契约**：仅 REST API + JSON `{code,msg,data}` + HTTP 状态码；前端**不新增独立业务接口**、不发散自建路径（api.md §5）。
- **会话传递**：后端 `SessionMiddleware` 下发 Cookie；前端用统一 HTTP 客户端（httpx/requests 会话）保存并回传 Cookie。Streamlit 脚本运行于 Streamlit 服务进程（非浏览器 JS 直调），无浏览器 CORS 同源问题；但不得在页面代码中硬编码用户身份，登录态仅来自后端会话。
- **目录与启动约定**（建议）：仓库内分 `backend/`（FastAPI 源码）与 `frontend/`（app.py 等）；`uvicorn backend.main:app --port 8000` 与 `streamlit run frontend/app.py --server.port 8501` 各自启动；前端对后端的 base_url 做成可配置项。
- **验收提示**：任务 4 单独计 1 分（API 调用、会话传递、响应与异常处理）；演示时两个进程同时运行、页面状态与后端数据一致（不得仅前端模拟操作结果）。

## 2. 硬性时间节点（2026 年）

| 时间 | 事项 |
|---|---|
| 9.10（周四）课前 | 全部源码完成，在网络学堂提交**最后一次 git commit 号** |
| 9.10（周四） | 助教**线下验收**（形式后续通知，参考第一次大作业；结合 Linux 自动评测 + 人工） |
| 9.10（周四）23:59 | 实验报告在网络学堂截止提交（建议 PDF） |
| — | 原则上不补交（需医学证明等充分理由且仅一次）；逾期未验收功能记 0 分 |

> 仓库：助教为每位同学创建 GitLab 作业仓库（形如 `pa2-oj-<学号>` @ git.tsinghua.edu.cn），clone 认证用 **Personal Access Token**（非登录密码）。详见 §8。

## 3. 总体技术要求（红线）

1. **异步接口**：所有 API 必须使用 FastAPI 的 `async def`；不使用异步拿不到本次作业分数。异步评测可参考 `asyncio.create_task`；评测只需支持单用户提交，不要求多用户同时提交。
2. **响应协议**：所有接口 JSON 必须含 `code` 字段且与 HTTP 状态码一致；服务器必须设置对应 HTTP 状态码（不能全返回 200）。成功示例 `{"code": 200, "msg": "success", "data": ...}`；错误示例 `{"code": 404, "msg": "problem not found", "data": null}`。
3. **异常处理顺序**：401 > 403 > 400 > 429 > 409 > 404 > 500。FastAPI 默认 422 校验错误需转为 400（用 `Depends`/`RequestValidationError` 中间件解决，FAQ 有示例）。
4. **状态码语义**：200 正常 / 400 参数错误 / 401 未登录 / 403 权限不足或被 ban / 404 资源不存在 / 409 状态冲突（id 已存在、任务已结束）/ 429 频率超限（1 min 内提交超过 3 次）/ 500 服务器异常。
5. **Git 提交**：遵循 Conventional Commits（`feat`/`fix`/`docs` 等 + 简洁描述）；**不得把大文件提交进 git**（扣分项）。
6. **Linux 兼容**：最终在 Linux 自动评测（g++、python3 等常用指令）。Windows 同学建议用 WSL2 开发/测试。
7. ⚠ **初始管理员**：系统启动自动创建 `admin` / `admintestpassword`。该密码为 **17 位全小写**（`admin`+`test`+`password`），满足注册校验（用户名 3–40、密码 ≥6），与注册规则无冲突；注册/建管理员接口对重名用户按 400 处理（api.md：注册"400 用户名已存在"，创建管理员同）。
8. **测试支持接口**：`POST /api/reset/`（仅管理员，测试环境可不校验）——清空用户/题目/提交数据、退出登录、重建初始管理员。**自动评测会使用，必须实现**。

## 4. 数据模型与通用约定

> **存储总体方案（用户决策 2026-09-02，dec-0f895a1ddd678090）**：**全 JSON 文件**——题目每题一个 JSON（`problems/`）；用户/提交/日志等以 JSON 条目存于各自目录（`users/ submissions/ logs/`）；无二进制文件、结构透明便于阅读讲解；`POST /api/reset/` 清空即删目录重建。数据规模小且评测单用户串行，无并发写压力。

### 4.1 题目（problem）字段
必填：`id`(str)、`title`、`description`、`input_description`、`output_description`、`samples`(list of {input,output})、`constraints`、`testcases`(list of {input,output})
可选：`hint`、`source`、`tags`(list)、`time_limit`(float，api.md 标注默认 3s)、`memory_limit`(int，api.md 标注默认 128MB)、`author`、`difficulty`(str，api.md 契约，展示标签如"入门")
- ⚠ **AI 扩展字段（向后兼容新增，不破坏 api.md）**：`difficulty_score`(float，可选，建议范围 0–10) 用于数值化难度，供 AI 模块抽取"难度相近的站内题"作参考（用户决策 dec-7b47335beaa64320）；`difficulty`(str) 保留原契约不动，未提供 score 时可由标签映射估值。
- 存储建议：本地目录 `problems/`，每题一个 JSON 文件（文件名建议含 id，转义不安全字符）。
- 查询详情时默认字段需返回本类型默认值（str→""、list→[]）。
- `samples`（展示给用户）与 `testcases`（评测用）分开。
- ⚠ **资源限制生效链**（Step2 页面 + api.md 综合）：题目显式给出 time/memory_limit → 使用之；否则回退到**该语言注册时的默认值**（语言注册字段可选 time_limit/memory_limit）；再缺省按 api.md 题目字段标注 3s/128MB 兜底。实现内置语言默认值时应与上述对齐。

### 4.2 评测状态（submission 级）与测试点结果（case 级）
- submission 状态：`pending` / `success` / `error`。
- 测试点结果：`AC` / `WA` / `TLE` / `MLE` / `RE` / `CE` / `UNK`；**非 AC~CE 状态一律归 UNK**（Step2 页面）。
- 计分（Step2 页面）：**一个测试点 10 分**；score=通过测例数×10，counts=测例总数×10。
- submission 详情示例字段：`submission_id, user_id, problem_id, language, code, status, score, counts, compile_info{result,message}, run_info{result,message}, error_info, details[{id,result,time,memory}]`。`pending/error` 至少返回 `submission_id` 与 `status`，未产生字段可返回 null。

### 4.3 用户
角色：`user` / `admin` / `banned`（banned 再登录被拒 403；⚠ 已登录会话中途被改 banned 是否立即失效官方未定义，需自定并在文档说明；现按用户决策 dec-0f895a1ddd678090 定为**立即失效**——每次请求实时查库校验角色，被 ban 后下一次请求即 403）。
字段：`user_id, username, password(bcrypt 加密), role, join_time(YYYY-MM-DD), submit_count(按提交计，一题可多次), resolve_count(按题目 AC 计，一题最多一次)`（口径注释出自 api.md 注册接口）。
认证：**Session**（FastAPI/Starlette `SessionMiddleware` + `uuid4` 生成 session id，服务端存储；登出清除服务端 session；可设过期时间）。Step4 页面教学：Session 优于 JWT 之处在于服务端可立即失效。
- ⚠ **加密与传输边界**：①存储层——密码必须 bcrypt 哈希（api.md），模型 api_key 等敏感配置不得明文落盘/日志；②会话层——Cookie 只携带 uuid4 session id（不可预测/伪造），不含明文身份，靠服务端会话映射 + 过期实现安全，无需对 cookie 内容二次加密；③传输层——本地开发与课程验收走 HTTP 明文即可，TLS/HTTPS 仅公网部署需要（FAQ 中"HTTPS 传 Cookie"为生产建议，不属验收项）；④泄露防护——密码/密钥不进日志、错误信息与普通响应，不放入 URL/GET 参数（避免访问日志留痕），`error_info` 等字段脱敏。

### 4.4 语言（language）注册
`name`、`file_ext`、`compile_cmd`(可选)、`run_cmd`(必填)、`time_limit`(可选)、`memory_limit`(可选)。
命令中 `{src}`/`{exe}` 需替换为**路径**（如 `./test.cpp` 而非 `test.cpp`）。示例：
- cpp: `compile_cmd="g++ {src} -o {exe}"`, `run_cmd="{exe}"`
- python: `run_cmd="python3 {src}"`（解释型无 compile_cmd）
注册语言权限：**任意已登录用户**（api.md）；暂不考虑删除语言（Step4 页面权限提示）。

## 5. 基础模块接口清单（须严格遵循 api.md）

> 下表为验收基准（api.md，2026-09-01 版）。各 Step 页面内部的**评分权重**（用于排优先级）见附录 A。

### Step 1 题目管理（5 分）
| 接口 | 权限 | 说明 |
|---|---|---|
| GET `/api/problems/` | 登录 | 列表：`[{id,title},...]` |
| POST `/api/problems/` | 登录 | 字段校验；400 缺失/格式错误；409 id 已存在；返回 `{"id":...}` |
| PUT `/api/problems/{problem_id}` | 登录 | body 中 id 必须与路径一致（否则 400）；404 不存在 |
| DELETE `/api/problems/{problem_id}` | **仅管理员** | 404 不存在；**级联删除**：testcases（随题目文件）、该题全部 submissions 及其评测日志（judge log）、access 审计中该 problem_id 的记录（助教确认 2026-09-02） |
| GET `/api/problems/{problem_id}` | 登录 | 404 不存在；含全部字段与类型默认值 |

> ⚠ **助教澄清（微信群 2026-09-02，作为实现/验收基准）**：
> 1. 普通用户查看题目详情时 **`testcases` 需要返回**（含全部字段与类型默认值，与 api.md 详情示例一致）；
> 2. **题目修改（PUT）允许所有普通登录用户**（仅删除限管理员，与上表一致）；
> 3. **修改题目或测试点后，历史已通过的提交不需要重新评测**——系统不自动触发 rejudge（rejudge 仅管理员手动调用）；
> 4. **删除题目时级联删除**：testcases（随题目 JSON 删除）、该题全部 submissions、judge_log（submission 级评测日志与测例 details）、access_log 中该 problem_id 的审计记录。
> 未定义项（建议必要时追问助教）：删除题目后历史提交曾计入的 `submit_count`/`resolve_count` 是否回退——当前默认**不回退**（统计视为历史快照，实现时在文档注明）。

### Step 2 评测控制（5 分）
- 评测流程：取题目 → 取用户代码与语言 → 编译（如需要，C++ 先编译再运行）→ 逐个测例运行、限时/限内存（超限立即 kill → TLE/MLE）→ 比对输出（忽略行末空格与最后多余换行；程序不得输出多余提示语）→ 结构化结果（compile_info/run_info/error_info）。
- 支持 Python + C++（多语言机制可扩展，动态注册如 go）；评测接口返回最终结果（详细测例在 Step5 日志接口）。
- `POST /api/submissions/`：登录；参数 problem_id/language/code；异常含 400/401/403/**429**（1min 内 >3 次）/404（题目或语言不存在）；返回 `{submission_id, status:"pending"}`。
- `POST /api/languages/`：登录注册语言；`GET /api/languages/`：返回 `{"name":["python","cpp"]}`。

### Step 3 评测管理（5 分）
- `GET /api/submissions/`：参数 user_id、problem_id（**一级条件，至少提供一个**）、status、page、page_size（二级）。page+page_size 全空=全部数据；page 空 page_size 非空=第 1 页；page 非空 page_size 空=400。
- ⚠ **可见性修订**（api.md 原文语义）：提供 user_id 时——管理员可查任意用户记录，普通用户只能查自己的（越权应拒绝）；未提供 user_id 时（此时必有 problem_id）——管理员=该题所有用户的记录，普通用户=该题自己的记录。
- ⚠ **列表摘要裁剪**：条目 status 为 `pending`/`error` 时只需返回 `submission_id` 与 `status`；其余返回 `{submission_id,status,score,counts}`。响应 `{total, submissions:[...]}`。
- `GET /api/submissions/{submission_id}`：仅本人或管理员；含 status/score/counts/compile_info/run_info/error_info；pending 至少 id+status。
- `PUT /api/submissions/{submission_id}/rejudge`：仅管理员；**覆盖原 submission_id 对应内容**；状态回 pending；404 不存在。

### Step 4 用户管理（5 分）
- `POST /api/users/` 注册（用户名 3–40、密码 ≥6、唯一性 400、bcrypt）；`POST /api/auth/login`（400 参数 / 401 用户名或密码错误 / **403 用户被禁用**）、`POST /api/auth/logout`（401 未登录）。
- `GET /api/users/{user_id}`：仅本人或管理员（不含密码）；404 用户不存在。⚠ 响应含 username/role（以 api.md 为准；Step4 页面旧示例缺这些字段，属版本漂移，勿照抄页面）。
- `PUT /api/users/{user_id}/role`：仅管理员，role∈{admin,user,banned}（否则 400），**记录权限操作日志**（谁在何时改了谁的权限——与 Step5 的 view_log 审计是两回事，勿混淆）。
- `GET /api/users/`：仅管理员，分页筛选（语义同 submissions 列表）；响应 `{total, users:[...]}`。
- `POST /api/users/admin`：仅管理员创建新管理员（重名 400）。
- **权限回填**（Step4 页面"权限提示"，关键！）：Step4 之后——题目上传/语言创建=任意登录用户；删除题目=仅管理员；暂不支持删除语言；**未登录用户不得对任何资源增删查改**（Step1–3 接口需补 401/403 校验）。

### Step 5 评测日志（5 分）
- `GET /api/submissions/{submission_id}/log`：仅本人（未公开时）或管理员；管理员可见 `details`（每测例 `{id,result,time,memory}`）；仅当题目 `public_cases=True` 时其他用户可见 details。响应 `{details, score, counts}`。⚠ Step5 页面补充语义：日志对所有人公开 ≠ 公开 Step2/3 的简单结果——无权限用户即便能看该评测的日志 details，仍访问不了该 submission 的 Step2/3 详情接口。
- `PUT /api/problems/{problem_id}/log_visibility`：仅管理员；参数 `public_cases`(bool，默认 False)。
- `GET /api/logs/access/`：仅管理员；审计日志查询，action 统一为 `"view_log"`（⚠ api.md 正文一处笔误写作 `view_logs`，以响应示例为准，全站统一）；返回含 `status`（记录本次访问是否被拒，如 `"403"`）。筛选 user_id/problem_id/page/page_size（分页语义同 submissions）。**不记录**：未登录 / submission 不存在 / 参数错误时。

### Step 6 前端交互（5 分）
- **Streamlit**（Python，不要求 JS/HTML/CSS），`streamlit run app.py` 启动；通过 REST API 与后端交互；**不新增独立业务接口**；禁止绕过 API 直读后端数据、禁止硬编码用户身份；登录态靠 Session/Cookie 传递；按 HTTP 状态码与 `code/msg` 展示结果；权限与可见性以后端为准（不能仅靠前端隐藏按钮）。
- 三组页面（FAQ/Step6 页清单）：
  - 用户：注册、登录、信息展示、**用户管理**（role 修改，仅管理员可见）；
  - 题目：列表、详情、新增/编辑（删除）、表单覆盖完整配置字段并在提交前校验；
  - 评测与提交：提交代码、记录列表、详情（评测状态、编译信息、运行结果、错误、TLE 等明确提示）、日志；提交后轮询或手动刷新状态。
- 评分权重：用户组 2 / 题目组 1 / 评测提交组 1 / 前后端对接 1（见附录 A）。

## 6. 进阶模块：AI 智能命题（10 分）

- **目标**：命题人输入知识点/难度/要求 → 系统独立完成题目设计与题目配置、测试点生成，产出**可直接进入题目新增/编辑流程**的结果。
- **评分**：R1 出题交互界面 1 / R2 可自定义模型配置 1 / R3 实时进度渲染与中断 1 / R4 Token 用量与价格统计 1 / 题目合理性 2 / 测试用例有效性 2 / 功能易用性 2。
- **R1**：界面可提交命题需求、展示处理状态与结果、与题目新增/审阅/修改合理衔接（**返回压缩包/纯文本=反例③"与基础功能割裂"**；仅单次文本生成、内容与输入约束无关=反例④）。
- **R2**：可配置 provider_url、model、api_key（不得硬编码在代码中）；配置**必须实际用于后续请求**；密钥不得在日志/页面响应/错误信息中明文泄露。
- **R3**：执行期间持续展示可观察进度（流式/SSE/WebSocket/轮询皆可），禁止只在完成后一次性返回；中断必须**实际终止任务或阻止继续执行**（仅停前端动画不算），界面明确展示"已中断"。
- **R4**：统计并清晰展示当前任务 Token 用量与费用；接口能区分输入/输出 Token 时应分开记录；费用 = 输入token/计价单位×输入单价 + 输出token/计价单位×输出单价；**说明计价依据**；接口不能提供完整用量时须说明统计/估算方式及限制。
- 工具调用/Agent Loop **不要求**（仅设计参考方向）。
- 接口建议（可等价替换，替换时须在项目文档说明路径/参数/状态/响应）：`PUT /api/ai/model-config`、`POST /api/ai/problem-tasks/`、`GET /api/ai/problem-tasks/{id}`、`GET .../events`(SSE)、`PUT .../cancel`；任务状态至少区分 等待/执行/完成/中断/失败；取消已完成任务返回 409。

### 6.1 AI 命题界面与产出衔接（用户设计决策，2026-09-02，dec-7b47335beaa64320）

**两种输入界面**（发起命题时二选一）：
- **结构化表单**：考点（关键词多选，参考洛谷题目标签体系，配"其他"自定义输入）、难度（多档数值，基于题目 `difficulty_score` 的数值档位；可附带站内题目链接作为难度/风格参考）、预期复杂度（选项 + 其他）、数据规模（选项 + 其他）、情景或背景故事（可选文本框）、备注（可选）。⚠ **不含 SPJ 维度**（用户已决定移除——站内评测仅文本比对）。
- **纯文本**：用自然语言描述命题需求；同样支持引用站内题目链接；可选**本地上传文件**作为背景资料——若所接入模型为纯文本模型，上传界面须警告"大模型无法观看图片"（文件仅按其可提取的文本内容处理）。

**站内参考题抽取**：解析需求中的站内题目链接 → 拉取该题题面/配置作参考；难度相近参考题按 `difficulty_score` 邻域（默认 ±1，可调）从题库抽取。参考题内容仅作为喂给模型的上下文，不直接成为产出。

**产出衔接（规避反例③、复用既有代码）**：模型完整回复产出**结构化题目 JSON**（题面/输入输出说明/样例/数据范围/时间内存限制/测试点等）后，前端**跳转到题目"新增/编辑"界面并把 AI 产出预填到对应表单字段**，供人工审阅修改后按普通题目 CRUD 提交。不产生与题目管理割裂的产物（返回压缩包/纯文本粘贴即反例③）。

## 7. 实验报告（5 分，建议 PDF，图文并茂）

| 评分点 | 分值 | 内容 |
|---|---|---|
| 系统功能与设计 | 2 | 架构、主要功能、技术选型、模块划分 |
| 关键实现与难点 | 2 | 关键技术实现、难点与解决方案 |
| 成果展示 | 1 | 系统效果、边界测试结果 |
| AI 使用说明 | 0 | 工具链、工作流、Vibe Coding 代码比例 |
| 总结与建议 | 0 | 收获、改进建议、时间投入 |

> ⚠ 表格标注 0 分，但评分标准明确：**使用 Vibe Coding（AI 辅助）必须在报告中提交 AI 使用说明**；本项目全程人机协同，四项都应写（内容并入 4 分评分点一并展示）。扣分项另见评分标准：抄袭 0 分、代码/报告与演示内容不符酌情扣分。

## 8. 隐含约束与风险备忘

- 自动评测可能调用 `POST /api/reset/`，接口路径/响应结构**必须与 api.md 完全一致**（基础模块接口不允许自创变体；AI 模块允许等价接口但须文档说明）。
- 校验响应为 400 而非 422；"题目 id 已存在"返回 409；"用户名已存在"返回 400。
- 内存限制监控参考 FAQ 的 psutil + 子线程轮询方案（`psutil.Process(pid).memory_info().rss` 超限 kill → MLE；超时 kill → TLE）。
- `compile_info` 解释型语言可返回 null；`error_info` 不得泄露服务器路径/密钥。
- Windows 本机开发时评测命令（g++/python3/资源限制）须在 **WSL2/Ubuntu** 中测试；`psutil` 等包按 Linux 行为适配。
- 登录态用 Cookie/Session；Step6 前端轮询评测结果。
- ⚠ **仓库操作**（gitpull 教程）：作业仓库由助教创建于 git.tsinghua.edu.cn（GitLab，形如 `pa2-oj-<学号>`）；`git clone` 时认证——username=清华 GitLab 账户，password=**Personal Access Token**（在 GitLab User settings 创建，非登录密码）；`git remote -v` 检查 origin；拉取助教示例仓库更新用 `git remote add upstream <url>` + `git fetch/pull upstream`（可配 `git config pull.rebase true`）。
- ⚠ 前端表单应与后端校验一致（用户名 3–40、密码 ≥6、题目 id 与路径一致等），避免把可预检错误抛给后端。

## 9. 已确认决策与待提供事项

**已确认（2026-09-02，用户答复，decision dec-64d607b21978d527 + dec-7b47335beaa64320）：**
1. **范围**：基础六步 30 分为硬保底；AI 进阶冲完整 10 分（在不伤基础进度的前提下）。
2. **节奏**：砍掉所有专门"熟悉日"——开发时段（每日约 3h）专注功能开发，**阶段熟悉由用户另出时间完成**；每阶段交付"实现说明 + 代码导读 + 自测用例清单"（docs/），供用户自行研读，开发时可随时打断提问。
3. **时间预算**：工作日每日约 3h；周末（9.5/9.6）各 4–6h。
4. **题目难度数值化**：新增可选扩展字段 `difficulty_score`(float，0–10)，api.md 的 `difficulty`(str) 契约不动；AI 参考题抽取用 score。
5. **AI 命题界面**：结构化表单（考点多选/难度数值/预期复杂度/数据规模/背景/备注，**不含 SPJ 维度**）与纯文本两种输入；支持站内链接引用与难度相近题抽取；上传文件须对纯文本模型提示"无法观看图片"；AI 产出预填"新增/编辑题目"表单供人审改（详见 §6.1）。
6. **banned 会话语义**（dec-0f895a1ddd678090）：被 ban 后已登录会话**立即失效**——每次请求实时查库校验角色，被 ban 后下一次请求即 403。
7. **存储方案**（同 dec）：**全 JSON 文件**（题目每题一 JSON；用户/提交/日志目录化 JSON；reset 删目录重建，详见 §4）。
8. **开工**（同 dec）：9.2 晚提前铺环境（venv/依赖/目录骨架），D1 直接进入公共骨架编码。

**假设（未获用户否定前按此推进）：**
4. **环境**：Windows 上开发，WSL2 + Ubuntu 做评测测试（Ubuntu 尚未安装，列入环境搭建首日）。
5. **仓库**：GitLab 作业仓库尚未创建/未知 → 先在 `E:\程序\python\大作业-2` 本地 `git init` 并搭骨架，仓库可用后按 gitpull 教程关联 remote（origin 指向作业仓库；upstream 指向助教示例仓库拉更新）。

**待用户提供**：AI 模块联调用的大模型 API key（OpenAI 兼容端点 + 模型名，暂无则本地 mock 打通流程）；GitLab 作业仓库 URL；第一次大作业验收形式细节（供 9.10 演练参考）。

---

## 附录 A：各 Step 页面内部评分权重（来源：各 project/step* 页面"评分细则"，供投入优先级参考）

| 模块 | 内部评分点 | 权重 |
|---|---|---|
| Step 1 | 题目列表/详情 API 3 + 题目增删改 API 2 | 5 |
| Step 2 | 多语言评测 2 + 动态注册语言 1 + 语言列表查询 1 + 时间/内存限制实现 1 | 5 |
| Step 3 | 评测列表 2 + 详情 2 + 重新评测 1 | 5 |
| Step 4 | 用户注册 2 + 用户信息 1 + 权限变更 1 + 用户列表 1 | 5 |
| Step 5 | 日志记录与查询 2 + 日志/测例权限管理 2 + 审计与安全说明 1 | 5 |
| Step 6 | 用户页面组 2 + 题目页面组 1 + 评测提交页面组 1 + 前后端对接 1 | 5 |

> 说明：Step2 为全项目技术难点核心（评测器正确性影响 Step3/5 与整体演示）；Step4 是全部鉴权前提。官方 Step 编号与依赖关系不一致，实际开发顺序见 WORK_PLAN。
