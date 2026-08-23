@echo off
:: Xeneon Dashboard — Auto-start Setup
:: Run ONCE as Administrator

set "DIR=%~dp0"

echo === Xeneon Dashboard Setup ===
echo.

:: Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Download from https://python.org — check "Add Python to PATH"
    pause & exit /b 1
)

:: Install cryptography for cert generation
echo Installing dependencies...
python -m pip install cryptography --quiet

:: Generate SSL certificate and install to Windows trust store
echo.
echo Generating SSL certificate...
python "%DIR%generate_cert.py"
if errorlevel 1 (
    echo [ERROR] Certificate generation failed.
    pause & exit /b 1
)

:: Register Task Scheduler
echo.
echo Registering auto-start on login...
schtasks /delete /tn "XeneonDashboard" /f >nul 2>&1
schtasks /create /tn "XeneonDashboard" /tr "pythonw \"%DIR%server.py\"" /sc onlogon /rl highest /f >nul 2>&1
if errorlevel 1 (
    echo [WARN] Task Scheduler needs Administrator. Re-run as Admin.
) else (
    echo [OK] Auto-start registered.
)

:: Start server now
echo.
echo Starting server...
start "" pythonw "%DIR%server.py"
timeout /t 2 >nul

echo.
echo =====================================================
echo  Server running!
echo  URL: https://192.168.1.148:8080/lights.html
echo.
echo  In iCUE: Web URL widget, Size XL
echo  Paste:   https://192.168.1.148:8080/lights.html
echo =====================================================
echo.
pause
