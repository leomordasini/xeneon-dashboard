@echo off
set SCRIPT_DIR=%~dp0
echo Starting Xeneon Dashboard server...
start "" pythonw "%SCRIPT_DIR%server.py"
timeout /t 3 > nul
echo Starting Cloudflare tunnel...
start "" pythonw "%SCRIPT_DIR%tunnel.py"
echo.
echo Dashboard will be available at:
echo https://xeneon.mordasin.com/lights.html
