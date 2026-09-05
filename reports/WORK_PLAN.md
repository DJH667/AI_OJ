# 实验二 OJ —— 工作进度计划 v3（2026-09-05 修订，加速版）

> 依据：① 9.2 决策（dec-64d607b21978d527：砍专门熟悉日 / 周末加时 / 基础保底 AI 冲 10）；
> ② 9.3 用户指示 AI 先挂起待对齐（后于 9.5 dec-f5d32ddffe9a354c **恢复纳入新排期，尽快对齐**）；
> ③ 9.5 用户实测反馈："一天可以做两天的事，原估算偏保守"——本版按加速节奏重排。
> 验收：9.10（周四）课前提交最后一次 commit → 当天线下验收 → 当晚 23:59 前实验报告 PDF。

---

## 0. 进度快照（截至 2026-09-05）

| 计划日 | 状态 | 对应提交 |
|---|---|---|
| D1 公共骨架（9.3 前） | ✅ | 5bdd95f / f4ea57b(评审) |
| D2 用户系统 Step4（9.3） | ✅ | 0a83e28 |
| D3 Step1 题目 + Step2 评测主体（9.3–9.4） | ✅ | 83e500c / 634720a(评审) |
| 评审处理与助教澄清 | ✅ | 各 docs/fix 提交 |

**剩余工作**：Step2 收尾(MLE) + Step3（5 分）→ Step5（5 分）→ Step6 前端（5 分）→ 回归/演练/报告（5 分）→ AI（10 分，对齐后冲刺）。基础 30 分功能预计 **9.8（周二）前收尾**，9.9 留给 AI 与报告，9.10 上午演练提交。

## 1. 时间账（加速版：1 天 ≈ 原 2 个计划日）

| 日期 | 内容 | 等效原计划 |
|---|---|---|
| 9.5（六）晚 | **D4** ✅（commit 1524d10）：Step2 收尾（psutil → MLE/真实 memory）+ Step3（列表/详情/rejudge） | = 原 D4 |
| 9.6（日） | **D5**：Step5（日志/可见性/access 审计）+ **AI 对齐 1h**；⚠ 开工前向助教确认 **Q5（CE 状态归属）** 答复 | = 原 D5 + AI 对齐 |
| 9.7（一） | **D6a**：Step6 前端三组页面主体 | = 原 D6 + 原 D7（前端合并） |
| 9.8（二） | **D7a**：Step6 联调收尾 + **全量回归 + 边界用例** + Q5 答复回填 + 报告素材收集 | = 原 D8 预备 + 评审闭环 |
| 9.9（三） | **AI 冲刺**（R1–R4 + 质量打磨）+ 实验报告成稿 | = AI + 报告 |
| 9.10（四） | 上午：演练 2 轮 + 最终 commit；晚上：报告 PDF（23:59 截止） | 验收日 |

> 缓冲与取舍：若 9.7 前端或 9.8 回归出现超时，**AI 自动收缩为 R1–R4 最小闭环（保底 ~4–5 分），基础与报告绝不挤占**；
> 9.6 的 AI 对齐若未完成，顺延至 9.7 晚/9.8 晚各 30 分钟碎片完成（对齐议题见 reports/ai-alignment-notes.md，8 项，不阻塞开发框架）。

## 2. 分日详细任务（已完成日见 reports/d1–d3-implementation-notes.md）

### D4 9.5（六）晚 — Step2 收尾 + Step3 评测管理（官方 5 分）
- **Step2 收尾**：psutil 内存监控线程（超限 kill → MLE）；测例 details 记录真实 `memory`（MB）与 `time`；WSL 下构造超内存样例验证。
- **Step3**：`GET /api/submissions/` 列表（一级条件 user_id/problem_id 至少其一、二级 status/page/page_size、分页边界、可见性 本人/管理员、pending/error 摘要只回 id+status）；`GET /api/submissions/{id}` 详情（pending 至少 id+status）；`PUT /api/submissions/{id}/rejudge`（仅管理员、覆盖原记录、回 pending，复用 judge 串行锁）。
- 交付：Step3 三接口自测全绿；MLE 样例记录（报告素材）。
- 熟悉重点：筛选/分页边界语义、评测可见性、rejudge 语义。

