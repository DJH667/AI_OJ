# 实验二 OJ —— 工作进度计划 v2（2026-09-02 修订）

> 依据用户 9.2 决策（decision dec-64d607b21978d527）重排：
> ① 砍掉专门"熟悉日"，开发时段（每日约 3h）专注功能开发，**阶段熟悉由用户另出时间完成**；
> ② 周末（9.5/9.6）各加时至 4–6h；
> ③ 基础六步 30 分为硬保底，AI 智能命题冲完整 10 分。
> 验收：9.10（周四）课前提交最后一次 git commit 号 → 当天助教线下验收 → 当晚 23:59 前交实验报告 PDF。

---

## 1. 总盘与策略

- **主轨道（必达，40 分）**：公共骨架 → Step4 用户 → Step1 题目 → Step2 评测 → Step3 评测管理 → Step5 日志审计 → Step6 前端 → 回归走查。
- **并行轨道（冲刺 10 分）**：AI 智能命题（R1–R4 + 质量打磨），利用 D5–D7 每日开发末尾的 +0.5–1h 缝隙与 9.9 晚/9.10 上午弹性推进；**若主轨道 9.9 前未全绿，AI 自动收缩为 R1–R4 最小闭环（保底约 4–5 分），基础优先**。
- **开发顺序说明**：Step4（用户/Session/权限依赖）先于 Step1–3，使后续所有接口一次带鉴权、避免 Step4 后返工回填（验收点不变，官方 Step 编号只是文档顺序）。
- **熟悉机制（用户另出时间）**：每阶段结束在 `docs/` 产出《实现说明 + 代码导读 + 自测用例清单》；每日开发开始时用 5–10 分钟过一遍前日交付与您的疑问（不占开发主体时间）；开发中您可随时在场提问。

## 2. 时间账

| 日期 | 时段 | 主轨道 | AI 缝隙 |
|---|---|---|---|
| 9.3（四）D1 | 3h | 环境 + 公共骨架 | — |
| 9.4（五）D2 | 3h | Step4 用户系统 | — |
| 9.5（六）D3 | 4–6h | Step1 + Step2 主体 | — |
| 9.6（日）D4 | 4–6h | Step2 收尾 + Step3 | +0.5h |
| 9.7（一）D5 | 3h | Step5 日志审计 | +0.5h |
| 9.8（二）D6 | 3h | Step6 前端（用户+题目组） | +0.5h |
| 9.9（三）D7 | 3h | Step6 完成 + 全量回归 | +1h |
| 9.10（四）D8 | 课前 | 演练 + 最终 commit | 收尾 |
| 9.10 晚 | — | 实验报告 PDF（23:59 截止） | — |

主轨道合计 ≈ 24–28h；AI 合计可挤 ≈ 4–6h（含 9.9 晚/9.10 上午弹性）。**核心风险：主轨道若超时，AI 质量打磨被牺牲——D6/D7 每天先核对主轨道进度再决定 AI 投入。**

## 3. 分日详细任务

### D1 9.3（四）环境 + 公共骨架（3h）
- **用户侧（当天第一件事，可并行）**：安装 WSL2 + Ubuntu（需管理员权限，可能要重启）；装好后 `sudo apt install g++ python3 python3-venv`，验证 `python3 --version` 与 `g++ --version`。若当天未就绪：Windows 侧先跑通除"评测执行"外的全部，D4 前补验即可。
- **目录结构（前后端分离，官方 Step6 任务 4）**：仓库内分 `backend/`（FastAPI 源码）与 `frontend/`（Streamlit app.py）；后端 `uvicorn` 起在 8000 端口，前端 `streamlit run` 起在 8501 端口，仅经 REST API + Cookie 会话交互（架构约定见 PROJECT_REQUIREMENTS §1.1）。
- **我侧**：`E:\程序\python\大作业-2` 建 venv + `requirements.txt`（fastapi uvicorn pydantic streamlit bcrypt psutil httpx pytest python-multipart）；确认 git 仓库与 `.gitignore`（排除 venv/`__pycache__`/数据目录/密钥）。
- **公共层**：统一响应 `{code,msg,data}` 工具；全局异常处理器（顺序 401>403>400>429>409>404>500，422→400）；存储目录规划（`problems/ users/ submissions/ logs/`，JSON 文件持久化，实现方案 D2 敲定）；`POST /api/reset/`；启动钩子创建初始管理员 `admin/admintestpassword`。
- **交付**：`uvicorn` 可启动、`POST /api/reset/` 可调用；`docs/` 更新《D1 实现说明与导读》。
- **自测**：reset 返回 `{"code":200,"msg":"system reset successfully","data":null}`；错误响应各状态码抽样验证。

