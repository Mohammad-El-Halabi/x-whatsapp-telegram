@echo off
chcp 65001 >nul
echo Building Signal Staff Control...

pip install -r requirements.txt

pyinstaller --onefile --windowed --name "Signal Staff Control" ^
  --icon icon.ico ^
  --add-data "logo.webp;." ^
  --add-data "icon.ico;." ^
  --additional-hooks-dir=hooks ^
  --hidden-import=supabase ^
  --hidden-import=aiohttp ^
  --hidden-import=aiohttp.web ^
  --hidden-import=customtkinter ^
  --hidden-import=PIL ^
  --hidden-import=PIL.Image ^
  --hidden-import=dotenv ^
  --hidden-import=qrcode ^
  --hidden-import=pydantic ^
  --collect-all=supabase ^
  --collect-all=customtkinter ^
  --collect-all=pydantic ^
  --collect-all=qrcode ^
  --collect-all Pillow ^
  --exclude-module pkg_resources ^
  --exclude-module setuptools ^
  --noconfirm ^
  run.py

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
echo     SUPABASE_URL=https://wghpuytsnjldzysxnrpm.supabase.co
echo     SUPABASE_KEY=your_anon_key
echo     SUPABASE_SERVICE_KEY=your_service_key
echo     SIGNAL_CLI_PATH=signal-cli\bin\signal-cli.bat
echo     JAVA_HOME=C:\Program Files\Java\jdk-25.0.2
echo.
echo   [REQUIRED] signal-cli\  - copy the entire build folder:
echo     C:\Users\pc\Downloads\signal-cli-master\signal-cli-master\build\install\signal-cli\
echo.
echo   [REQUIRED] Java JDK 25 - install and set JAVA_HOME
echo.
echo ============================================
pause
