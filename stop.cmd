@echo off
rem Stop OJ backend: kill the WSL uvicorn bound to port 8000 (precise pattern).
wsl -e bash -lc "pkill -f 'uvicorn main:app --port 8000' 2>/dev/null; echo Backend stopped; close this window"
pause
