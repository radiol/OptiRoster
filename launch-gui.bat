@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ---- move to project root (this .bat location) ----
cd /d "%~dp0"

REM ---- check uv ----
where uv >nul 2>nul
if errorlevel 1 (
    echo [info] uv not found. trying to install...

    REM 1) try winget
    where winget >nul 2>nul
    if not errorlevel 1 (
        echo [info] trying winget install...
        winget install -e --id astral-sh.uv --silent --accept-package-agreements --accept-source-agreements
    )

    REM 2) if still not found, run official installer via PowerShell
    where uv >nul 2>nul
    if errorlevel 1 (
        echo [info] uv still not found. trying PowerShell installer...

        set "POWERSHELL="

        REM prefer PowerShell 7 if available, then Windows PowerShell
        for %%P in (pwsh.exe powershell.exe) do (
            where %%P >nul 2>nul && (
                set "POWERSHELL=%%P"
                goto :ps_found
            )
        )

        REM fallback to standard Windows PowerShell path
        if not defined POWERSHELL if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" (
            set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
        )

:ps_found
        if not defined POWERSHELL (
            echo [error] no PowerShell found. cannot install uv.
            exit /b 1
        )

        REM install uv to a project-local dir (CI friendly)
        set "UV_INSTALL_DIR=%CD%\.uv-bin"

        "!POWERSHELL!" -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command ^
            "$ErrorActionPreference='Stop';" ^
            "$env:UV_INSTALL_DIR='!UV_INSTALL_DIR!';" ^
            "$env:UV_NO_MODIFY_PATH='1';" ^
            "irm https://astral.sh/uv/install.ps1 | iex"

        REM make it visible in this session
        set "PATH=!UV_INSTALL_DIR!;!PATH!"
    )
)

REM ---- add common install dirs to PATH for this session ----
set "PATH=%USERPROFILE%\.local\bin;%LOCALAPPDATA%\Programs\uv\bin;%LOCALAPPDATA%\uv\bin;%PATH%"

REM ---- final check ----
where uv >nul 2>nul
if errorlevel 1 (
    echo [error] failed to install uv.
    exit /b 1
)

REM ---- run the app ----
REM In CI, do not start GUI. Just smoke-test import.
if /i "%~1"=="--ci" (
    uv --version || exit /b 1
    uv run python -c "import src.gui.app; print('smoke: import ok')" || exit /b 1
    exit /b 0
)

REM ---- run the GUI app ----
uv run python -m src.gui.app
