@echo off
:: Kill server and tunnel
taskkill /f /im pythonw.exe >nul 2>&1
taskkill /f /im cloudflared.exe >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8080 ^| findstr LISTENING 2^>nul') do taskkill /f /pid %%a >nul 2>&1
echo Xeneon Dashboard stopped.
timeout /t 2 >nul
