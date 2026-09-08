# 9.8 评审意见 —— 当前状况总评审 + GitHub 推送完成记录

- **评审日期**：2026-09-08
- **对应 git**：`077e79e`（HEAD；remote 已推送同 commit）
- **评审范围**：全仓库健康度（9.7–9.8 新增：AI per-user/计价自动化、Step6 前端 polish、一键启动加固、示例题自动种入、题目申请审批流）+ GitHub 推送
- **结论**：✅ 当前状况健康可交付演示；✅ 已成功推送至 `github.com/DJH667/AI_OJ`（main，68 提交全历史）。

## 1. 实测验证

| 项 | 结果 |
|---|---|
| 全量测试（WSL Linux） | **75 passed**（2 条依赖弃用警告） |
| 工作区 | clean（84 文件、68 提交、无跟踪的 data/密钥/大文件） |
| 一键启动 | `start.cmd` 已加固；后端 8000 探活正常 |
| SSH 认证 | `Hi DJH667!`（使用 Windows 侧 `C:\Users\djh_r\.ssh\id_ed25519`，已拷贝至 WSL `~/.ssh`，chmod 600） |
| 推送 | `origin` = `git@github.com:DJH667/AI_OJ.git`；`main -> main`；`git status -sb` = `## main...origin/main`；远程 HEAD=`077e79e` ✅ |

## 2. 历次评审问题闭环核对（截至 9.8 HEAD）

| 原发现 | 状态 | 提交 |
|---|---|---|
| AI model-config 省略计价字段 → 500（P1） | ✅ 消除：改为 per-user + `ai_catalog` 目录自动计价，价格字段不再由用户提供 | `3f2da5d` / `e49bcd6` / `5078193` |
| AI 普通任务 cancel 不生效（P1） | ✅ `_guard_interrupted` 写状态前检查，interrupted 不再被覆盖 | `3f2da5d` |
| model-config 任意用户改全局配置（P2） | ✅ per-user 配置 | `e49bcd6` |
| POST 后 submit_count 延迟（P3） | ✅ POST 保存 pending 后立即 `recompute_stats` | 9.7 修复 |
| `_JudgeError` 分支未清零旧字段（P3） | ✅ 兜底清零（score/counts/compile_info/run_info） | `3f2da5d` |
| start.cmd 无限等待 / 端口冲突（P2×2） | ✅ 40 次超时 + 8000/8501 占用检测 + 依赖预检 | `984bf75` |
| 浏览器打开过早 / 文档不一致 / stop.cmd 误杀（P3） | ✅ 浏览器延后 4s；README/USER_GUIDE 文案统一；stop 精确匹配端口 | `984bf75` / `46498ee` |
| `.gitattributes` 未声明 `*.cmd`（P3） | ✅ 已补 `*.cmd text eol=crlf` | 9.7 修复 |

> ⏳ 台账纪律：上述修复此前未回填 `reports/review-findings.md`（状态仍标"待处理"），本次已回填（见该文件）。

## 3. 新观察 / 需与用户确认（P2 级，不阻塞）

1. **示例题自动种入 P1000/P1001**（启动幂等、reset 不回种、删除后重启恢复）：若自动评测脚本用同 id 建题会 409。建议在 USER_GUIDE/README 明确"评测环境可用 `OJ_SEED_DEMO=0` 关闭"（conftest 已设），并在验收前用真实评测脚本复核一次。
2. **普通用户改/删题走"申请-审批"流**（`applications.py`，9.8 polish）：后端 `PUT /api/problems/{id}`（登录可改）与 `DELETE`（仅 admin）的 api.md 语义未变，审批流是前端产品增强。需确认演示口径：若按 api.md 走查，普通用户可直接 PUT；若演示审批流，二者都保留。请与验收预期对齐。
3. **access 审计响应形态 / 文件名同微秒碰撞**（P3）：仍待 D7a 与 api.md 终核。

## 4. GitHub 推送记录（供报告引用）

- 远端：`git@github.com:DJH667/AI_OJ.git`（origin，已设 upstream）
- 分支：`main`（68 个提交全历史，未改写、无 force push）
- 无敏感内容外泄：`data/`、`.venv/`、`.env`、日志均被 `.gitignore` 排除，跟踪文件不含密钥/API key（AI 配置按用户存 `backend/data/ai_configs/`，本地未入库）
- 后续更新：改完提交后 `git push` 即可；若在其它机器克隆需配置 SSH key

## 5. 结论

- 代码与文档状态：**75/75 测试绿、工作区 clean、历次评审问题基本闭环**，处于 9.8 回归/演示就绪阶段。
- 推送：**已完成**，请到 GitHub 检查 `https://github.com/DJH667/AI_OJ`（建议顺手确认仓库可见性与 README 渲染）。
