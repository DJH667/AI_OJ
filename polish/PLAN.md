# polish 计划：OJ 前端打磨（2026-09-07 用户反馈 v1）

> 目标仓库：`E:\程序\python\大作业-2`（对应官方需求 https://dbg-course.github.io/python-docs/oj/）
> 计划存放于 `polish/`，代码直接修改，提交遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/v1.0.0/)。

## 1. 现状理解（读码结论）

- 架构：前后端分离。后端 FastAPI（`backend/`，端口 8000，全 JSON 存储于 `backend/data/`），
  前端 Streamlit 单文件 `frontend/app.py`（端口 8501），仅经 `api_client.py`（httpx + Session Cookie）调 REST API。
- 现有页面组（`PAGES = ["AI 命题", "题目", "评测", "用户"]`，侧栏 `st.radio` 切换）：
  登录/注册在侧栏内（checkbox 切换注册表单，注册后不自动登录）；题目页把"列表 + 新增/编辑表单"混在同一页；
  评测页含"提交代码 + 我的提交记录筛选"；用户页含个人信息 + 管理员用户管理。
- 后端契约要点（api.md / PROJECT_REQUIREMENTS.md）：
  - `GET /api/problems/` 列表仅 `{id,title}`；详情含全字段（含 difficulty/tags）。
  - `GET /api/submissions/`：一级条件 user_id/problem_id 至少其一；普通用户仅能查自己
    （只传 problem_id 时后端归一为"本人该题"）；摘要裁剪 pending/error 仅
    `{submission_id,status}`，其余 `{submission_id,status,score,counts}`；按 submission_id 倒序；分页。
  - 题目 POST/PUT 任意登录用户可用；DELETE 仅管理员（级联 + 统计回退）。
  - `difficulty_score`（float 0–10）为服务端私有隐藏字段：仅 AI 产出/示例题写入，不参与对外 API，
    供 AI 命题抽取"难度相近参考题"（±1 邻域）使用。
- 数据现状：`backend/data/problems/` 为空（demo 无题）；`sample_problems/` 有 aplusb（P1001）、maxn（P1002，带 difficulty_score=3.0）；
  用户有 admin（管理员）与 djh（普通用户）；后端正在运行（backend.pid=467，:8000）。
- 测试基线：后端 pytest 63 通过（官方跑法：WSL `~/oj-venv` 下执行）；前端无自动化测试。
  `test_d3_problems.py::test_add_list_get_defaults` 对题目列表做了**精确相等**断言（`[{id,title}]`），
  `test_d4_step3.py` 仅按键取值断言（附加字段安全）。

## 2. 打磨目标（对照用户反馈 1–7）

1. **登录/注册一体化 + 全画幅登录页**：未登录时隐藏侧栏，居中卡片式登录页（登录/注册双 tab），
   注册成功自动登录并进入题库；登录后默认落点 = 题库。
2. **侧栏设计感 + 单击选择**：侧栏导航改为"圆角矩形按钮"（紫/黄主色调、悬停态、激活态），
   单击即切换（弃用 radio）；"提交评测"等关键按钮与普通按钮颜色区分（黄色）。
3. **题库页**：登录后首页。分页展示所有题目，每题一张圆角卡片（标题/难度/标签/通过率条状图，
   不暴露题目 id）；悬停卡片变灰；空题库显示"当前题库为空"；点击卡片进入题目详情页（二级页面，
   题目 id 仅经 session 传递，不显示）。初始题库种子：Hello World + A+B。
4. **提交记录查询两块**：
   a. 题目详情页右侧栏：近 3 次本人提交 + "查询提交记录"按钮（跳到查询页并预选该题）；
   b. 查询页：按题目（下拉，不暴露 id）查自己该题记录 / 查自己全部记录（时间倒序）；管理员可查所有用户所有记录。
5. **侧栏三项（待定，见 §4 决策 1）**：题库 / 题目管理 / 个人（"查询"入口位置二选一）。
6. **题目管理页**：每题卡片右侧编辑/删除图标；页面右上方"＋ 新增题目"按钮（跳转出题表单，复用现有表单并修复
   time_limit 步进 0.5、memory_limit 步进 128MB、加减号过小）；支持按编号与按标题关键词搜索（仅标题，不匹配内容）。
   AI 命题入口移入本页（"🤖 AI 命题"按钮，与新增题目并排，保留现有两界面与产出预填流程）。
7. **全局美化**：简约风，紫（主）+ 黄（辅）色调，浅灰/留白大块区域；`.streamlit/config.toml` 主题 + 全局 CSS。

## 3. 实施步骤

### 后端（backend/）
- B1 `services/problems.py`：列表视图扩展 difficulty/tags/pass_rate（已定决策 2）。
- B2 `services/submissions.py`：列表摘要附加 problem_id/language/created_at/username（已定决策 2）。
- B3 `db/seed.py` + `main.py` lifespan：启动幂等导入示例题 `helloworld`（新增 `sample_problems/helloworld.json`）+ `aplusb`；
  测试经 `conftest.py` 环境开关关闭（TA 自动评测先 reset，不受影响）。
