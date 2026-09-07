@echo off
rem ============================================================
rem  OJ one-click start (Windows): backend(WSL :8000) + frontend(Streamlit :8501)
rem  Prereq: WSL2 with ~/oj-venv, Windows .venv with streamlit
rem  Stop backend: stop.cmd   (backend log: backend.log, pid: backend.pid)
rem ============================================================
setlocal EnableExtensions

set "REPO=%~dp0"
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"
set "DRV=%~d0"
set "WP=%~p0"
set "WP=%WP:\=/%"
if "%WP:~-1%"=="/" set "WP=%WP:~0,-1%"
if /i "%DRV%"=="C:" (set WDRV=c) else if /i "%DRV%"=="D:" (set WDRV=d) else if /i "%DRV%"=="E:" (set WDRV=e) else if /i "%DRV%"=="F:" (set WDRV=f) else if /i "%DRV%"=="G:" (set WDRV=g) else (
    echo [ERROR] Drive %DRV% not supported by auto WSL mapping.
    echo         Please place the repo on a drive C:..G:, or start manually per reports/USER_GUIDE.md
    pause
    exit /b 1
)
set "WROOT=/mnt/%WDRV%%WP%"

echo [1/4] Repo in WSL: %WROOT%

rem ---- dependency pre-check ----
wsl test -x "$HOME/oj-venv/bin/python" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] ~/oj-venv not found in WSL. See reports\USER_GUIDE.md
    pause
    exit /b 1
)
wsl "$HOME/oj-venv/bin/python" -c "import fastapi,uvicorn" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] fastapi/uvicorn missing in ~/oj-venv. Run the install command in reports\USER_GUIDE.md
    pause
    exit /b 1
)
if not exist "%REPO%\.venv\Scripts\streamlit.exe" (
    echo [ERROR] streamlit not found in Windows .venv. Install per reports\USER_GUIDE.md section 2.2
    pause
    exit /b 1
)

rem ---- port conflict check (P2, review 2026-09-07) ----
set "UP8000=no"
%SystemRoot%\System32\curl.exe -s -o nul -m 2 http://127.0.0.1:8000/api/no-such-probe
if not errorlevel 1 set "UP8000=yes"
set "UP8501=no"
%SystemRoot%\System32\curl.exe -s -o nul -m 2 http://127.0.0.1:8501/
if not errorlevel 1 set "UP8501=yes"
if "%UP8501%"=="yes" (
    echo [ERROR] Port 8501 is already in use. Close the old frontend first.
    pause
    exit /b 1
)

if "%UP8000%"=="yes" (
    echo [2/4] Port 8000 already has a service; will reuse it as the OJ backend.
    goto have_backend
)

echo [2/4] Starting backend FastAPI :8000 ...
start "OJ-Backend" /b wsl -e bash -lc "bash %WROOT%/scripts/start-backend.sh"

echo Waiting for backend...
set /a cnt=0
:wait_loop
%SystemRoot%\System32\ping.exe -n 2 127.0.0.1 >nul
%SystemRoot%\System32\curl.exe -s -o nul -m 2 http://127.0.0.1:8000/api/no-such-probe
if not errorlevel 1 goto have_backend
set /a cnt+=1
if %cnt% GEQ 40 (
    echo [ERROR] Backend did not start within timeout. Please check backend.log tail.
    pause
    exit /b 1
)
goto wait_loop

:have_backend
echo Backend is up.  http://127.0.0.1:8000

rem ---- open browser a few seconds later, then run frontend in foreground ----
echo [3/4] Opening browser in 4s...
start "oj-browser" /b cmd /c "%SystemRoot%\System32\timeout.exe /t 4 /nobreak >nul & start http://localhost:8501"
echo [4/4] Starting frontend Streamlit :8501 ...
"%REPO%\.venv\Scripts\python.exe" -m streamlit run "%REPO%\frontend\app.py" --server.port 8501

echo.
echo Frontend exited. To stop backend: run stop.cmd
pause
endlocal
