# 9.7 评审意见 —— 一键启动脚本（start.cmd / stop.cmd / scripts/start-backend.sh）

- **评审日期**：2026-09-07
- **对应 git**：`9cba4ba`
- **评审对象**：`start.cmd`、`stop.cmd`、`scripts/start-backend.sh`（及 README/USER_GUIDE 中的启动说明）
- **结论**：✅ 脚本可用（`backend.log` 证明已成功启动过后端；本次探测 8000 端口当前在线、探活 404 正常）。无阻断性问题；有 2 个 P2 健壮性建议和若干 P3。

## 1. 已核验事实

- `start.cmd`/`stop.cmd` 为 CRLF（批处理正确行尾）；`scripts/start-backend.sh` 为 LF 且可执行。
- 路径推导使用 `%~dp0`，中文路径处理正确（当前仓库 `E:\程序\python\大作业-2` 已被正确映射为 `/mnt/e/...`）。
- 探活机制：`curl` 请求 `/api/no-such-probe`，后端返回 404 即认为就绪（curl 退出码 0），合理。
- `backend.log` 未被 git 跟踪（`.gitignore` 的 `*.log` 覆盖），不会污染仓库。
- 当前 8000 端口有后端在线（探活返回 404），8501 未在运行——与"先起后端、前端退出"的状态一致。

## 2. 问题与建议

| # | 级别 | 问题 | 建议 |
|---|---|---|---|
| 1 | P2 | `start.cmd` 的 `:wait_loop` 无超时：后端启动失败（缺依赖/端口占用）时会无限循环 | 加计数器（如 30 次≈30s）后报错退出，并提示查看 `backend.log` 尾部 |
| 2 | P2 | 无端口占用检测：8000 已有旧后端/其它服务时，探活会"通过"，前端连的是旧后端 | 启动前检查 8000/8501 是否被占（或自动调用 stop 逻辑），冲突时明确报错 |
| 3 | P3 | 浏览器打开过早：`start "" http://localhost:8501` 在 `streamlit run` 之前执行，首次打开会看到连接失败 | 先起 streamlit 并探活 8501 后再打开浏览器 |
| 4 | P3 | 文档与实际不一致：README/USER_GUIDE 写"新窗口 OJ-Backend / 可关闭该窗口停止"，但脚本用 `start /b`（无窗口），关闭窗口并不能停后端 | 统一为"仅 stop.cmd 停止后端" |
| 5 | P3 | 预检只查 WSL venv 的 python 存在，未校验 fastapi/uvicorn；Windows 侧未校验 streamlit | 加 `python -c "import fastapi, uvicorn"` 与 streamlit 存在性检查 |
| 6 | P3 | 盘符仅支持 C:–G:，仓库在 H: 等盘会直接报错（当前 E: 无碍） | 改用 `wslpath` 动态转换或放宽提示 |
| 7 | P3 | `--host 0.0.0.0` 使后端对局域网可达；本机演示通常无需 | 如无远程访问需求可改 `127.0.0.1`（需确认 WSL2 localhost 转发） |
| 8 | P3 | `stop.cmd` 用 `pkill -f 'uvicorn main:app'` 会误杀其它项目的同名 uvicorn | 可按工作目录/端口精确匹配 |
| 9 | P3 | `.gitattributes` 未显式声明 `*.cmd text eol=crlf`，仅靠 `* text=auto` | 补 `*.cmd text eol=crlf` 防止其它平台 checkout 后行尾错误 |
| 10 | P3 | `backend.log` 只追加不轮转，长期会变大 | 可加简单截断或轮转 |

## 3. 结论

脚本**可以直接使用**，无需返工。建议在 9.8 回归前至少处理 **#1（超时退出）** 和 **#2（端口冲突检测）**，避免验收演示时因残留进程/端口占用卡住或连错后端。
