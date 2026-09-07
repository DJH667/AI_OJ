# OJ 系统使用说明（USER GUIDE）

> 面向：验收演示、日常使用、报告附图。实现与契约详见 `PROJECT_REQUIREMENTS.md`；进度见 `WORK_PLAN.md`。
> 适用版本：2026-09-07 起（基础 Step1–6 + AI 命题全部实现；后端 pytest 63/63）。

---

## 1. 系统架构

前后端分离（官方 Step6 任务 4）：

```
frontend/  Streamlit（端口 8501，进程 A）
     │  REST API + Session Cookie（{code, msg, data}）
     ▼
backend/   FastAPI（端口 8000，进程 B，全 JSON 存储于 backend/data/）
```

- 前端**不直连数据**，一切操作经 `/api/*`；登录态由后端 Session Cookie 维持。
- 评测执行需要 Linux（python3 / g++）：后端与评测请在 **WSL2/Ubuntu** 中运行（venv `~/oj-venv`）。
- Windows `.venv` 含 streamlit，可用于起前端；此时经 WSL2 localhost 转发访问后端。

## 2. 启动步骤

### 2.1 后端（WSL Ubuntu，端口 8000）

```bash
# 首次环境（仅一次）：
wsl python3 -m venv ~/oj-venv
wsl ~/oj-venv/bin/pip install fastapi "uvicorn[standard]" pydantic httpx pytest psutil bcrypt python-multipart

# 启动：
wsl -e bash -lc 'cd /mnt/e/程序/python/大作业-2/backend && ~/oj-venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000'
```

启动钩子自动：建数据目录、创建初始管理员 `admin / admintestpassword`、内置语言 python/cpp。

### 2.2 前端（端口 8501）

```bash
cd /mnt/e/程序/python/大作业-2/frontend
../.venv/Scripts/python.exe -m streamlit run app.py --server.port 8501
```

- 浏览器打开 http://localhost:8501。
- 若前端与后端不在同一地址，设置环境变量 `OJ_BACKEND_URL`（默认 `http://127.0.0.1:8000`）。
- 前端在 WSL venv 运行也可（需该 venv 另装 streamlit）。

### 2.3 测试

```bash
wsl ~/oj-venv/bin/python -m pytest tests -q     # backend/ 目录下；64 passed
```

> polish（2026-09-07）：启动时**自动种入示例题** Hello World（P1000）与 A+B（P1001），幂等导入（缺失才写）。
> `POST /api/reset/` 会清空题库且不回种，重启后端即恢复；测试环境经 `OJ_SEED_DEMO=0` 关闭（conftest 已设置）。

### 2.4 一键启动（推荐）

仓库根双击或运行 **`start.cmd`**：自动在 WSL 起后端（:8000，日志 backend.log）→ 等待就绪 → 起前端（Streamlit :8501）并自动打开浏览器。退出前端后，运行 **`stop.cmd`** 停止后端（后端为后台进程，无独立窗口）。
> 依赖：WSL2 + `~/oj-venv`（见 2.1）与 Windows `.venv`（含 streamlit，见 2.2）。

## 3. 账号与角色

| 账号 | 说明 |
|---|---|
| `admin / admintestpassword` | 初始管理员（系统自动创建，user_id=0） |
| 普通用户 | 登录页"注册"tab 创建，注册成功**自动登录**并进入题库 |

角色：`admin`（全部权限）/ `user` / `banned`（再登录 403，已登录会话**立即失效**）。
重置环境：需以 **admin 登录后**调用 `POST /api/reset/`（清空用户/题目/提交/任务并重建 admin 与内置语言；AI 模型配置不清）。

## 4. 功能走查

### 4.1 用户
- 未登录时显示**全画幅登录/注册页**（登录/注册双 tab）；注册成功自动登录，登录后默认落在**题库**页；
- 侧边栏三项：**题库 / 题目管理 / 个人**（圆角按钮，单击切换），底部退出登录；
- 个人页：信息卡（提交数/通过题/角色/加入时间）+ "查询我的提交记录"入口；**管理员**可见用户列表并可改角色（admin/user/banned）。

### 4.2 题目
- 题库：分页圆角卡片（标题/难度/标签/通过率条，不显示题目 id），悬停变灰，点击进入**题目详情**（二级页）；
- 题目详情：左侧题面（描述/输入输出/样例/限制/提示），右侧栏 = 提交代码 + 近 3 次提交（每 2s 自动刷新）+ "查询提交记录"入口；
- 题目管理（所有登录用户可见）：右上角「AI 命题」与「＋ 新增题目」按钮；支持按编号/标题关键词搜索；每题卡片右侧编辑/删除图标（删除经确认弹窗，**仅管理员**；级联删除该题提交/审计并回退用户统计）；
- 出题表单：time_limit 步进 0.5s、memory_limit 步进 128MB（加减号已放大）；编辑时编号锁定；samples/testcases 用 JSON 编辑（`[{ "input": "...", "output": "..." }]`）。

### 4.3 评测与提交
- 提交：题目详情右侧栏「✏️ 提交代码」→ 选语言 + 大文本框贴代码 → **黄色「🚀 提交评测」按钮** → 异步评测，秒级完成；
- 结果：AC/WA/TLE/MLE/RE/CE；分数 = 通过测例数 × 10；编译/运行/错误信息在提交详情；
- 近 3 次提交：题目右侧栏实时刷新（状态徽章/得分/语言/时间）；
- 查询提交记录（题目右侧栏按钮或个人页进入）：按"全部题目/指定题目"（题目下拉只显示标题，不暴露 id）查自己的记录，时间倒序、分页；**管理员**还可按用户范围查询（含"全部用户"）；
- 重新评测（rejudge）：管理员触发（`PUT .../rejudge`）；
- 限频：同一用户同一题 1 分钟内第 4 次提交返回 429。

