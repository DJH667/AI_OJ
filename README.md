# 程序设计训练（Python）· 实验二：在线评测系统（OJ）

人机协同开发项目。后端 FastAPI（前后端分离，仅提供 REST API），前端 Streamlit，评测执行测试在 WSL2/Ubuntu。

## 一键启动（Windows）

双击 **`start.cmd`**：WSL 起后端（:8000）→ 前端 Streamlit（:8501）→ 自动打开浏览器。
停止后端：`stop.cmd`（后端为后台进程，无独立窗口）。详细使用见 `reports/USER_GUIDE.md`。

## 目录结构

```
大作业-2/
├── backend/            # FastAPI 后端（源码，端口 8000）
│   ├── app/
│   │   ├── core/       # 统一响应、异常处理、密码哈希（bcrypt）
│   │   ├── db/         # 全 JSON 存储层、初始管理员种子
│   │   ├── api/        # REST 路由（/api/*）
│   │   └── config.py   # 数据目录 / 初始管理员等全局配置
│   ├── tests/          # pytest 冒烟测试
│   ├── conftest.py
│   └── main.py         # FastAPI 入口
├── frontend/           # Streamlit 前端（端口 8501，D6 起实现）
├── reports/            # 面向用户的文档（需求分析、进度计划、每日实现说明…）
└── requirements.txt    # Python 依赖（venv: .venv/，Python 3.14）
```

> 运行期数据（用户/题目/提交/日志）生成于 `backend/data/`，已 gitignore，不进版本库。

## 常用命令

```bash
# 后端依赖（Windows：.venv；WSL Linux：~/oj-venv —— 评测需 Linux，推荐 WSL）
#  WSL 首次：wsl python3 -m venv ~/oj-venv && wsl ~/oj-venv/bin/pip install fastapi "uvicorn[standard]" pydantic httpx pytest psutil bcrypt python-multipart
wsl ~/oj-venv/bin/python -m pytest tests -q              # 全量测试（Linux，含评测执行）

# 启动后端（backend/ 目录下；8000 端口）
wsl ~/oj-venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
# Windows 侧备用：../.venv/Scripts/python.exe -m uvicorn main:app --port 8000（评测执行不可用）
```

> Windows 与 WSL 双环境提示：venv 为 Windows 原生（`.venv/Scripts/`）；在 WSL 内
> 用 `curl http://127.0.0.1:8000/...` 访问的是 WSL 网络栈，访问 Windows 侧进程请用
> `/mnt/c/Windows/System32/curl.exe`，或让 uvicorn 绑定 `0.0.0.0` 后访问宿主地址。

## 文档索引（reports/）

- `PROJECT_REQUIREMENTS.md` — 需求分析 v2（含官方澄清与用户决策记录，开发/验收对照基准）
- `WORK_PLAN.md` — 工作进度计划 v2（9.3–9.10）
- `d1-implementation-notes.md` — 每日实现说明与代码导读（您自行消化的材料）
