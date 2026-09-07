#!/usr/bin/env bash
# 后端启动（WSL 内运行）：由 start.cmd 调用；也可手动：wsl bash scripts/start-backend.sh
# - 日志：仓库根 backend.log（每次启动截断）
# - pid： 仓库根 backend.pid（供 stop.cmd 精确停止）
# - 默认绑定 127.0.0.1（WSL2 localhost 转发使 Windows localhost:8000 可达）；如需局域网访问改 0.0.0.0
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR/backend"
LOG="$DIR/backend.log"
PIDFILE="$DIR/backend.pid"
: > "$LOG"
echo $$ > "$PIDFILE"
exec "$HOME/oj-venv/bin/python" -m uvicorn main:app --host 127.0.0.1 --port 8000 >>"$LOG" 2>&1
