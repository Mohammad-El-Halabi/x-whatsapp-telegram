@echo off
chcp 65001 >nul
echo ============================================
echo   Building Admin Panel Executable
echo ============================================
echo.

cd /d "%~dp0"

echo [1/3] Installing PyInstaller...
.venv\Scripts\python.exe -m pip install pyinstaller --quiet
echo Done.
echo.

echo [2/3] Building executable (this may take a few minutes)...
.venv\Scripts\pyinstaller ^
    --onefile ^
    --name "AdminPanel" ^
    --add-data "src\templates;templates" ^
    --add-data "src\static;static" ^
    --hidden-import pydantic ^
    --hidden-import pydantic._internal ^
    --hidden-import pydantic._internal._config ^
    --hidden-import pydantic._internal._model_construction ^
    --hidden-import pydantic.v1 ^
    --hidden-import dotenv ^
    --hidden-import supabase ^
    --hidden-import supabase._sync ^
    --hidden-import gotrue ^
    --hidden-import postgrest ^
    --hidden-import httpx ^
    --hidden-import httpcore ^
    --hidden-import waitress ^
    --hidden-import certifi ^
    --collect-all supabase ^
    --collect-all pydantic ^
    --noconfirm ^
    src\main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)
echo Done.
echo.

echo [3/3] Copying .env.example as .env template...
if not exist "dist\.env" (
    copy ".env.example" "dist\.env.example" >nul
)
echo Done.
echo.

echo ============================================
echo   BUILD COMPLETE!
echo ============================================
echo.
echo Executable: dist\AdminPanel.exe
echo.
echo IMPORTANT:
echo 1. Copy dist\AdminPanel.exe to your customer's PC
echo 2. Create a .env file next to the exe with their Supabase credentials
echo    (use the .env.example file as a template)
echo 3. Run AdminPanel.exe
echo.
pause
