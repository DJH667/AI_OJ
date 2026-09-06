# 待向助教确认的问题清单（2026-09-03 整理）

> 用途：携带官方 api.md/FAQ 原文词句向助教提问；拿到答复后把结论回填本文件（"答复"栏）并同步 PROJECT_REQUIREMENTS.md §9。
> 说明：以下问题均不阻塞开发——每项都附"当前默认实现"，若无答复按默认推进，评测若不符再做局部调整。

---

## 问题 1：`POST /api/reset/` 的鉴权与评测调用方式（✅ 已答复 2026-09-04）

**官方原文**（api.md，测试支持：系统重置）：
> 路径：`POST /api/reset/`
> 权限：仅管理员（**测试环境可不校验**）
> 说明：清空测试产生的用户、题目和提交数据，退出当前登录状态，并重新创建初始管理员账户。
> 异常：401 用户未登录 / 403 权限不足

**当前实现**：已按 api.md **实现管理员鉴权**——未登录返回 401、已登录非管理员返回 403（与异常表及异常处理顺序 401 > 403 一致）；同时提供 `config.RESET_REQUIRE_ADMIN` 开关（默认 True）落实"测试环境可不校验"的放宽口径。

**想确认**：自动评测调用 reset 前是否会先以 `admin/admintestpassword` 登录？（若是则现有实现无需任何调整；若评测会免登录直接调用，请告知——我们将开关置 False 以兼容。）

**答复**：✅ 会先登录 admin（2026-09-04 用户确认）。当前实现（`RESET_REQUIRE_ADMIN=True`，未登录 401 / 非管理员 403）无需调整。

---

## 问题 2：429 限频的口径（✅ 已答复 2026-09-03）

**官方原文**（api.md）：
> 状态码表：429 | 频率超限 | **1min 内提交超过 3 次**
> `POST /api/submissions/` 异常：… / 429 提交频率超限

**当前实现**：按助教答复改为**单人单题**——1 分钟内**同一用户对同一题目的提交** >3 次返回 429（2026-09-03 确认；实现见 D3/D4 submissions 接口）。

**想确认**：限频按**用户全局**统计，还是按**单题**统计？窗口是否固定为 1 分钟（评测的多次提交会不会误触发 429，例如评测脚本快速连续提交多题）？

**答复**：单人单题。

---

## 问题 3（对应清单 5）：删除题目后 `submit_count` / `resolve_count` 是否回退（✅ 已答复 2026-09-03）

**官方原文**（api.md，用户注册响应示例注释）：
> `"submit_count": 0, // 用户提交数（按提交算，一个 problem 可贡献多次）`
> `"resolve_count": 0 // 用户通过数（按题目算，一个 problem 最多贡献一次）`

**相关已确认**（助教群答 2026-09-02）：删除题目时级联删除 testcase、submission、judge_log、access_log。

**当前实现**：按助教答复改为**回退**（2026-09-03 确认）——删除题目时，对该题有提交的用户 `submit_count` 减去其在该题的提交数；`resolve_count` 若 AC 过该题则减 1。实现随 D3 DELETE 题目（先建 submissions 后再联动）落地。

**想确认**：删除题目后用户统计应保持（快照）还是回退重算？

**答复**：是的，需要回退。

---

## 问题 4（对应清单 6）：`GET /api/logs/access/`（及用户列表）筛选能否"全空全览"（✅ 已答复 2026-09-03）

**官方原文**（api.md）：
> `GET /api/logs/access/` 参数：`user_id` (str, **可选**)：按用户筛选 / `problem_id` (str, **可选**)：按题目筛选 / `page` / `page_size`；**参数意义与 `GET /api/submissions/` 一致**。
> `GET /api/users/` 参数：`page`、`page_size`（可选）；参数意义与 `GET /api/submissions/` 一致。
> `GET /api/submissions/` 参数说明："这五个参数均可选，其中 `user_id`、`problem_id` 为**一级条件**，其余为二级条件。**一级条件不可以全部为空。**"

