# 评审发现与处理记录（Review Findings Log）

> 约定（2026-09-05 起）：每轮评审产出的**问题与建议**，除写入 `/comments` 评审文件外，
> 同步登记到本文件；处理后回填"状态 / 对应提交"。按日期倒序维护，未关闭项始终可见。

---

## 2026-09-07 · 新增部分评审（对应 `comments/2026-09-07-review-a981671.md`）

| # | 级别 | 问题 | 建议 | 状态 |
|---|---|---|---|---|
| 1 | P1 | `PUT /api/ai/model-config` 省略可选计价字段（input_price 等）→ `float(None)` 500 | `float(body.get("input_price") or 0.0)` 等 + 最小请求测试 | 待处理 |
| 2 | P1 | AI 普通任务 cancel 不生效：cancel 后最终 status 变回 completed（状态被 RUNNING 覆盖） | `chat()` 返回后先查 `cancel_requested`；interrupted 一旦置位不再被覆盖 | 待处理 |
| 3 | P2 | `model-config` 任意登录用户可改全局共享配置 | 建议仅管理员（`require_admin`），至少文档定案 | 待处理 |
| 4 | P3 | POST 保存 pending 后未立即 recompute_stats，submit_count 延迟到评测完成 | POST 后同步 recompute 一次 | 待处理 |
| 5 | P3 | `judge._JudgeError` 分支未清 score/counts/compile_info/run_info | 兜底清零 | 待处理 |
| 6 | P3 | `llm_client.chat` 半截配置（有 key 缺 url/model）→ `KeyError` | 缺失转 `LLMError` | 待处理 |
| 7 | P3 | access 审计文件名 `时间戳-user_id` 同微秒可覆盖；access 响应形态待终核 | 文件名加随机后缀；D7a 与 api.md 核对 | 待处理 |
| 8 | P3 | `ai_tasks.next_task_id` 无锁（单 worker 理论安全）；`ACCEPTED_VERDICTS` 等死代码 | 低优先清理 | 待处理 |

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
| 3 | P2 | model-config 全局配置权限口径 | ✅ 定案 require_admin（PUT/GET 均仅管理员） |
| 4 | P3 | POST 后 submit_count 滞后到评测完成 | ✅ POST 保存 pending 后立即 recompute（幂等、评测完成再算） |
| 5 | P3 | judge error 分支未清 score/counts/compile_info | ✅ 兜底清零 |
| 6 | P3 | llm_client 半截配置 KeyError | ✅ 转 LLMError（provider_url/model 缺失检查） |
| 7 | P3 | access 审计文件名同微秒碰撞 / 响应形态 | 🟡 记录：D7a 与 api.md 终核（响应如需 total 再补） |
| 8 | P3 | next_task_id 无锁 + 死代码 | ✅ 死代码清理（judge `ACCEPTED_VERDICTS`、pipeline 重复 get）；无锁属单进程安全，已注明 |

> 基础部分（Step5/Q5/Q6/flaky）评审确认 ✅；全量 63/63。

---

## 历史已关闭项（简表）| 日期 | 问题 | 处理 |
|---|---|---|
| 2026-09-04 | D3 P1 resolve/submit 并发竞态 | ✅ 全局串行锁（`634720a`） |
| 2026-09-04 | D3 P2 languages 列表顺序/鉴权 | ✅ 按内置顺序 + 登录鉴权（`634720a`） |
| 2026-09-04 | D3 Q1 reset 鉴权与自动评测调用方式 | ✅ 自动评测先登录 admin（用户确认，默认 True） |
| 2026-09-03 | D1 P1 500 兜底、P2 损坏文件日志、P3 conftest | ✅ 已闭环 |
| 2026-09-03 | D2 P3 save_json 原子写 | ✅ `tmp + os.replace`（`93a75e8`） |
