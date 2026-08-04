@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0infrastructure\windows\setup_windows.ps1"
pause
