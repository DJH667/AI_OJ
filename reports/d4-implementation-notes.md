# D4（9.5 晚）实现说明与代码导读 —— Step2 收尾(MLE) + Step3 评测管理

> 消化材料。需求基准：PROJECT_REQUIREMENTS §5 Step3 与 §4.2；加速计划见 WORK_PLAN v3。

## 1. 本次交付

| 项 | 状态 |
|---|---|
| Step2 收尾：psutil 内存监控（超限 kill → **MLE**），测例 details 记录真实 `memory` 峰值（MB）与 `time` | ✅ |
| Step3 `GET /api/submissions/`：一级条件（user_id/problem_id 至少其一）→ 400；status 过滤；分页语义；admin 全站/普通用户仅自己；pending·error 摘要只回 id+status | ✅ |
| Step3 `GET /api/submissions/{id}`：仅本人或管理员（他人 403）；404；pending 可 null 字段 | ✅ |
| Step3 `PUT /api/submissions/{id}/rejudge`：仅管理员；覆盖回 pending；复用评测串行锁自动重跑 | ✅ |
| 分页逻辑抽取公共模块（services/pagination.py，users/submissions 共用） | ✅ |
| pytest **46/46**（WSL Linux；含真实 MLE 评测） | ✅ |

> 遗留说明：rejudge 不改动用户统计（resolve 只增不减、重评不重算 submit）——官方未定义，语义记录于此，验收如有出入再调。

## 2. 文件变动

```
backend/app/services/
├── pagination.py    # 新增：分页参数规范化（原 users._normalize_pagination 抽出共用）
├── judge.py         # 新增 _monitor_memory（FAQ psutil 轮询）、_run_case 传 mem_limit；details.memory 记录峰值
└── submissions.py   # 新增 list_records/summary（摘要裁剪）/reset_for_rejudge
backend/app/api/submissions.py   # 新增 GET 列表 / GET 详情 / PUT rejudge
backend/tests/test_d4_step3.py   # 新增 6 用例（MLE/列表筛选可见性/详情/rejudge×2）
```

## 3. 关键实现点

1. **内存监控**（judge.py，FAQ 参考实现）：监控线程每 20ms 用 `psutil.Process(pid).memory_info().rss` 采样，
   超 `memory_limit` 即 `proc.kill()` → 该测例 MLE；同时记录峰值 RSS 供 `details.memory`。
   限制解析链：题目 `memory_limit` → 语言注册默认 → 兜底 128MB；超时 kill 仍优先 TLE。
   MLE 用例验证：题目 memory_limit=16MB + python `bytearray(64MB)` → 实测 MLE 且 memory>0。
2. **评测列表语义**（Step3）：
   - 权限归一：admin 可按任意 user_id/problem_id 查；普通用户传他人 user_id → 403，且只查得到自己的记录
     （`?problem_id=P` 时普通用户仅见自己的该题提交，不是全站）；
   - 一级条件 user_id/problem_id 至少其一（全空 400，`FILTER_REQUIRED`）；status 过滤；排序按提交号倒序（最新在前）；
   - **摘要裁剪**（api.md）：pending/error 条目只有 `{submission_id, status}`；其余 `{submission_id, status, score, counts}`；
   - 分页复用 `services/pagination.normalize_page`（page 有 size 无=400、size 有 page 无=第 1 页、全空=全部、<1=400）。
3. **详情**：仅本人或管理员（普通用户查他人 403、不泄露存在性）；返回 api.md §9 字段集
   （submission_id/user_id/problem_id/language/code/status/score/counts/compile_info/run_info/error_info，
   不含测例 details——测例明细归 Step5 log 接口）；pending 时 compile_info 等可为 null。
4. **rejudge**：`reset_for_rejudge` 把记录覆盖为 pending（score/counts 清零、details/编译运行信息清空）→
   经 `_judge_serial`（全局串行锁）自动重跑 → 覆盖更新。仅管理员；不存在 404。
5. **统计口径备忘**：rejudge 不产生新提交（不计 submit_count）；resolve_count 保持"一题一次、只增不减"
   （重评把唯一 AC 变失败不回溯——官方未定义，验收如有出入单点调整）。

## 4. 自测（已执行，Linux WSL）

```bash
wsl ~/oj-venv/bin/python -m pytest tests -q    # 46 passed（D1 5 + D2 15 + D3 20 + D4 6）
```

## 5. 遗留 / 明日预告（9.6 = Step5 + AI 对齐）

- Step5：评测日志（log 接口/details 可见性 public_cases）、log_visibility、access 审计
  （action=view_logs；user_id/problem_id 至少其一全空 400——助教确认）；
  评测完成即持久化 details（现状 judge 已存，Step5 只加读取/权限）。
- AI 对齐（reports/ai-alignment-notes.md 8 项，~1h）。
- 助教 Q5（CE 状态归属）答复待回填（当前 CE→success）。
- 报告素材：D4 的 MLE/分页/越权截图可归档。
