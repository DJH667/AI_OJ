# 评审发现与处理记录（Review Findings Log）

> 约定（2026-09-05 起）：每轮评审产出的**问题与建议**，除写入 `/comments` 评审文件外，
> 同步登记到本文件；处理后回填"状态 / 对应提交"。按日期倒序维护，未关闭项始终可见。

---

## 2026-09-09 · 全量对标检查（对应 `comments/2026-09-09-review-full-check-1d3925e.md`）

结论：基础六步 + AI R1–R4 主体完成；**P1：log_visibility 无前端入口（必改）**；P2：access 审计无前端页、§6.1 参考题链接解析/邻域抽取未实现、普通用户无直接编辑入口（待拍板）；P3 若干。

| # | 级别 | 问题 | 建议 | 状态 |
|---|---|---|---|---|
| 1 | P1 | `PUT log_visibility` 后端有、前端无入口 | 题目管理/详情加管理员"日志公开"开关 | ✅ 已处理 `5ab8054`（题目管理卡片 toggle + 后端 GET 查询接口） |
| 2 | P2 | `GET /api/logs/access/` 无前端查看页 | 管理员加审计页 | ✅ 已处理 `5ab8054`（个人中心管理员区"访问审计"） |
| 3 | P2 | §6.1 纯文本站内链接解析 + difficulty_score 邻域（±1）抽题未实现 | 补实现或按基础优先放弃并文档标注 | ✅ 用户拍板保持现状；文档 §6.1/§9 已按现状如实化，前端删"可附站内题目链接" |
| 4 | P2 | 普通用户前端仅"申请-审批"改题，无直接编辑（后端 PUT 开放） | 与验收口径对齐 | ✅ 已处理：管理员个人端"允许普通用户编辑"开关（默认开）；关闭时后端 PUT/编辑申请 403、前端编辑入口禁用 |
| 5 | P3 | `POST /api/users/admin` 无前端入口 | 加按钮 | 待处理 |
| 6 | P3 | `review` 与需求 `needs_review` 命名不一致 | 统一命名 | ✅ 已处理：官网原文未证 needs_review（出自 9.5 问答定稿），代码保留 review，文档统一为 review |
| 7 | P3 | mock 模式任务页未标注"模拟用量" | 加说明 | ✅ 已处理（用户口径：mock 不改；自定义模型可选填单价，留空时费用估算显示"未知"） |
| 8 | P3 | applications/notifications/scope=all 扩展接口未在需求文档登记 | §9 补 polish 扩展清单 | 待处理 |
| 9 | P3 | 示例题 P1000/P1001 与自动评测建题 id 冲突风险 | 验收前复核 | 待复核 |
| 10 | P3 | 题目管理页删除文案与审批流不一致 | 改文案 | ✅ 已处理 `5ab8054` |

---

## 2026-09-08 · 当前状况评审（对应 `comments/2026-09-08-review-current-077e79e.md`）

结论：✅ HEAD `077e79e` 全量 75 passed、工作区 clean、已推送 `github.com/DJH667/AI_OJ`（main，68 提交）。

| # | 级别 | 问题 | 建议 | 状态 |
|---|---|---|---|---|
| 1 | P2 | 启动自动种入示例题 P1000/P1001（reset 不回种、重启恢复）：若自动评测用同 id 建题会 409 | 验收前用真实评测脚本复核；文档说明可用 `OJ_SEED_DEMO=0` 关闭 | 待验收复核 |
| 2 | P2 | 前端"普通用户改/删走申请-审批流"（applications，9.8 polish）：后端 PUT/DELETE 的 api.md 语义未变，需确认演示口径（api.md 走查 vs 审批流演示） | 与验收预期对齐并在演示脚本中明确 | 待确认 |
| 3 | P3 | access 审计文件名同微秒碰撞 / 响应形态 | 文件名已加随机后缀（2026-09-09）；响应形态保持数组契约（现有测试一致），D7a 终核 | 🟡 文件名已修 |
| — | 台账 | 9.7 本文件曾有两处重复旧表 + AI Phase2 #3 误记 require_admin（实际 per-user） | #3 已更正；重复旧表已清理（2026-09-09） | ✅ 已清理 |

