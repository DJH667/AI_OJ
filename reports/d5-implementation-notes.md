# D5（9.6 提前推进）实现说明与代码导读 —— Step5 评测日志/可见性/审计

> 消化材料。需求基准：PROJECT_REQUIREMENTS §5 Step5（含助教 Q7 精确语义）与 §4.2。
> 加速计划见 WORK_PLAN v3：D5 含 **Step5 + AI 对齐 1h**（对齐部分见 reports/ai-alignment-notes.md）。

## 1. 本次交付

| 项 | 状态 |
|---|---|
| `GET /api/submissions/{id}/log`：可见性三态（Q7 精确语义） | ✅ |
| - `public_cases=False`：本人可见 score/counts、**details 为空**；其他登录用户 → 403 | ✅ |
| - `public_cases=True`：本人与**所有登录用户**可见完整 details | ✅ |
| - 管理员不受影响、始终完整 | ✅ |
| `PUT /api/problems/{id}/log_visibility`（仅管理员；public_cases 默认 False） | ✅ |
| public_cases 存题目文件、**不进题目对外字段**；题目 CRUD 覆盖不丢失 | ✅ |
| 审计 `GET /api/logs/access/`（仅管理员；action=`view_logs`；user_id/problem_id 至少其一 400；status 记录 200/403；401/404/参数错不记） | ✅ |
| pytest **55/55**（D5 新增 8 例） | ✅ |

## 2. 文件变动

```
backend/app/services/
├── problems.py   # get_public_cases/set_public_cases；update 保留私有键（public_cases/difficulty_score）
├── logs.py       # 新增：record_access（审计写入）/ query_access（筛选+分页）
backend/app/api/logs.py    # 新增：log / log_visibility / access 三接口
backend/main.py            # include logs router
backend/tests/test_d5_logs.py  # 新增 8 用例
```

## 3. 关键实现点

1. **log 可见性判定**（api/logs.py）：未登录 401（依赖）→ 404（记录不存在，不审计）→
   非 admin 且题目未公开：非本人 403（**审计记 403**）；本人 → `{details:[], score, counts}`；
   其余（admin 或公开）→ `{details 完整, score, counts}`（本人与其他登录用户相同）。
   返回 details 元素为评测时记录的 `{id, result, time, memory}`。
2. **审计记录**（services/logs.py）：仅记录"已鉴权且资源存在"的 log 访问（200 与 403 都记，status 存字符串）；
   未登录/不存在/参数错误不记（api.md"不必记录"）。条目字段
   `{user_id, username, problem_id, action:"view_logs", time, status}`，文件名 `时间戳-userid`。
   ⚠ action 为 **view_logs**（助教澄清 2026-09-02）；与 role 变更的操作日志是两回事。
3. **查询**：仅管理员；user_id/problem_id 至少其一（全空 400，助教确认 2026-09-03）；
   分页语义同 submissions（pagination.normalize_page）；按 time 倒序；响应 `data` 为条目数组（api.md 示例形态；
   如需 total 可后续补 `{total, logs}`）。
4. **public_cases 存储**：写在题目 JSON 的私有键（不进 to_public——api.md 题目字段无此项）；
   PUT /api/problems/{id} 覆盖更新时显式保留 public_cases 与 difficulty_score 两个私有键，避免丢配置。

## 4. 自测（已执行，Linux WSL）

```bash
wsl ~/oj-venv/bin/python -m pytest tests -q    # 55 passed（D5 新增 8 例）
```

## 5. 遗留 / 下一步

- Step6 前端（9.7）：日志页需区分"本人+未公开（无 details）"与"公开（details 可见）"与"无权限（403 提示）"三种渲染。
- AI 对齐（9.6 内 1h）：按 ai-alignment-notes 8 项议题定案后回填并恢复 AI 排期（9.9 冲刺）。
- 素材：D5 三态截图登记到 reports/report-assets.md（报告引用）。