- B4 同步更新受影响的测试断言；WSL 全量 pytest 回归。

### 前端（frontend/）
- F1 `api_client.py`：无破坏性改动（如需可加 list 便捷方法）。
- F2 全局路由（session state）：`page ∈ {题库, 题目管理, 查询, 个人}` + 二级页
  `view_problem_id`（题目详情）、`manage_action`（新增/编辑表单）、`ai_open`（AI 命题）。
- F3 登录/注册页：全画幅居中卡片（tabs），注册成功自动登录，默认落点题库。
- F4 侧栏：用户信息卡 + 圆角导航按钮（单击切换）+ 退出登录。
- F5 题库页：分页（每页 10）+ 圆角卡片 + 难度徽章 + 标签 chips + 通过率条状（st.progress 或样式化条）+ 空态 + 悬停变灰。
- F6 题目详情页：题面（描述/输入输出/样例/限制/提示/来源/时限内存）+ 右侧栏
  （提交代码入口 → 大文本框 + 语言下拉 + 黄色"提交评测"；近 3 次提交；"查询提交记录"）。
- F7 查询页：题目下拉（含"全部题目"）/ 管理员用户范围下拉；结果表格（题目标题/语言/状态/得分/时间），时间倒序，分页，空态。
- F8 题目管理页：搜索（编号 + 标题关键词）+ 卡片列表 + 编辑/删除图标 + 右上方"🤖 AI 命题"/"＋ 新增题目"；
  出题表单 time_limit step=0.5、memory_limit step=128、放大步进按钮。
- F9 个人页：复用现有用户页并样式化（指标卡、角色徽章、管理员用户管理）。
- F10 全局样式：`.streamlit/config.toml`（紫主色/浅灰底）+ CSS（圆角按钮、导航、卡片悬停灰、黄色提交按钮、放大 number_input 步进）。

### 提交（Conventional Commits，逻辑拆分）
- `feat(backend): ...`（B1/B2/B3 按主题拆分）、`feat(frontend): ...`、`style(frontend): ...`、`fix(frontend): ...`、
  `docs: polish 计划与打磨说明`；每步本地验证（pytest / py_compile / 前后端联调走查）。

## 4. 已定决策（2026-09-07 用户拍板，dec-d92ecd6050f922ce）

1. **"查询"入口**：侧边栏 3 项 = 题库 / 题目管理 / 个人；查询页从题目详情右侧栏"查询提交记录"按钮与个人页入口进入。
2. **数据来源**：后端列表响应附加字段（保留 api.md 契约字段原样）——
   题目列表 +difficulty/tags/pass_rate；提交摘要 +problem_id/language/created_at/username。
3. 题目管理页可见性：按后端契约"任意登录用户可增/改题、仅管理员可删"，页面对所有登录用户可见（删除对非管理员报 403 提示）。
4. AI 命题入口：不占侧栏项，作为"题目管理"页右上方按钮保留全部功能。


## 5. difficulty_score（浮点难度）方案 —— ✅ 已定案：方案 D（2026-09-07 用户拍板）

背景：字段为私有 0–10 浮点，供 AI 命题"±1 邻域参考题"抽取；此前仅 AI 生成时由模型打分。
已实施（`backend/app/services/problems.py::refresh_difficulty`）：

- **先验 prior**（来源优先级）：`difficulty_prior` 存留值 > 出题/AI 提示的 `difficulty_score`（POST/PUT 可选接收，0–10，仅作私有先验不回传）> 难度标签映射（入门 1.0 / 普及- 2.0 / 普及 3.0 / 普及+ 4.0 / 提高 5.5 / 提高+ 7.0 / 省选 8.5 / NOI 10.0）> 默认 5.0；
- **后验 posterior** = `10 × (1 − 通过率)`（通过率 = AC 提交数 / 总提交数）；
- **融合** `score = α·prior + (1−α)·posterior`，`α = 2 / (2 + 提交数)`——无提交取先验，提交越多越收敛到真实通过率难度；
- **刷新时机**：每次评测完成（含 rejudge）后实时刷新；题目新建/编辑后刷新；种子题导入后初始化。
- 两个私有键（`difficulty_prior` / `difficulty_score`）均不回传 API，CRUD 覆盖不丢失。
- 示例：A+B 难度 1.0；djh 提交 1 次 0 分 + 1 次 AC → 通过率 0.5 → score = 0.5×1 + 0.5×5 = **3.0**。

其余备选方案（A LLM 评分规范化 / B 静态特征加权 / C 数据驱动后验 / E 难度标签映射）见 git 历史与评审记录；D = A/E 先验 + C 后验的折中。

## 6. 风险与回退

- 后端附加字段若与 TA 契约测试冲突（精确相等断言）：可快速回退为"方案 B"或仅前端聚合；
  内部测试在 B4 同步更新，保证 pytest 全绿。
- 种子题若影响验收：TA 已确认自动评测先 reset，种子题会被清空，无风险；本地演示需重启后端即恢复。
- Streamlit 无原生"整卡点击/右侧栏"：用按钮卡 + 双列右侧栏 + CSS 悬停实现，行为等价且全部原生组件。
