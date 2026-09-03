# D2（9.3 下午加推 / 计划 9.4）实现说明与代码导读 —— 用户系统（官方 Step4，5 分）

> 消化材料：先读"做了什么"，按"代码导读"顺序看文件，最后跑"自测清单"。需求基准见 `PROJECT_REQUIREMENTS.md` §5 Step4 与 §4.3。

## 1. 今天（加推）做了什么

D2 = 官方 Step4 用户系统，提前完成并自测通过：

| 项 | 状态 |
|---|---|
| 注册 `POST /api/users/`（用户名 3–40 / 密码 ≥6 / 唯一 400 / bcrypt） | ✅ |
| 登录/登出 `POST /api/auth/login` `logout`（**服务端 session**：uuid4 + `data/sessions/`，Cookie 只放 session id） | ✅ |
| banned：再登录 403 + **已登录会话立即失效**（实时查库，dec-0f895a1ddd678090） | ✅ |
| `GET /api/users/{id}`（本人/管理员；越权 403；404）、`GET /api/users/`（管理员，分页语义同 submissions） | ✅ |
| `PUT /api/users/{id}/role`（role 校验 400 / 非管理员 403 / **权限操作日志**落盘） | ✅ |
| `POST /api/users/admin`（创建管理员；重名 400；非管理员 403） | ✅ |
| 权限依赖 `get_current_user` / `require_admin`（供 Step1–3 复用） | ✅ |
| 统一 msg 契约表 `core/messages.py`（评审 P1/P3 落地） | ✅ |
| pytest 20/20（D1 5 + D2 15）+ 真实 uvicorn 冒烟（登录/会话/登出全链路） | ✅ |

## 2. 新增/修改文件

```
backend/app/
├── core/
│   └── messages.py        # 全站统一 msg（英文，对齐 api.md 示例风格）
├── services/              # 业务层（薄 API 只做编排）
│   ├── users.py           # 注册/查询/role 变更/分页/操作日志/自增 user_id
│   └── sessions.py        # 服务端 session：uuid4、TTL、Cookie 读写
├── api/
│   ├── deps.py            # get_current_user / require_admin（关键！）
│   ├── auth.py            # POST /api/auth/login、logout
│   └── users.py           # /api/users/* 五个接口
└── config.py              # + ROLE_CHANGES_DIR（权限操作日志目录）
backend/tests/test_d2_users.py   # 15 个用例
```

## 3. 关键实现点（请逐条理解）

1. **服务端 Session 而非 Cookie 内嵌**（`services/sessions.py`）
   - 登录 → `uuid4().hex` 生成 sid → 会话 JSON 存 `data/sessions/{sid}.json`（含 expires_at，TTL 7 天）→ 响应 `Set-Cookie: oj_session=...; HttpOnly; SameSite=Lax`。
   - Cookie 里**只有随机 id，没有明文身份**；登出删除服务端文件即失效（JWT 无法做到这点，Step4 页面教学强调）。
   - 校验时若过期/损坏 → 顺带删除（懒清理）。
   - reset 清空 `sessions/` 目录 ⇒ "退出当前登录状态"自动成立。

2. **权限依赖与 banned 立即失效**（`api/deps.py`，供 Step1–3 复用）
   - `get_current_user`：读 cookie → 查 session → **实时按 username 查库取用户** → 判定：无/失效会话 401 → 用户不存在 401 → **role=banned 403**。
   - 因为每次请求都实时查库，admin 把用户设 banned 后，该用户已登录会话的**下一次请求即返回 403**（决策 dec-0f895a1ddd678090，测试专门覆盖）。
   - `require_admin` = 在 get_current_user 基础上再校验 role，非管理员 403。
   - 判定顺序符合 401 > 403 > ... 约定。

3. **注册校验链路**（`api/users.py` + `services/users.py`）
   - pydantic `Field(min_length=3/max_length=40)`、密码 `min_length=6` → 超限触发 `RequestValidationError` → 全局处理器转 **400**（这次顺带补上了评审 P2 要的 422→400 实测用例）。
   - service 层对 strip 后的 username 再防御校验；唯一性 → 400 "username already exists"。
   - `user_id` 自增：取现有最大 user_id+1（admin 固定 "0"，首个普通用户 "1"，对齐 api.md 注册示例）。

