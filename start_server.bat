@echo off
:: Manual start — use this to test or restart the server
set "DIR=%~dp0"
echo Starting Xeneon Dashboard server...
start "" pythonw "%DIR%server.py"
timeout /t 2 >nul
echo Server running at http://192.168.1.148:8080/lights.html
pause
