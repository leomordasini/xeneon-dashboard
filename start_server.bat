@echo off
set SCRIPT_DIR=%~dp0
echo Stopping any existing processes...
taskkill /f /im python.exe 2>nul
taskkill /f /im pythonw.exe 2>nul
taskkill /f /im cloudflared.exe 2>nul
timeout /t 1 > nul
echo Starting Xeneon Dashboard (background)...
wscript.exe "%SCRIPT_DIR%start_background.vbs"
echo Done. Dashboard at: https://xeneon.mordasin.com/lights.html