4. **权限变更日志**（`services/users.py::_log_role_change`）
   - 每次 role 变更写 `data/logs/role_changes/{时间戳}-{user_id}.json`，含 operator/target/old/new role/time。
   - ⚠ 与 Step5 的 access 审计（action=`view_logs`，助教澄清 2026-09-02）是两回事，别混淆。

5. **分页语义**（`list_users`，api.md：与 submissions 一致）
   - page 有值 + page_size 空 → 400（`page_size is required...`）；page_size 有值 + page 空 → 第 1 页；两者皆空 → 全量；page/page_size <1 → 400。
   - 排序：按 user_id 数值升序（admin "0" 在前）。

6. **统一 msg 表**（`core/messages.py`）
   - 响应文案全部引用常量（英文、贴近 api.md 示例如 "problem not found" 风格），避免散点中英混杂——回应评审 P1/P3。

7. **真实 HTTP 冒烟发现的一个注意点**
   - 命令执行环境为 WSL，`curl 127.0.0.1` 连不上 Windows 侧 uvicorn，需用 `/mnt/c/Windows/System32/curl.exe`（README 已提示）。
   - shell 变量在跨 `&&` 段不保留（宿主分段执行），curl 脚本里把 cookie 文件名写死即可。

## 4. 自测清单（已执行，全部通过）

```bash
cd backend
../.venv/Scripts/python.exe -m pytest tests -v     # 20 passed（D1 5 + D2 15）
# 真实服务冒烟（uvicorn :8000 + curl.exe + cookie jar）：
#  reset → 200；注册 smoke → user_id "1"；登录 → Set-Cookie；
#  带 cookie GET /api/users/1 → 200；无 cookie → 401；
#  登出 → 200；登出后旧 cookie → 401（服务端会话已删）
```

建议自行复跑 pytest，并按 §3 的 7 个要点对照阅读：`sessions.py → deps.py → users.py(service) → api/users.py → api/auth.py`。

## 5. 与官方/需求对照

- 注册/登录响应结构与 api.md 示例一致（data 字段、msg 文案）。
- banned 立即失效、服务端 session、权限操作日志均按需求文档已确认决策实现。
- `GET /api/users/` 响应键为 `users`（api.md 示例），非 submissions 的 `submissions`——注意区分。
- ✅ 响应字段已**逐字段对照官方 api.md（2026-09-01）示例**核对（回应 D2 评审 P2）：注册返回 `user_id/username/join_time/role/submit_count/resolve_count` 六字段、登录返回 `user_id/username/role`、创建管理员返回 `user_id/username`、用户详情与列表条目同六字段——均与官方示例一致，无多余字段。

## 6. 遗留/风险

- 越权访问他人详情返回 403（不泄露存在性）；管理员查不存在 → 404。语义按"403 优先于 404"实现（判定顺序约定）。
- `GET /api/users/` 的 api.md 异常表含"404 用户不存在"疑似笔误，本实现不产生该场景（列表接口只 400/401/403）。
- Step2–3 接入鉴权时复用 `api/deps.py`；提交计数 submit_count/resolve_count 的维护在 Step2/3 落地。
- 会话 TTL 7 天为默认，未做"服务端主动清过期"定时任务（懒删除足够）。
- 【评审 P3 观察项，2026-09-03】管理员**可自我降权/被 ban**（api.md 未禁止、无保护）：系统可能瞬间失去可用管理员，需 reset 恢复；验收演示时避免误操作。代码不改，语义在此记录。
- 【评审 P3 观察项】Session Cookie 未设 `Secure`：本地 HTTP 验收无碍（TLS 非验收项），公网部署需加。
- 【评审 P3 观察项】Starlette 默认 404/405 的 msg 仍为 `str(exc.detail)`（"Not Found"），未走 `messages` 表；后续统一契约文案时收敛。
- 【评审 P3，已落地 9.3 晚】`store.save_json` 已改 tmp + `os.replace` 原子写。
