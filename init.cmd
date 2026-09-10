@echo off
rem ============================================================
rem  OJ environment setup (Windows, one-click)
rem  - Checks WSL toolchain: python3, g++
rem  - Creates/validates WSL venv  ~/oj-venv   (backend + tests)
rem  - Creates/validates Windows .venv         (streamlit frontend)
rem  - Idempotent: existing venvs are skipped; "init.cmd rebuild" recreates them
rem  - Portable: repo can live in any folder on any drive (mapped to /mnt/<drive>)
rem  After setup, run start.cmd
rem ============================================================
setlocal EnableExtensions

set "REPO=%~dp0"
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"

rem ---- map Windows repo path to WSL path: E:\a\b -> /mnt/e/a/b ----
set "DRV=%~d0"
set "WDRV="
for %%L in (a b c d e f g h i j k l m n o p q r s t u v w x y z) do (
    if /i "%DRV%"=="%%L:" set "WDRV=%%L"
)
if not defined WDRV (
    echo [ERROR] Drive %DRV% could not be mapped to a WSL mount.
    pause
    exit /b 1
)
set "WP=%~p0"
set "WP=%WP:\=/%"
if "%WP:~-1%"=="/" set "WP=%WP:~0,-1%"
set "WROOT=/mnt/%WDRV%%WP%"

set "REBUILD="
if /i "%~1"=="rebuild" set "REBUILD=1"

echo Repo (Windows): %REPO%
echo Repo (WSL)    : %WROOT%

rem ---- [1/4] WSL toolchain ----
echo [1/4] Checking WSL toolchain (python3, g++) ...
wsl -e bash -lc "command -v python3 >/dev/null 2>&1 && command -v g++ >/dev/null 2>&1"
if errorlevel 1 (
    echo [WARN] python3 and/or g++ missing inside WSL.
    echo        Install once in WSL: sudo apt update ^&^& sudo apt install -y python3 python3-venv g++
    echo        Continuing; API can still run, but judging needs both.
) else (
    echo       OK: python3 and g++ found.
)

rem ---- [2/4] WSL venv (~/oj-venv) ----
if defined REBUILD (
    echo [2/4] Rebuild requested: removing ~/oj-venv ...
    wsl -e bash -lc "rm -rf $HOME/oj-venv"
)
echo [2/4] Setting up WSL venv ~/oj-venv ...
wsl -e bash -lc "test -x $HOME/oj-venv/bin/python"
if not errorlevel 1 (
    echo       OK: already exists ^(skip^). Use init.cmd rebuild to recreate.
) else (
    wsl -e bash -lc "python3 -m venv $HOME/oj-venv && $HOME/oj-venv/bin/python -m pip install --upgrade pip -q && $HOME/oj-venv/bin/python -m pip install -q fastapi 'uvicorn[standard]' pydantic httpx pytest psutil bcrypt python-multipart"
    if errorlevel 1 (
        echo [ERROR] Failed to create the WSL venv. See output above.
        pause
        exit /b 1
    )
    echo       OK: created ^(backend + test dependencies^).
)

rem ---- [3/4] Windows venv (.venv) ----
if defined REBUILD (
    echo [3/4] Rebuild requested: removing .venv ...
    if exist "%REPO%\.venv" rmdir /s /q "%REPO%\.venv"
)
echo [3/4] Setting up Windows venv .venv ...
if exist "%REPO%\.venv\Scripts\python.exe" (
    echo       OK: already exists ^(skip^). Use init.cmd rebuild to recreate.
) else (
    set "PY="
    where py >nul 2>nul && set "PY=py -3"
    if not defined PY where python >nul 2>nul && set "PY=python"
    if not defined PY (
        echo [ERROR] Python not found on Windows PATH. Install Python 3.12+ first.
        pause
        exit /b 1
    )
    %PY% -m venv "%REPO%\.venv"
    if errorlevel 1 (
        echo [ERROR] Failed to create .venv.
        pause
        exit /b 1
    )
    "%REPO%\.venv\Scripts\python.exe" -m pip install --upgrade pip -q
    "%REPO%\.venv\Scripts\python.exe" -m pip install -q -r "%REPO%\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] pip install failed. See output above.
        pause
        exit /b 1
    )
    echo       OK: created ^(streamlit frontend dependencies^).
)

rem ---- [4/4] Summary ----
echo [4/4] Environment ready.
echo       start.cmd  -^> start backend :8000 + frontend :8501
echo       stop.cmd   -^> stop backend
echo       clear.cmd  -^> factory reset runtime data ^(backend\data^)
echo       Tests      -^> wsl -e bash -lc "cd backend ^&^& ~/oj-venv/bin/python -m pytest tests -q"   ^(run inside repo's backend^)
pause
endlocal
