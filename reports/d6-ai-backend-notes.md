# D6（9.8 晚窗口，Phase2）实现说明与代码导读 —— AI 智能命题后端

> 需求基准：PROJECT_REQUIREMENTS §6/6.2 与 ai-alignment-notes.md（2026-09-05 定稿）。
> 本阶段交付 AI **后端**；前端（Phase3）随 Step6/9.9 推进。

## 1. 交付

| 项 | 状态 |
|---|---|
| `PUT/GET /api/ai/model-config`（登录；key 脱敏、计价字段、reset 保留） | ✅ |
| `POST /api/ai/problem-tasks/`（requirement/language?/problem_id?/hardcore/retry_limit）；任务状态机 waiting/running/completed/interrupted/failed + review 标记；`data/ai_tasks/` 持久化 | ✅ |
| `GET /api/ai/problem-tasks/{id}`（创建者或管理员；progress/usage/cost/对拍状态）；`PUT .../cancel`（终态 409） | ✅ |
| LLM client：OpenAI 兼容真实调用 / 本地 mock 无缝切换（mock 固定题目 JSON + usage） | ✅ |
| ai_pipeline：prompt（题目 JSON schema + 语言规则 + 硬核三代码要求）、解析、语言兜底拒绝、对拍重试闭环、usage/cost 累计 | ✅ |
| 对拍引擎 ai_verify + **runner.py 共享执行原语**（judge 重构复用，支持所有已注册语言） | ✅ |
| 私有字段：meta（语言/生成器/标答/暴力代码）随 result 保留，不进题目对外 API | ✅ |
| pytest **61/61**（D6 新增 6 例） | ✅ |

## 2. 文件

```
backend/app/services/
├── runner.py       # 新增：编译/运行/归一 共享原语（judge 与 ai_verify 复用）
├── ai_config.py    # model-config：存储 data/ai_config.json（reset 不清）、脱敏视图、计价 estimate_cost
├── llm_client.py   # OpenAI 兼容 chat + mock（无 key 时返回固定题目 JSON 与模拟 usage）
├── ai_tasks.py     # 任务状态机 + data/ai_tasks/ 持久化 + 自增 task_id（ai-task-N）
├── ai_verify.py    # 硬核对拍：generator→std→小点 brute 对照；失败 VerifyError（摘要回传 AI）
├── ai_pipeline.py  # 任务执行：组装 prompt/调 LLM/解析/语言校验/对拍重试闭环/usage 累计/中断检查
└── judge.py        # 重构：改用 runner（行为不变）
backend/app/api/ai.py      # model-config + 任务三接口
backend/tests/test_d6_ai.py
```

## 3. 关键实现点

1. **model-config 密钥安全**：api_key 存 data/ai_config.json（data 目录 gitignore、reset 不清）；对外视图仅 `api_key_configured: bool`，任何响应/日志不含明文。
2. **计价（R4）**：`estimate_cost` = prompt/unit×input_price + completion/unit×output_price（unit 默认 1_000_000，OpenRouter 每 1M tokens 定价）；多轮调用 token 累计后统一计费；`currency=USD`；页面需注明计价依据（Phase3）。
3. **mock ↔ 真实**：未配置 api_key 即走 mock（返回固定 A+B 题目 JSON + usage 1200/350）——无 key 也能完整演示全流程；配置 key 后自动切真实 OpenAI 兼容请求。
4. **硬核对拍协议**（ai_verify，仅本地执行）：generator 输出 `[{"input","small"}]` JSON → std 求 expected（非 0/超时/超内存即 VerifyError）→ small 点（small 标记或输入 ≤512 字符）跑 brute 对照 → 不一致即失败摘要（截断、无路径泄露）；通过返回含大小梯度的 testcases（无错误数据）。三段代码均用**所选语言**（经 runner 按语言注册编译/运行）。
5. **重试闭环**：hardcore 首次失败后，把 VerifyError 摘要作为 user 反馈追加再请求；`retry_limit`=额外重试次数（默认 2 → 最多 3 次调用）；用尽 → completed + `review=True` + `review_note`（**题目不入库**）。普通模式（hardcore=False）直接接受 AI 产出 testcases。
6. **语言规则**：结构化必填（API 层校验未注册 → 400）；纯文本产出 language 未注册 → 任务 failed + `language not supported: x; available: ...`（兜底拒绝）。
7. **中断**：`cancel_requested` 标志 + 执行阶段检查；cancel 置 interrupted（终态 409）。

## 4. 自测（Linux WSL）

```bash
wsl ~/oj-venv/bin/python -m pytest tests -q    # 61 passed
```

## 5. 遗留 / 下一步（Phase3 前端，随 Step6/9.9）

- Streamlit：AI 配置页（拉价可选）、命题两界面 + 硬核开关 + 重试调节、任务页轮询/中断/费用、产出预填题目新增/编辑（samples+全量 testcases）、needs_review 复核入口；与 Step6 页面组整合。
- 联调：mock→真实 OpenRouter key（用户提供）；演示素材（O(N log N) 题 + O(N²) 部分分梯度）。
- 素材登记 reports/report-assets.md；AI 使用说明。
