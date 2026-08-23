@echo off
echo Stopping Xeneon Dashboard...
taskkill /f /im pythonw.exe 2>nul
taskkill /f /im cloudflared.exe 2>nul
echo Done.