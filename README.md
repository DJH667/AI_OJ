# 程序设计训练（Python）· 实验二：在线评测系统（OJ）

人机协同开发项目。后端 FastAPI（前后端分离，仅提供 REST API），前端 Streamlit，评测执行测试在 WSL2/Ubuntu。

## 一键启动（Windows）

**首次使用**：双击 **`init.cmd`** 一键配环境——自动创建/校验 WSL 的 `~/oj-venv`（后端 + 测试依赖）与 Windows `.venv`（Streamlit 依赖），并检查 WSL 里的 `python3`/`g++`；已存在则跳过，`init.cmd rebuild` 可强制重建。仓库可放在任意目录/盘符（自动映射为 WSL 的 `/mnt/<盘符>/...`）。

双击 **`start.cmd`**：WSL 起后端（:8000）→ 前端 Streamlit（:8501）→ 自动打开浏览器。
停止后端：`stop.cmd`（后端为后台进程，无独立窗口）。
出厂级清除：`clear.cmd`（先停后端，再删 `backend/data`、`backend/data_test` 及 `OJ_DATA_DIR` 指向仓库内的全部运行期数据目录，代码/文档不受影响；清完用 `start.cmd` 恢复全新环境）。详细使用见 `reports/USER_GUIDE.md`。

## 前端页面（polish 2026-09-08）

- **登录/注册**：未登录时全画幅居中卡片，注册成功自动登录并进入题库；刷新页面自动恢复登录态（浏览器 Cookie）。
- **侧边栏**：题库 / 题目管理 / 个人 三项圆角导航按钮（单击切换），紫黄简约主题。
- **题库**：登录后默认页。分页圆角卡片（编号、难度、标签、通过率条状），按编号/标题搜索；点击进入题目详情。
- **题目详情（二级页）**：左侧题面（描述/输入输出/样例/约束），右侧栏提交代码（语言选择 + 大文本框 + 黄色"提交评测"）、近 3 次提交（自动刷新）与"查询提交记录"入口。
- **查询提交记录**：从题目右侧栏或"个人"页进入。按题目/状态筛选，时间倒序，结果自动刷新；管理员可查所有用户提交并重新评测。
- **题目管理**：编号/标题搜索、每题编辑/删除图标、新增题目与 AI 命题入口；普通用户改/删走申请审批，管理员审批执行。
- **个人**：信息卡 + 查询入口；管理员可进行用户管理与申请审批。
- 启动后端时按 id 幂等种入示例题 **Hello World（P1000）** 与 **A+B（P1001）**；删除后重启后端恢复。

## 目录结构

```
大作业-2/
├── backend/            # FastAPI 后端（源码，端口 8000）
│   ├── app/
│   │   ├── core/       # 统一响应、异常处理、密码哈希（bcrypt）
│   │   ├── db/         # 全 JSON 存储层、初始管理员/示例题种子
│   │   ├── api/        # REST 路由（/api/*）
│   │   └── config.py   # 数据目录 / 初始管理员等全局配置
│   ├── tests/          # pytest 测试
│   ├── conftest.py
│   └── main.py         # FastAPI 入口
├── frontend/           # Streamlit 前端（端口 8501，app.py + api_client.py）
├── scripts/            # 启动/冒烟脚本（start-backend.sh、app_smoke.py）
├── polish/             # polish 计划与打磨说明
├── reports/            # 面向用户的文档（需求分析、进度计划、每日实现说明…）
├── technical_report/   # 实验报告源稿（EXP_REPORT.md + 截图）
├── init.cmd / start.cmd / stop.cmd / clear.cmd   # 一键配环境/启动/停止/清零（Windows）
└── requirements.txt    # Python 依赖（venv: .venv/，Python 3.14）
```

> 运行期数据（用户/题目/提交/日志/会话/AI 任务与配置等）默认存 `backend/data/`
> （见 `backend/app/config.py` 的 `DATA_DIR`），可用环境变量 `OJ_DATA_DIR` 覆盖
> （如测试隔离用 `backend/data_test`）；两者均已 gitignore，不进版本库。

## 常用命令

```bash
# 后端依赖（Windows：.venv；WSL Linux：~/oj-venv —— 评测需 Linux，推荐 WSL）
#  一键完成两套 venv：双击 init.cmd（或 `cmd /c init.cmd rebuild` 强制重建）
#  手动等价命令（WSL 首次）：wsl python3 -m venv ~/oj-venv && wsl ~/oj-venv/bin/pip install fastapi "uvicorn[standard]" pydantic httpx pytest psutil bcrypt python-multipart
wsl ~/oj-venv/bin/python -m pytest tests -q              # 全量测试（Linux，含评测执行）
.venv/Scripts/python.exe -m pytest backend/tests -q      # Windows 侧后端测试

# 启动后端（backend/ 目录下；8000 端口）
wsl ~/oj-venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
# Windows 侧备用：../.venv/Scripts/python.exe -m uvicorn main:app --port 8000（评测执行不可用）

# 前端冒烟测试（需后端已在 8000 运行；会注册一次性用户 smokeuser 并真实提交）
.venv/Scripts/python.exe scripts/app_smoke.py
```

> Windows 与 WSL 双环境提示：venv 为 Windows 原生（`.venv/Scripts/`）；在 WSL 内
> 用 `curl http://127.0.0.1:8000/...` 访问的是 WSL 网络栈，访问 Windows 侧进程请用
> `/mnt/c/Windows/System32/curl.exe`，或让 uvicorn 绑定 `0.0.0.0` 后访问宿主地址。

## 文档索引（reports/）

- `PROJECT_REQUIREMENTS.md` — 需求分析 v2（含官方澄清与用户决策记录，开发/验收对照基准）
- `WORK_PLAN.md` — 工作进度计划 v2（9.3–9.10）
- `d1-implementation-notes.md` — 每日实现说明与代码导读（您自行消化的材料）
- `technical_report/EXP_REPORT.md` — 实验报告源稿（同目录截图素材；PDF 最终提交网络学堂）
