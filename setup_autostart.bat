@echo off
:: Xeneon Dashboard — Full Setup
:: Run ONCE as Administrator
:: Registers both the HTTP server and cloudflared tunnel to start on login

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

:: Check cloudflared
if not exist "%DIR%cloudflared.exe" (
    echo [ERROR] cloudflared.exe not found in %DIR%
    echo Download from:
    echo https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
    echo Save it as: %DIR%cloudflared.exe
    pause & exit /b 1
)

:: Remove old tasks
schtasks /delete /tn "XeneonDashboard" /f >nul 2>&1
schtasks /delete /tn "XeneonTunnel"    /f >nul 2>&1

:: Register dashboard server (silent, no window)
echo Registering dashboard server...
schtasks /create /tn "XeneonDashboard" ^
  /tr "pythonw \"%DIR%server.py\"" ^
  /sc onlogon /rl highest /delay 0000:05 /f >nul 2>&1
if errorlevel 1 (
    echo [WARN] Could not register XeneonDashboard task. Make sure you ran as Admin.
) else (
    echo [OK] XeneonDashboard task registered.
)

:: Register tunnel (silent, no window)
echo Registering tunnel...
schtasks /create /tn "XeneonTunnel" ^
  /tr "pythonw \"%DIR%tunnel.py\"" ^
  /sc onlogon /rl highest /delay 0000:08 /f >nul 2>&1
if errorlevel 1 (
    echo [WARN] Could not register XeneonTunnel task. Make sure you ran as Admin.
) else (
    echo [OK] XeneonTunnel task registered.
)

:: Kill any existing instances
taskkill /f /im pythonw.exe >nul 2>&1
taskkill /f /im cloudflared.exe >nul 2>&1
timeout /t 1 >nul

:: Start server now
echo.
echo Starting server...
start "" pythonw "%DIR%server.py"
timeout /t 2 >nul
echo [OK] Server started on http://localhost:8080

:: Start tunnel now
echo Starting tunnel...
start "" pythonw "%DIR%tunnel.py"

echo.
echo Waiting for tunnel URL (up to 20 seconds)...
set WAITED=0
:WAITLOOP
timeout /t 2 >nul
set /a WAITED+=2
if exist "%DIR%tunnel_url.txt" goto GOTURL
if %WAITED% GEQ 20 goto TIMEOUT
goto WAITLOOP

:GOTURL
echo.
echo =====================================================
echo  Setup complete!
echo.
type "%DIR%tunnel_url.txt"
echo.
echo  Copy the lights.html URL above into iCUE:
echo  Web URL widget → Size XL → paste URL
echo.
echo  NOTE: This URL changes each reboot. Check
echo  C:\xeneon-dashboard\tunnel_url.txt after restart.
echo =====================================================
echo.
pause
goto END

:TIMEOUT
echo.
echo [WARN] Tunnel URL not captured yet. Check tunnel_url.txt in a few seconds.
echo.
pause

:END
