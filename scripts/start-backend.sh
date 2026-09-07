#!/usr/bin/env bash
# 后端启动（WSL 内）：由 start.cmd 通过 wsl 调用；也可手动：wsl bash scripts/start-backend.sh
# 日志写入仓库根 backend.log
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR/backend"
LOG="$DIR/backend.log"
exec "$HOME/oj-venv/bin/python" -m uvicorn main:app --host 0.0.0.0 --port 8000 >>"$LOG" 2>&1
