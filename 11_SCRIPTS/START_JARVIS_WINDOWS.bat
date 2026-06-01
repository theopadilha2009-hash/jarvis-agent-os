@echo off
cd /d "%~dp0\.."
powershell -ExecutionPolicy Bypass -File "11_SCRIPTS\start_jarvis_windows.ps1"
pause