---

## 2026-09-05 · D4 计划评审（对应 `comments/2026-09-05-review-D4-plan-1524d10.md`）

| # | 级别 | 问题 | 建议 | 状态 |
|---|---|---|---|---|
| 1 | P2 | 全量测试 flaky：`test_compile_error_cpp` 报 `FileNotFoundError`（1/2 轮；单测通过、复跑 46 passed） | 定位后台评测任务跨用例竞态；测试夹具 teardown 收敛后台任务 | ✅ 已修（d3_judge/d4 fixture teardown `_drain_judges`：等待 pending 消失或稳定 3s）；6/7 轮全绿，残余偶发未复现 → 9.6 复测观察 |
| 2 | P2 | D4 计划未写 rejudge 统计口径（不新计 submit_count、resolve 只增不减）——官方未定义 | 口径落档（已记入 d4-implementation-notes §3.5）并列入待助教确认 | ✅ 用户判定（9.5）：评测/重评后实时重算用户统计——已实现 `recompute_stats`（submit=现存提交数、resolve=AC 去重，rejudge 实时回退），测试覆盖；需求 §5 Step3 与 ta-qa Q6 回填 |
| 3 | P2 | Q5（CE 状态归属 success/error）排期偏晚，Step3 摘要裁剪对其敏感 | 提前到 9.6 拿答复，避免 9.8 回归返工 | ✅ 用户判定（9.5）：CE 归 **error**——judge CE 分支已改（compile_info 保留、score/counts=0），CE 测试更新，无需再问助教 |
| 4 | P3 | 时间账"等效原计划"列不准确：D4 行应为"原 D4"，D5 行应为"原 D5 + AI 对齐" | 修正 WORK_PLAN v3 时间账表 | ✅ 已修（WORK_PLAN v3 时间账列修正，D4 标完成） |
| 5 | P3 | "MLE 样例记录（报告素材）"无独立落地，仅有 pytest 用例 | 补截图 + submission JSON 摘录存档 | 🟡 骨架已建 `reports/report-assets.md`（复现命令 + JSON 摘录）；截图于 D7a 素材收集日补齐 |

---

## 2026-09-07 · AI 后端 Phase2 评审（对应 `comments/2026-09-07-review-a981671.md`）

| # | 级别 | 问题 | 状态 |
|---|---|---|---|
| 1 | P1 | `model-config` 省略可选计价字段 → 500 | ✅ 已修：`or` 默认兜底 + `test_model_config_minimal_request_ok` |
| 2 | P1 | 普通任务 cancel 不生效（最终 completed） | ✅ 已修：pipeline `_guard_interrupted`（写状态前读最新任务、中断不再被覆盖）+ `test_task_normal_cancel_effective` |
| 3 | P2 | model-config 全局配置权限口径 | ✅ 已处理：**per-user**（用户判定 9.7 `e49bcd6`，改为每人自存配置，非 require_admin；本条此前误记为 require_admin，9.8 更正） |
| 4 | P3 | POST 后 submit_count 滞后到评测完成 | ✅ POST 保存 pending 后立即 recompute（幂等、评测完成再算） |
| 5 | P3 | judge error 分支未清 score/counts/compile_info | ✅ 兜底清零 |
| 6 | P3 | llm_client 半截配置 KeyError | ✅ 转 LLMError（provider_url/model 缺失检查） |
| 7 | P3 | access 审计文件名同微秒碰撞 / 响应形态 | ✅ 文件名加随机后缀（2026-09-09）；响应形态保持数组（与现有测试/契约一致），D7a 终核 |
| 8 | P3 | next_task_id 无锁 + 死代码 | ✅ 死代码清理（judge `ACCEPTED_VERDICTS`、pipeline 重复 get）；无锁属单进程安全，已注明 |

> 基础部分（Step5/Q5/Q6/flaky）评审确认 ✅；全量 63/63。

---

