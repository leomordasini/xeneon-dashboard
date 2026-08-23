@echo off
:: Xeneon Dashboard - Named Tunnel Setup
:: Run this ONCE as Administrator after cloning the repo
:: Prerequisites: cloudflared.exe in this folder, mordasin.com on Cloudflare

echo ==========================================
echo  Xeneon Dashboard - One-Time Setup
echo ==========================================
echo.

set SCRIPT_DIR=%~dp0

:: Step 1 - Log into Cloudflare (opens browser)
echo [1/4] Logging into Cloudflare...
"%SCRIPT_DIR%cloudflared.exe" tunnel login
echo.

:: Step 2 - Create the named tunnel
echo [2/4] Creating named tunnel "xeneon"...
"%SCRIPT_DIR%cloudflared.exe" tunnel create xeneon
echo.
echo NOTE: Copy the Tunnel ID shown above.
echo Edit cloudflared-config.yml and replace ^<TUNNEL-ID^> and ^<YOUR-USERNAME^>
echo Then press any key to continue...
pause > nul

:: Step 3 - Create DNS record on Cloudflare
echo [3/4] Creating DNS record xeneon.mordasin.com...
"%SCRIPT_DIR%cloudflared.exe" tunnel route dns xeneon xeneon.mordasin.com
echo.

:: Step 4 - Register Task Scheduler tasks
echo [4/4] Registering Task Scheduler tasks...

schtasks /create /tn "XeneonDashboard" /tr "pythonw \"%SCRIPT_DIR%server.py\"" /sc onlogon /delay 0000:05 /rl highest /f
schtasks /create /tn "XeneonTunnel" /tr "pythonw \"%SCRIPT_DIR%tunnel.py\"" /sc onlogon /delay 0000:10 /rl highest /f

echo.
echo ==========================================
echo  Setup complete!
echo  Dashboard will be live at:
echo  https://xeneon.mordasin.com/lights.html
echo ==========================================
echo.
echo Rebooting now will auto-start everything.
echo Or run start_server.bat to start manually.
pause
