@echo off
rem ============================================================
rem  OJ one-click clear (Windows): factory reset of runtime data
rem  - Stops the WSL backend (port 8000, same pattern as stop.cmd)
rem  - Deletes runtime data folders:
rem      backend\data              (default DATA_DIR)
rem      backend\data_test         (isolated data dir, when present)
rem      %OJ_DATA_DIR% target      (data isolation env var, see
rem                                 backend/app/config.py) when it points
rem                                 INSIDE this repo
rem    contents: users / problems / submissions / logs / sessions /
rem    ai tasks / ai model configs / applications / notifications ...
rem  - A %OJ_DATA_DIR% pointing OUTSIDE this repo is skipped with a hint
rem    (remove that folder manually if a full wipe is intended)
rem  - Keeps all source code, docs, sample_problems and git history
rem  - After clearing, run start.cmd to get a fresh environment
rem    (admin/admintestpassword, builtin python+cpp, demo problems re-seeded)
rem ============================================================
setlocal EnableExtensions

set "REPO=%~dp0"
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"
set "T1=%REPO%\backend\data"
set "T2=%REPO%\backend\data_test"
set "T3="

rem ---- resolve %OJ_DATA_DIR% if set (WSL /mnt/X/... form is converted) ----
if not defined OJ_DATA_DIR goto no_odj
if "%OJ_DATA_DIR%"=="" goto no_odj
set "ODD=%OJ_DATA_DIR%"
if not "%ODD:~0,5%"=="/mnt/" goto odj_winpath
set "ODD=%ODD:~5,1%:\%ODD:~6%"
:odj_winpath
set "ODD=%ODD:/=\%"
echo %ODD% | findstr /b /i /c:"%REPO%" >nul
if errorlevel 1 (
    echo [info] OJ_DATA_DIR points outside this repo and is SKIPPED: %ODD%
    echo        ^(delete that folder manually if a full wipe is intended^)
    goto no_odj
)
set "T3=%ODD%"
:no_odj

echo.
echo OJ CLEAR: this will DELETE all runtime data (factory reset), including
echo   users, problems, submissions, logs, sessions, AI tasks,
echo   AI model configs (api keys) and problem-change applications.
echo   Source code and documents are NOT touched.
echo.
echo Target folders:
if exist "%T1%" echo   - %T1%
if exist "%T2%" echo   - %T2%
if defined T3 (
    if exist "%T3%" echo   - %T3%
)
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

echo [2/2] Deleting runtime data folders ...
if exist "%T1%" rmdir /s /q "%T1%"
if exist "%T2%" rmdir /s /q "%T2%"
if defined T3 (
    if exist "%T3%" rmdir /s /q "%T3%"
)

rem ---- report leftovers (deletion may fail if a process still holds files) ----
set "FAILED=0"
if exist "%T1%" set "FAILED=1"
if exist "%T2%" set "FAILED=1"
if defined T3 (
    if exist "%T3%" set "FAILED=1"
)
if "%FAILED%"=="1" (
    echo.
    echo [ERROR] Some target folders could not be fully deleted.
    if exist "%T1%" echo         %T1%
    if exist "%T2%" echo         %T2%
    if defined T3 (
        if exist "%T3%" echo         %T3%
    )
    echo         A backend process may still hold files. Close it, then rerun.
) else (
    del "%REPO%\*.pid" >nul 2>nul
    echo.
    echo Done. Runtime data cleared. Pid files removed.
    echo Run start.cmd to boot a brand-new environment.
)
echo.
pause
endlocal
