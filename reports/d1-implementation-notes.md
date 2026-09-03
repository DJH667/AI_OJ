# D1（9.3）实现说明与代码导读 —— 后端公共骨架

> 面向您（项目成员）的消化材料：先读"做了什么"，再按"代码导读"顺序看文件，最后跑"自测清单"验证。
> 进度计划与需求基准见同目录 `WORK_PLAN.md` / `PROJECT_REQUIREMENTS.md`。

## 1. 今天做了什么

D1 目标 = 后端公共骨架，全部完成并自测通过：

| 项 | 状态 |
|---|---|
| 环境（venv + 依赖 + WSL g++/python3） | ✅ 9.2 晚提前完成 |
| 统一响应 `{code, msg, data}` + 全局异常（422→400、404 统一格式） | ✅ |
| 全 JSON 存储层（文件名安全转义、遍历、reset 清空） | ✅ |
| `POST /api/reset/`（清空全部业务数据并重建初始管理员） | ✅ |
| 启动钩子创建初始管理员 `admin` / `admintestpassword` | ✅ |
| pytest 冒烟 ×4 + uvicorn 真实启动验证 | ✅ 全部通过 |

## 2. 目录与文件职责

```
backend/
├── main.py               # FastAPI 入口：lifespan（建目录+种子 admin）、挂异常处理与路由
├── conftest.py           # 让 pytest 能把 backend/ 加入 sys.path
├── app/
│   ├── config.py         # 数据目录定义（problems/users/submissions/logs/sessions）、初始管理员账密
│   ├── core/
│   │   ├── response.py   # success()：统一成功响应体
│   │   ├── exceptions.py # ApiError 业务异常 + 全局处理器（含 422→400、404 收敛）
│   │   └── security.py   # bcrypt 哈希/校验（D2 登录复用）
│   ├── db/
│   │   ├── store.py      # 全 JSON 存储抽象：save/load/delete/list/iter/clear
│   │   └── seed.py       # ensure_admin()：幂等创建初始管理员（reset 复用）
│   └── api/
│       └── reset.py      # POST /api/reset/
└── tests/
    └── test_d1_smoke.py  # 冒烟测试
```

## 3. 关键实现点（请逐条理解）

1. **统一响应与异常**（`core/response.py` + `core/exceptions.py`）
   - 成功：路由 `return success(msg=..., data=...)` → `{"code":200,...}`（HTTP 200）。
   - 业务错误：`raise ApiError(status_code, msg)` → 全局处理器输出同结构 JSON 且 HTTP 状态码一致。
   - FastAPI 默认参数校验失败返回 **422**，项目约定转 **400**（`RequestValidationError` 处理器）。
   - 未匹配路由的 404 也收敛为 `{"code":404,"msg":"Not Found","data":null}`。
   - 判定优先级 401>403>400>429>409>404>500 是**业务层顺序约定**（D2 起在依赖/服务里落实：先鉴权后校验），异常处理器本身只负责"格式化"。

2. **全 JSON 存储**（`db/store.py`）
   - key（题目 id、用户名等）经 `urllib.parse.quote` 百分号编码作为文件名，防止 `/ : * ?` 等非法字符与路径注入；`list_keys` 反向解码。文件名一律 `*.json`。
   - 目录统一在 `backend/data/` 下（已 gitignore）；`clear_all()` = reset 清空语义。
   - 数据量小 + 单用户串行评测 ⇒ 无并发写压力（需求文档 §4 决策）。

3. **初始管理员**（`db/seed.py`）
   - `ensure_admin()` 幂等：按 username 存在即跳过；user_id 固定 **"0"**，普通用户自 "1" 分配（对齐 api.md 注册示例首个用户 user_id="1"）。
   - 密码 bcrypt 哈希后存储，绝不明文。
   - 启动（lifespan）与 reset 后都会调用 ⇒ "重置后重建初始管理员"。

