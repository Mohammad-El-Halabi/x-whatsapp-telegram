@echo off
chcp 65001 >nul
echo Building Signal Staff Control...

cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

.venv\Scripts\pyinstaller.exe "Signal Staff Control.spec" --clean --noconfirm

if %errorlevel% neq 0 (
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo Build complete! dist\Signal Staff Control.exe
echo ============================================
echo.
echo === Deployment Checklist ===
echo Place these NEXT to the .exe:
echo.
echo   [REQUIRED] .env  - create from .env.example:
echo     SUPABASE_URL=https://your-project.supabase.co
echo     SUPABASE_ANON_KEY=your_anon_key
echo     SIGNAL_CLI_PATH=signal-cli-wrapper.bat
echo.
echo   [REQUIRED] Run prepare-runtime.ps1, then copy next to the exe:
echo     signal-cli-wrapper.bat, signal-cli\, and runtime\java\
echo.
echo   The preparation script supplies the required Java runtime.
echo.
echo ============================================
pause
