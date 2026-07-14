@echo off
chcp 65001 >nul
echo ============================================
echo   Building Telegram Staff Control Executable
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] Installing dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
echo Done.
echo.

echo [2/3] Building executable (this may take a few minutes)...
.venv\Scripts\pyinstaller TelegramStaffControl.spec --noconfirm
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)
echo Done.
echo.

echo [3/3] Copying icon files and .env template...
if exist "icon.ico" copy "icon.ico" "dist\icon.ico" >nul 2>&1
if exist "icon.webp" copy "icon.webp" "dist\icon.webp" >nul 2>&1
if not exist "dist\.env" (
    if exist ".env.example" (
        copy ".env.example" "dist\.env" >nul 2>&1
    ) else if exist ".env" (
        copy ".env" "dist\.env" >nul 2>&1
    )
)
echo Done.
echo.

echo ============================================
echo   BUILD COMPLETE!
echo ============================================
echo.
echo Executable: dist\TelegramStaffControl.exe
echo.
echo IMPORTANT:
echo 1. Place the exe and icon files anywhere
echo 2. Place a .env file NEXT to the exe with:
echo    TELEGRAM_API_ID=your_api_id
echo    TELEGRAM_API_HASH=your_api_hash
echo    SUPABASE_URL=https://your-project.supabase.co
echo    SUPABASE_ANON_KEY=your_anon_key
echo    SERVICE_ROLE_KEY=your_service_role_key
echo 3. Run TelegramStaffControl.exe
echo.
pause