### D2 9.4（五）用户系统 = 官方 Step4（3h）
- 存储与加密：users 持久化、bcrypt 密码；SessionMiddleware + uuid4 + 服务端 session（登出清除、可设过期）；banned 再登录拒 403。
- 接口：注册（用户名 3–40、密码 ≥6、唯一 400）、登录/登出、`GET /api/users/{id}`（本人/管理员）、`GET /api/users/`（管理员分页）、`PUT /api/users/{id}/role`（含权限操作日志）、`POST /api/users/admin`。
- **权限依赖**（供 Step1–3 直接复用）：`get_current_user` / `require_admin`。
- 交付：curl/pytest 自测脚本全绿 + 导读文档。熟悉重点：Session 原理、bcrypt、FastAPI 依赖注入做鉴权。

### D3 9.5（六）题目管理 Step1 + 评测 Step2 主体（4–6h）
- **Step1**：Problem 模型（pydantic，必选/可选、类型校验、默认字段 str→""/list→[]）；JSON 存取（id→文件）；5 个 CRUD 接口带鉴权（删除仅管理员、409 id 已存在、PUT 的 body id 与路径一致）；**AI 扩展字段 `difficulty_score`(float，可选) 一并纳入题目模型**；预置 2 道示例题（含边界与卡规模测例，其中 1 道带 difficulty_score 供 AI 抽题联调）。
- **Step2 主体**：语言注册表（内置 python/cpp + `POST/GET /api/languages/`，`{src}`/`{exe}` 路径替换）；submissions 存储；评测流程（存码→编译/运行→逐测例→输出归一比对（忽略行末空格与末尾多余换行）→ AC/WA/RE/CE/UNK 映射）；`asyncio.create_task` 异步评测（单用户串行即可）；429（1min >3 次）。
- 交付：Step1 接口自测全绿；python 简单题端到端评测跑通（WSL 或本机 python3）。
- 熟悉重点：题目模型字段、评测状态机、计分（score=通过数×10、counts=总数×10）。

### D4 9.6（日）评测收尾 Step2 + 评测管理 Step3（4–6h）
- **Step2 收尾（★难点）**：资源限制——psutil 内存监控线程（超限 kill→MLE）+ 超时 kill→TLE；error_info 脱敏；**WSL 实测** cpp（先编译 g++）与 python 真实测例（含 time/memory 边界、CE/RE/TLE/MLE 各态）。
- **Step3**：提交列表（一级条件 user_id/problem_id 至少其一、二级 status/page/page_size、分页边界语义、可见性本人/管理员、pending/error 摘要只回 id+status）；详情（pending 至少 id+status）；`rejudge`（仅管理员、覆盖原记录、回 pending）。
- 交付：评测器 WSL 实测记录（报告素材）；Step3 自测全绿。
- 熟悉重点：subprocess+asyncio、资源限制实现、筛选/分页边界语义。

### D5 9.7（一）评测日志 Step5（3h，AI +0.5h 可选）
- 评测时记录每测例 `details[{id,result,time,memory}]`；`GET .../log`（本人/管理员；题目 `public_cases=True` 时公开 details；公开日志≠公开 Step2/3 简单结果）；`PUT /api/problems/{id}/log_visibility`；access 审计（action=`view_log`、status 记录拒绝、不记 未登录/不存在/参数错误）。
- **AI 起步（+0.5h）**：`/api/ai/*` 路由骨架 + model-config 持久化（密钥脱敏存储、响应不回显明文）+ 命题需求数据模型（结构化/纯文本两类，字段见需求文档 §6.1）。
- 交付：Step5 自测全绿（含可见性三态：本人/管理员/公开后他人）。
- 熟悉重点：日志裁剪与可见性、审计"只记已鉴权的访问结果"。

### D6 9.8（二）前端 Step6 上半（3h，AI +0.5h 可选）
- Streamlit `app.py`：统一 API client（Session cookie 传递、code/msg 展示、401/403/429 友好提示）；用户页面组（注册/登录/登出/信息展示/用户管理——仅管理员可见）；题目页面组（列表/详情/新增/编辑/删除，表单预检与后端校验一致）。
- **回归第 1 轮**：对照 PROJECT_REQUIREMENTS §5 逐接口脚本化验证 + reset 全流程。
- **AI（+0.5h）**：任务队列抽象（等待/执行/完成/中断/失败）+ 建任务/查任务接口 + 站内参考题抽取（站内题目链接解析、按 difficulty_score 邻域抽相近题作为模型上下文）。
- 交付：前端用户+题目组可用；回归清单记录。

