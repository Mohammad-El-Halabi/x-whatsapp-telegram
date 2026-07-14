@echo off
chcp 65001 >nul
echo ============================================
echo   Building SMS Staff Control Executable
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] Installing dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
echo Done.
echo.

echo [2/3] Building executable (this may take a few minutes)...
.venv\Scripts\pyinstaller SMSStaffControl.spec --noconfirm
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)
echo Done.
echo.

echo [3/3] Copying .env template...
if not exist "dist\.env" (
    copy ".env" "dist\.env" >nul 2>&1
)
echo Done.
echo.

echo ============================================
echo   BUILD COMPLETE!
echo ============================================
echo.
echo Executable: dist\SMSStaffControl.exe
echo.
echo IMPORTANT:
echo 1. Place dist\SMSStaffControl.exe anywhere
echo 2. Place a .env file NEXT to the exe with:
echo    SUPABASE_URL, SUPABASE_ANON_KEY, SERVICE_ROLE_KEY
echo    MODEM_PORT, MODEM_BAUD
echo 3. Run SMSStaffControl.exe
echo.
pause
