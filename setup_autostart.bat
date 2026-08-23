@echo off
:: Xeneon Dashboard — Auto-start Setup
:: Run this ONCE as Administrator. It registers the server to start
:: silently on every Windows login via Task Scheduler.

set "DIR=%~dp0"
set "PYTHON=%DIR%venv\Scripts\pythonw.exe"
set "SCRIPT=%DIR%server.py"

:: Check for Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python from https://python.org
    pause & exit /b 1
)

:: Create venv if not exists
if not exist "%DIR%venv\" (
    echo Creating virtual environment...
    python -m venv "%DIR%venv"
)

:: Use system python if venv pythonw not found
if not exist "%PYTHON%" set "PYTHON=pythonw"

echo Registering Task Scheduler entry...
schtasks /create /tn "XeneonDashboard" /tr "\"%PYTHON%\" \"%SCRIPT%\"" /sc onlogon /rl limited /f >nul 2>&1

if errorlevel 1 (
    echo [WARN] Task Scheduler failed. Trying with full python path...
    for /f "delims=" %%i in ('where python') do set PYPATH=%%i
    set "PYPATH=%PYPATH:python.exe=pythonw.exe%"
    schtasks /create /tn "XeneonDashboard" /tr "\"%PYPATH%\" \"%SCRIPT%\"" /sc onlogon /rl limited /f
)

echo.
echo [OK] Xeneon Dashboard will now start automatically on login.
echo      Dashboard URL: http://192.168.1.148:8080/lights.html
echo.
echo Starting server now...
start "" pythonw "%SCRIPT%"
echo Server started silently in background.
echo.
pause
