@echo off
cd /d "%~dp0"
py -3 11_SCRIPTS\jarvis_main_cli.py %*
exit /b %ERRORLEVEL%
