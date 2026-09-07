@echo off
rem ============================================================
rem  OJ one-click start (Windows): backend(WSL :8000) + frontend(Streamlit :8501)
rem  Prereq: WSL2 with ~/oj-venv (see reports/USER_GUIDE.md)
rem  Backend log: backend.log at repo root. Stop: stop.cmd
rem ============================================================
setlocal EnableExtensions

set "REPO=%~dp0"
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"
set "DRV=%~d0"
set "WP=%~p0"
set "WP=%WP:\=/%"
if "%WP:~-1%"=="/" set "WP=%WP:~0,-1%"
if /i "%DRV%"=="C:" (set WDRV=c) else if /i "%DRV%"=="D:" (set WDRV=d) else if /i "%DRV%"=="E:" (set WDRV=e) else if /i "%DRV%"=="F:" (set WDRV=f) else if /i "%DRV%"=="G:" (set WDRV=g) else (
    echo [ERROR] Drive %DRV% not supported. Keep repo on C:..G:.
    pause
    exit /b 1
)
set "WROOT=/mnt/%WDRV%%WP%"

echo [1/3] Repo in WSL: %WROOT%
wsl test -x "$HOME/oj-venv/bin/python" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] ~/oj-venv not found in WSL. See reports\USER_GUIDE.md
    pause
    exit /b 1
)

echo [2/3] Starting backend FastAPI :8000 ...
start "OJ-Backend" /b wsl -e bash -lc "bash %WROOT%/scripts/start-backend.sh"

echo Waiting for backend...
:wait_loop
%SystemRoot%\System32\ping.exe -n 2 127.0.0.1 >nul
%SystemRoot%\System32\curl.exe -s -o nul http://127.0.0.1:8000/api/no-such-probe
if errorlevel 1 goto wait_loop
echo Backend is up.  http://127.0.0.1:8000

echo [3/3] Starting frontend Streamlit :8501 ...
start "" http://localhost:8501
"%REPO%\.venv\Scripts\python.exe" -m streamlit run "%REPO%\frontend\app.py" --server.port 8501

echo.
echo Frontend exited. To stop backend run stop.cmd  (or close this window).
pause
endlocal