**评测日志可见性**（`GET /api/submissions/{id}/log`，助教 Q7）：

| 场景 | 本人 | 其他登录用户 |
|---|---|---|
| 题目未公开（默认） | 可见 score/counts，**无 details** | 403 |
| 题目 `public_cases=True` | 可见完整 details | 可见完整 details |
| 管理员 | 始终完整 | 始终完整 |

`public_cases` 开关：管理员调用 `PUT /api/problems/{id}/log_visibility`（body `{"public_cases": true}`）。审计查询 `GET /api/logs/access/`（仅管理员，需 user_id 或 problem_id 至少一个）。

### 4.4 AI 智能命题（入口：题目管理页右上角「AI 命题」按钮）
1. **模型配置**（折叠面板，per-user）：provider_url（通常 `https://openrouter.ai/api/v1`）、model（需 OpenRouter 有明确计价）、api_key（自己 provider 的或 OpenRouter 分发的）；`input_price/output_price` 填模型**美元单价**（USD/1M tokens）；`fx_rate`（USD→CNY，默认 7.2，可当日按人民银行中间价更新）。**不填 key 时自动走本地 mock**（也可完整演示）。
2. **命题输入**（二选一）：
   - 结构化表单：**语言必选**（=已注册语言下拉）、考点多选（可自定义）、难度分、预期复杂度、数据规模、情景/备注；可选"站内参考题"；
   - 纯文本：自然语言描述（可附站内题目链接、上传文本资料）；若指定未注册语言会被拒绝并提示可用语言。
   - **硬核模式**：勾选后展开"对拍重试次数"（默认 2）；开启则本地执行三代码（生成器/标答/暴力）对拍校验，测试数据错误会回传 AI 重试，用尽标记"需人工复核"。
3. **任务页**：轮询状态（等待/执行/完成/中断/失败），可"刷新"；Token 用量与**费用（CNY）**实时展示（计价依据见面板说明）；可中断运行中任务。
4. **采纳**：命题完成 → "✏️ 采纳到题目编辑" → 自动跳转题目页并**预填**（samples + 全量 testcases，可人工修改）→ 保存后即可提交评测验证。
5. **复核**：对拍用尽的题目不落库，任务显示"需人工复核 + 错误摘要"，可"以相同需求重试（新任务）"。

## 5. 验收演示脚本（约 10 分钟，两通道）

**通道 A：基础功能（管理员 + 普通用户）**
1. 全画幅登录页登录 admin；切「注册」tab 注册 `alice` → 自动登录进入题库；
2. 题库可见种子题 Hello World（P1000）与 A+B（P1001）；如需演示建题：题目管理 → 「＋ 新增题目」（如 P1002，含样例与 5 个测试点，含负数/边界）；
3. alice 提交正确 python → 等结果 → 详情显示 AC（全部测例 ×10）；
4. alice 提交错误代码 → 0/部分分；提交死循环 → TLE；大内存分配 → MLE；
5. alice 看自己的日志：题目未公开 → 只见分数、无 details；admin 打开 `log_visibility` → alice 可见完整 details；
6. 越权演示：alice 访问他人详情/删除题目 → 403；admin 把 alice 设 banned → alice 再操作 403；
7. `POST /api/reset/`（admin 登录）→ 环境复原。

**通道 B：AI 命题（mock 即可演示；有 key 走真实）**
1. 模型配置（mock：不填 key；或填真实 key + 模型 + 价格 + fx_rate）；
2. 结构化表单：语言 python、考点"排序"、难度 6、**预期复杂度 O(n log n)**、数据规模 10^5、勾选**硬核模式**（重试 2）→ 生成；
3. 任务完成展示测试点数与费用（CNY）→ 采纳预填 → 出题表单保存；
4. 提交 O(n log n) 代码 → AC；提交 O(n²) 暴力 → **中小点过 / 大点 TLE → 部分分**（演示测试数据区分复杂度）；
5. （可选）纯文本输入含"用 Java 出题" → 被拒绝并提示可用语言。

## 6. 常见注意（FAQ）

- 评测错误提示不会泄露服务器路径；`error_info` 为空说明无评测级错误。
- 429：同一人同一题 1 分钟超过 3 次提交；换题不触发。
- 删除题目会使相关用户 submit/resolve_count 实时回退（按现存数据重算）。
- rejudge 覆盖原提交重新评测，统计实时重算（Q6）。
- reset 会清空用户/题目/提交/日志/任务并重建 admin 与内置语言；**不会清 AI 模型配置**。
- 数据全部存 `backend/data/`（JSON 文件；已 gitignore，不入版本库）。

## 7. 相关文档索引（reports/）

`PROJECT_REQUIREMENTS.md`（需求与契约基准）· `WORK_PLAN.md`（进度）· `ai-alignment-notes.md`（AI 定案）·
`ta-qa-pending.md`（与助教问答）· `d1–d6-implementation-notes.md`（各阶段实现说明）· `review-findings.md`（评审台账）· `report-assets.md`（报告素材）。
