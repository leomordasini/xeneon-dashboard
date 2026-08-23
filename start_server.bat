@echo off
set SCRIPT_DIR=%~dp0
echo Starting Xeneon Dashboard...
start "" pythonw "%SCRIPT_DIR%server.py"
timeout /t 2 > nul
echo Starting OSC Bridge...
start "" pythonw "%SCRIPT_DIR%osc_bridge.py"
timeout /t 3 > nul
echo Starting Cloudflare tunnel...
start "" pythonw "%SCRIPT_DIR%tunnel.py"
echo.
echo Dashboard at: https://xeneon.mordasin.com/lights.html