### D7 9.9（三）前端 Step6 完成 + 全量回归（3h，AI +1h）
- 评测与提交页面组：提交代码、记录列表、详情轮询（pending→结果、编译信息/运行错误/TLE 等明确展示）、日志页（区分"无权限看 details"与"公开可见"两种渲染）。
- 全流程走查：管理员/普通用户/越权场景（401/403/429/404/409）+ reset；截图收集（报告素材）。
- **AI 冲刺（+1h，可延至晚间）**：结构化表单与纯文本两种命题输入界面（纯文本支持上传文件并对纯文本模型提示"无法观看图片"）；执行中持续进度渲染 + cancel 真正中断；R4 token/费用统计展示；AI 产出解析为题目 JSON → **跳转题目"新增/编辑"表单预填**供人审改（复用 Step1 前端）；**合入不晚于今晚**。
- 交付：基础功能全部可用；AI 最小闭环可演示（若主轨道未全绿则 AI 即止于此）。

### D8 9.10（四）验收日
- 课前：按验收要点演练 2 轮（管理员流程、普通用户流程、越权与异常、评测演示、reset 清场）；提交**最后一次 commit 号**到网络学堂。
- 白天/晚上：实验报告 PDF 成稿（23:59 截止）——系统功能与设计 2 / 关键实现与难点 2 / 成果展示 1 + **AI 使用说明**（工具链、工作流、Vibe Coding 代码比例——本作业全程人机协同，必写）。

## 4. AI 智能命题冲刺计划（并行轨道，目标完整 10 分）

| 分项 | 内容 | 排期 |
|---|---|---|
| R2 模型配置 | provider_url/model/api_key + 输入输出单价与计价单位；密钥脱敏；配置实际用于请求 | D5 起步 |
| R4 Token 与费用 | 按任务记录 input/output token，费用公式=输入/单位×单价 + 输出/单位×单价；页面展示并注明计价依据 | D6–D7 |
| R3 进度与中断 | 轮询或 SSE 持续进度；`cancel` 真正终止后台任务并显示"已中断" | D7 |
| R1 界面与衔接 | 两种输入界面：① 结构化表单（考点多选+其他自定义/难度数值档位/预期复杂度/数据规模/情景背景/备注）；② 纯文本（可引用站内链接、上传本地文件，纯文本模型提示无法看图）；站内参考题（difficulty_score 邻域抽取）随需求送入上下文；AI 产出结构化题目 JSON → 跳转题目新增/编辑表单**预填**供人审改 | D5–D7 |
| 质量打磨（2+2+2） | prompt 保证题目贴合知识点/难度；测试用例生成器含边界与规模区分（可淘汰暴力算法）；易用性 | 9.9 晚 / 9.10 上午弹性 |
| 降级预案 | 主轨道 9.9 未全绿 → 只保 R1–R4 四项各 1 分（约 4–5 分），质量维度放弃 | 自动触发 |

无 API key 期间用本地 mock（OpenAI 兼容响应返回固定 JSON 结构）先打通全流程，key 到位后仅替换 client 端点。

> 命题界面字段、站内参考题抽取与产出预填的完整设计见 PROJECT_REQUIREMENTS.md §6.1（用户决策 dec-7b47335beaa64320）。

## 5. Git 与文档纪律

- 提交遵循 Conventional Commits：`feat(step4): ...` / `fix(judge): ...` / `docs: ...`；每天至少一次 commit；**禁止提交大文件（.gitignore 覆盖数据/密钥/venv）**。
- 每阶段在 `docs/` 落两份产物：《需求偏差标注》与《实现说明 + 代码导读 + 自测清单》（您的熟悉材料）；git 提交按阶段推进，便于您逐 commit diff 阅读。
- GitLab 作业仓库就绪后：`git remote add origin <作业仓库URL>`、`git remote add upstream <助教示例仓库>`，按 gitpull 教程拉取更新（认证用 GitLab Personal Access Token）。

## 6. 待您提供/准备

1. **WSL2 + Ubuntu 安装**（D1 当天，需管理员权限，可能重启；已列入首日第一件事）。
2. **GitLab 作业仓库 URL**（助教创建后给，仓库未建前本地开发不受阻）。
3. **大模型 API key**（OpenAI 兼容端点 + 模型名；暂无则本地 mock 先行）。
4. 第一次大作业的验收形式细节（供 D8 演练对齐）；网络学堂报告入口位置。

## 7. 主要风险与预案

- **主轨道超时** → D6/D7 每天优先核对主轨道；AI 收缩为 R1–R4 闭环。
- **WSL2 安装失败/重启** → 开发不阻塞：评测器逻辑先在 Windows 用 python3 验证，D4 前在 WSL 补真实资源限制实测。
- **Windows Python 3.14 依赖无 wheel** → 主环境切到 WSL python3（3.12）venv；Windows 只保留编辑与文档。
- **验收形式与假设不符** → D8 演练脚本按"Linux 自动评测 + 人工走查"双通道准备（自动评测只依赖标准接口 + reset，人工看演示与代码）。
