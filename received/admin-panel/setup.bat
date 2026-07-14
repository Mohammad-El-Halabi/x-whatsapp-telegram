@echo off
title Staff Admin Panel - Setup
echo ========================================
echo   Staff Admin Panel - Setup
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

:: Create virtual environment
if not exist ".venv" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
) else (
    echo [1/4] Virtual environment already exists
)

:: Activate and install
echo [2/4] Installing dependencies...
call .venv\Scripts\activate.bat
pip install -r requirements.txt

:: Check .env
if not exist ".env" (
    echo [3/4] Creating .env from template...
    copy .env.example .env
    echo.
    echo [IMPORTANT] Edit .env with your Supabase credentials before running!
    echo.
) else (
    echo [3/4] .env file found
)

echo [4/4] Setup complete!
echo.
echo To start the app:
echo   run.bat
echo.
echo Or manually:
echo   .venv\Scripts\activate ^&^& python run.py
echo.

pause
