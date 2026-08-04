@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher not found. Install Python 3.10 first.
    pause
    exit /b 1
)
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo Aksh virtual environment not found. Run setup_aksh.bat first.
    pause
    exit /b 1
)
"%~dp0.venv\Scripts\python.exe" aksh.py
if errorlevel 1 pause
