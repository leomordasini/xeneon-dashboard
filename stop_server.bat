@echo off
:: Stop the Xeneon Dashboard server
taskkill /f /im pythonw.exe /fi "WINDOWTITLE eq server*" >nul 2>&1
:: Broader kill in case above misses it
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8080 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
)
echo Xeneon Dashboard server stopped.
timeout /t 2 >nul
