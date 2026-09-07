@echo off
rem Stop OJ backend (WSL uvicorn). Close the frontend window manually if running.
wsl -e bash -lc "pkill -f 'uvicorn main:app' 2>/dev/null; echo Backend stopped (close OJ-Backend window if any)"
pause
