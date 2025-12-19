@echo off
setlocal
REM ---- move to project root (this .bat location) ----
cd /d "%~dp0"

REM ---- check uv ----
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [info] uv not found. trying to install...

    REM 1) try winget
    where winget >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        winget install --id astral-sh.uv -e --silent
    )

    REM 2) if still not found, run official installer via PowerShell (no .ps1 files)
    where uv >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        set "POWERSHELL="
        REM try powershell.exe from PATH
        where powershell.exe >nul 2>nul && set "POWERSHELL=powershell.exe"
        REM fallback to standard Windows PowerShell path
        if not defined POWERSHELL if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
        REM try PowerShell 7 (pwsh)
        if not defined POWERSHELL where pwsh.exe >nul 2>nul && set "POWERSHELL=pwsh.exe"

        if not defined POWERSHELL (
            echo [error] no PowerShell found. cannot install uv.
            exit /b 1
        )

        %POWERSHELL% -NoProfile -ExecutionPolicy Bypass -Command "try { iwr -UseBasicParsing https://astral.sh/uv/install.ps1 | iex } catch { exit 1 }"
    )
)

REM ---- uv usually installs to %USERPROFILE%\.local\bin ; add to PATH for this session ----
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

REM ---- final check ----
where uv >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [error] failed to install uv.
    exit /b 1
)

REM ---- run the app ----
REM CIではGUIを起動せず、importできるかだけ確認
if /i "%~1"=="--ci" (
    uv --version || exit /b 1
    uv run -c "import src.gui.app; print('smoke: import ok')" || exit /b 1
    exit /b 0
)

REM ---- run the GUI app ----
uv run -m src.gui.app