### D5 9.6（日）— Step5 评测日志（官方 5 分）+ AI 对齐（1h）
- 评测完成即持久化测例 `details`；`GET /api/submissions/{id}/log`（本人/管理员；题目 `public_cases=True` 公开 details；公开日志 ≠ 公开 Step2/3 结果）；`PUT /api/problems/{id}/log_visibility`；`GET /api/logs/access/` 审计（action=`view_logs`；**user_id/problem_id 至少其一、全空 400**（助教确认）；status 记录拒绝；不记 未登录/不存在/参数错误）。
- **AI 对齐**：按 ai-alignment-notes 8 项议题逐项定案（界面范围/参考题/OpenRouter/计费口径/任务与中断/产出衔接/演示/裁剪），回填后恢复排期。
- 交付：Step5 自测全绿（可见性三态）；对齐结论回填。

### D6a 9.7（一）— Step6 前端三组页面（官方 5 分）
- Streamlit `frontend/app.py`：统一 API client（Session cookie、code/msg 展示、401/403/429 提示）；
  用户组（注册/登录/登出/信息/管理仅管理员）、题目组（列表/详情/新增/编辑/删除，表单预检与后端一致）、评测组（提交/列表/详情轮询/日志区分公开与无权限渲染）。
- 交付：三组页面可用（后端 9.8 前保持全绿以便联调）。
- 熟悉重点：streamlit 组件、session_state、前后端分离对接（REST + Cookie）。

### D7a 9.8（二）— 联调收尾 + 全量回归 + 报告素材
- 全流程走查：管理员/普通用户/越权（401/403/429/404/409）+ reset；HTTP 冒烟（uvicorn+curl 提交→轮询成功）。
- 逐接口回归对照 PROJECT_REQUIREMENTS §5；截图/边界用例收集（报告素材）；助教 Q5（CE 状态）答复回填。
- 交付：基础六步功能全部可用；回归清单与素材入库。

### AI 冲刺 9.9（三）— AI 智能命题（10 分，对齐后按定案实施）
- 后端：model-config（OpenRouter，密钥脱敏、配置实际生效）、任务状态机（等待/执行/完成/中断/失败）、进度轮询/SSE、cancel 真实终止、Token/费用统计（R4）。
- 前端：结构化表单与纯文本输入、站内参考题（difficulty_score 邻域）、产出 → 题目新增/编辑表单预填（R1）。
- 质量：prompt 贴合知识点/难度、测例含边界与规模区分；演示走查。
- 降级预案：若 9.8 基础未全绿，只保 R1–R4 闭环（约 4–5 分）。
- **同日**：实验报告初稿成稿（系统功能与设计/关键实现与难点/成果展示/AI 使用说明），素材取自各日 notes 与截图。

### D8 9.10（四）— 验收日
- 课前：演练 2 轮（管理员/普通用户/越权/评测/重置/可选 AI 演示）；提交**最后一次 commit 号**到网络学堂。
- 白天/晚上：报告 PDF 打磨并提交（23:59 截止）。

## 3. AI 智能命题（已恢复排期；对齐在 9.6 进行）
- 完整议题与决策回填：`reports/ai-alignment-notes.md`（8 项）。
- 技术要点（不变，来自 PROJECT_REQUIREMENTS §6/6.1）：OpenRouter（OpenAI 兼容 `/api/v1`）真实调用 + 计费/Token 统计；difficulty_score 服务端私有；产出预填题目新增/编辑表单；界面两形态（结构化/纯文本+上传提示）。
- 无 API key 期间本地 mock 打通流程，key 到位后仅替换 client。

## 4. Git 与文档纪律（沿用）
- Conventional Commits（feat/fix/docs/test）；**禁止大文件/密钥**；每日收尾提交（避免频繁小步）。
- 每阶段 `reports/` 产出《实现说明+导读+自测清单》与《评审处理记录》；关键口径变更集中记入 PROJECT_REQUIREMENTS §9。
- **评审发现**：每轮评审的问题与建议除 `/comments` 外，同步登记 `reports/review-findings.md` 并回填处理状态（2026-09-05 起）。
- 助教问答持续登记：`reports/ta-qa-pending.md`。

## 5. 风险与预案
- **节奏风险**：加速压缩 → 每日仍保留自测与 commit；超时预案见 §1（AI 收缩、报告不挤占）。
- **Q5（CE 状态）待答复**：当前 CE→success；若助教判 error，仅改 judge 状态映射 + 摘要裁剪逻辑（单点）。
- **AI 对齐延迟**：9.6 未对齐则碎片完成；对齐前 AI 后端骨架（model-config/任务队列）可先行（等价接口可替换）。
- **报告素材**：D4–D8 每日 10 分钟截图存档，避免 9.10 突击。