**矛盾点**：审计接口把 `user_id`/`problem_id` 标为"可选"，字面理解可不提供（全空）；但"参数意义与 submissions 一致"又暗示一级条件不可全空。即：全空时应返回全部（管理员全览）还是参数错误（400）？

**当前实现**：按助教答复（2026-09-03）：**access 审计的 `user_id`/`problem_id` 两项全空 → 400**；有一项不空则其余语义（分页等）按查询评测列表规则。`GET /api/users/` 仅有 page/page_size（无一级条件），维持"全空=全部"（助教答复未涉及该接口，分页语义照旧）。

**想确认**：access 审计与用户列表在不提供任何筛选条件时，应返回全部还是视为参数错误？

**答复**：两项全空返回错误码（400）；两项有一项不空，按照"查询评测列表"所述来。

---

## 问题 5（新增 2026-09-04）：编译错误（CE）的 submission 状态归属

**官方原文**（api.md）：submission 状态为 pending / success / error；"查询评测结果"示例为 status success + compile_info{result,message}；CE 的归属未明示。Step3 列表裁剪规则："status 为 error/pending 时只需返回 submission_id 与 status"。

**当前实现**（2026-09-05 用户判定后）：CE → **status=error**——编译失败视为提交未通过评测；`compile_info.result="compile error"` 保留供详情展示、score/counts=0、run_info=null、details=[]（不跑测例）。

**想确认**：编译错误（CE）的 submission 状态应为 success 还是 error？（影响 Step3 列表中 CE 提交是否可见 score/compile_info）

**答复**：按一般共识归 **error**（用户判定 2026-09-05，已实现——judge 改 CE 分支 + 相关测试更新）。

---

## 问题 6（新增 2026-09-05）：rejudge 对用户统计的影响

**官方原文**（api.md）：`PUT /api/submissions/{submission_id}/rejudge` 仅说明"重新评测需覆盖原 submission_id 对应的内容"；未提及对 submit_count/resolve_count 的影响。

**当前实现**（2026-09-05 用户判定后）：评测完成（含 rejudge）后**实时重算**该用户统计——`submit_count`=该用户现存提交记录数（按提交算，pending/error/CE 均计入，不因 rejudge 额外 +1）；`resolve_count`=AC 过的题目去重数（一题最多一次）。重评使唯一 AC 变失败 → resolve 实时回退（幂等重算，无读改写竞态，judge 串行锁内执行）。

**想确认**：① rejudge 是否计入 submit_count？② 若某用户对该题唯一 AC 提交被 rejudge 判失败，resolve_count 是否应回退？

**答复**：实时变化——rejudge 后更新该 submission 所属用户的统计数据（用户判定 2026-09-05，已实现：`recompute_stats` + 新增 rejudge 实时回退测试）。

---

## 问题 7（新增 2026-09-05，✅ 已答复）：评测日志可见性（public_cases 两态）的细粒度

**官方原文**（api.md Step5）：`GET /api/submissions/{submission_id}/log` 权限"仅本人（如果没有公开）或管理员"；"仅当该评测对应问题 public_cases 设置为 True 时用户可见 details"——未区分"本人是否可见 details"与"其他用户是否 403"。

**想确认**：① 未公开时本人能否看 details（AC/WA、耗时、内存）？② 未公开/公开两种设置下，其他已登录普通用户分别可见什么？③ 管理员是否始终可见？

**答复**（助教群答 2026-09-05）：
- `public_cases=False`：提交者本人可访问自己的日志，但**不能查看测试点明细 details**（看不到 AC/WA、耗时、内存），只能看到总得分 score 和总分 counts；**其他已登录普通用户访问返回 403**。
- `public_cases=True`：提交者本人**和其他已登录普通用户**都可查看 details（每测例状态、耗时、内存）以及 score/counts。
- 管理员不受 public_cases 影响，始终可查看完整日志；**日志公开不会同时开放用户代码、编译信息等 Step2/3 提交详情**。
- 已按此实现（D5，见需求文档 §5 Step5 与 d5 实现说明）。
