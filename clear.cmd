@echo off
rem ============================================================
rem  OJ one-click clear (Windows): factory reset of runtime data
rem  - Stops the WSL backend (port 8000, same pattern as stop.cmd)
rem  - Deletes backend\data\ entirely: users / problems / submissions /
rem    logs / sessions / ai tasks / ai model configs / applications ...
rem  - Keeps all source code, docs, sample_problems and git history
rem  - After clearing, run start.cmd to get a fresh environment
rem    (admin/admintestpassword, builtin python+cpp, demo problems re-seeded)
rem ============================================================
setlocal EnableExtensions

set "REPO=%~dp0"
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"
set "DATA=%REPO%\backend\data"

echo.
echo OJ CLEAR: this will DELETE all runtime data (factory reset), including
echo   users, problems, submissions, logs, sessions, AI tasks,
echo   AI model configs (api keys) and problem-change applications.
echo   Source code and documents are NOT touched.
echo   Target folder: %DATA%
echo.
choice /C YN /T 5 /D N /M "Type Y to confirm wipe, or wait/N to cancel"
if errorlevel 2 (
    echo.
    echo Cancelled. Nothing was deleted.
    pause
    exit /b 1
)

echo.
echo [1/2] Stopping OJ backend on port 8000 ...
wsl -e bash -lc "pkill -f 'uvicorn main:app --port 8000' 2>/dev/null; sleep 1; echo Backend stopped"

echo [2/2] Deleting runtime data folder ...
if exist "%DATA%" (
    rmdir /s /q "%DATA%"
)
if exist "%DATA%" (
    echo.
    echo [ERROR] Could not fully delete %DATA%.
    echo         A backend process may still hold files. Close it, then rerun.
) else (
    del "%REPO%\backend.pid" >nul 2>nul
    echo.
    echo Done. Runtime data cleared. A fresh backend.pid will be written on next start.
    echo Run start.cmd to boot a brand-new environment.
)
echo.
pause
endlocal