## 2026-09-07 · 一键启动脚本评审（对应 `comments/2026-09-07-review-start-script-9cba4ba.md`）

| # | 级别 | 问题 | 状态 |
|---|---|---|---|
| 1 | P2 | `:wait_loop` 无超时（启动失败会死循环） | ✅ 已修：计数 40 轮后报错并提示查看 backend.log 尾部 |
| 2 | P2 | 无端口占用检测（8000 残留会连错后端） | ✅ 已修：启动前探活 8000/8501；8000 在线则复用并提示、8501 占用则报错退出 |
| 3 | P3 | 浏览器过早打开 | ✅ 已修：延迟 4s 打开浏览器（后台 opener），随后前端前台运行 |
| 4 | P3 | 文档称可"关窗口停后端"，实为后台无窗口 | ✅ 文档统一为 `stop.cmd`（README/USER_GUIDE 更新） |
| 5 | P3 | 依赖预检不完整 | ✅ 增加 `import fastapi,uvicorn`（WSL venv）与 Windows `.venv\Scripts\streamlit.exe` 存在性检查 |
| 6 | P3 | 盘符仅 C:–G: | 🟡 保持自动映射 C:–G:（当前 E: 无碍）；错误提示引导手动方式（wslpath 捕获中文在 GBK cmd 不可靠，故不用） |
| 7 | P3 | `--host 0.0.0.0` 局域网可达 | ✅ 改 `127.0.0.1`（WSL2 localhost 转发已验证可达） |
| 8 | P3 | `pkill -f uvicorn` 可能误杀 | ✅ stop.cmd 精确匹配 `uvicorn main:app --port 8000`；start-backend.sh 另写 backend.pid 备用 |
| 9 | P3 | `.gitattributes` 未声明 `*.cmd` | ✅ 已加 `*.cmd text eol=crlf` |
| 10 | P3 | backend.log 无限增长 | ✅ 每次启动截断（`: >`） |

> 结论：脚本可直接使用；P2 已按"验收前必改"处理，v5 实测通过（后端就绪→前端 8501 启动）。

---

## 2026-09-09 · 并行打磨线协同与测试稳定性（dec-b0783065772ed895）

| # | 事项 | 处理 |
|---|---|---|
| 1 | 仓库出现 djh 于 9.7–9.9 并行提交的打磨功能（题目申请/删除审批、通知中心、千问直连、AI 监控页、流式 token 估算与任务列表、JSON 失败反馈重试、hint 分离、注册后 Cookie 修复、Windows 并发写退避、本题不考虑复杂度等，origin=GitHub AI_OJ） | ✅ 归属已明确：**打磨部分由用户新对话完成**（本协作任务职责止于"骨架/Demo 生成"）；打磨功能**纳入验收与报告口径**（不深改） |
| 2 | 工作区 main.py 未提交挂载 notifications 路由 | ✅ 已提交（232bdae，用户确认 dec-b0783065772ed895） |
| 3 | 全量测试顺序性 flaky（单测绿；全量偶红 test_polish_notifications / 偶发 test_d6_ai，服务端偶发 `GET /api/ai/problem-tasks/ai-task-1` 500；82 用例中 79 稳定绿） | 🟡 按用户指示**暂不修，仅记录**；验收（9.10）前需连续两轮全绿，否则交打磨侧或当场定位 |

---

## 历史已关闭项（简表）| 日期 | 问题 | 处理 |
|---|---|---|
| 2026-09-04 | D3 P1 resolve/submit 并发竞态 | ✅ 全局串行锁（`634720a`） |
| 2026-09-04 | D3 P2 languages 列表顺序/鉴权 | ✅ 按内置顺序 + 登录鉴权（`634720a`） |
| 2026-09-04 | D3 Q1 reset 鉴权与自动评测调用方式 | ✅ 自动评测先登录 admin（用户确认，默认 True） |
| 2026-09-03 | D1 P1 500 兜底、P2 损坏文件日志、P3 conftest | ✅ 已闭环 |
| 2026-09-03 | D2 P3 save_json 原子写 | ✅ `tmp + os.replace`（`93a75e8`） |