4. **reset**（`api/reset.py`）
   - 清空全部业务子目录 → 重建 admin；响应 msg=`system reset successfully`。
   - **未做权限校验**：api.md 写"仅管理员（测试环境可不校验）"，为让自动评测可直接调用，本项目按不校验处理（已在注释说明）。
   - "退出当前登录状态"：D2 接入服务端 session 后，reset 会顺带清空 `data/sessions/`。

5. **Windows/WSL 双环境**
   - venv 是 Windows 原生（`.venv/Scripts/`）；在 WSL 里也能调用该 exe 跑测试/起服务。
   - uvicorn（Windows 进程）监听 Windows 网络栈：WSL 内 `curl 127.0.0.1` 连不上，需用
     `/mnt/c/Windows/System32/curl.exe`，或让 uvicorn 绑 `0.0.0.0` 后访问宿主 IP。
   - 评测执行（g++/python3/资源限制）后续统一在 WSL Ubuntu 里验证（D4 前完成）。

## 4. 自测清单（已执行，全部通过）

```bash
cd backend
../.venv/Scripts/python.exe -m pytest tests -v            # 4 passed
# 真实服务（backend/ 下后台起 uvicorn :8000）
# curl.exe -X POST http://127.0.0.1:8000/api/reset/
#   → {"code":200,"msg":"system reset successfully","data":null}
# curl.exe http://127.0.0.1:8000/api/no-such/
#   → {"code":404,"msg":"Not Found","data":null}
```

建议您自行复跑一遍（尤其 pytest），然后对照 §3 的 5 个要点逐个文件读一遍代码。

## 5. 明日预告（D2，9.4）— 用户系统（官方 Step4，5 分）

- users 持久化完善 + 用户注册（用户名 3–40 / 密码 ≥6 / 唯一 / bcrypt）
- 登录/登出：**服务端 session**（uuid4 + `data/sessions/`，cookie 只放 session id）
- banned 会话**立即失效**（每次请求实时查库校验角色，决策 dec-0f895a1ddd678090）
- `GET /api/users/{id}`、用户列表、role 变更（含权限操作日志）、创建管理员
- 权限依赖 `get_current_user` / `require_admin`（供 Step1–3 复用）

## 6. 评审意见处理（9.3 晚，详见 comments/2026-09-03-review-f5e6738.md）

评审结论：✅ D1 达标可进入 D2。处理结果：

| 意见 | 处理 |
|---|---|
| P1 缺兜底 Exception 处理器 | ✅ 已落地：`exceptions.py` 增 `@app.exception_handler(Exception)` → `{"code":500,"msg":"internal server error","data":null}`，堆栈仅入服务端日志不回显；新增 `test_unhandled_exception_500_unified` |
| P3 conftest 隐式 sys.path | ✅ 已改显式 `sys.path.insert(backend 目录)` |
| P2 损坏 JSON 静默吞 | ✅ `store.py` 对 `JSONDecodeError` 记 `logger.warning`（与"不存在"可区分） |
| P1/P3 404 msg 英文契约化 | 观察项：D2 起业务 msg 统一中文契约表时一并落实 |
| P2 422→400 实测 | D2 出现带 body 接口（注册）后补测试 |
| P3 save_json 无原子性 | ✅ 已落地（9.3 晚补）：`store.save_json` 改 tmp + `os.replace` 原子写 |
| P2 reset 不鉴权观察项 | 验收前按助教口径复核（已在下方遗留清单） |

> 测试备注：Starlette 在纯 `ASGITransport` 下会把已处理的 500 异常 re-raise 给调用方，故 500 用例改用 `TestClient(app, raise_server_exceptions=False)` 断言真实响应体。

## 7. 遗留/风险

- `error_info` 等脱敏、日志防泄露属 D2–D5 逐项落实。
- 若 reset 的"不鉴权"选择与自动评测预期不符（评测若要求必须 admin 才能 reset），届时按实测调整。
