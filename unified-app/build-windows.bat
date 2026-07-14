@echo off
setlocal
cd /d "%~dp0"

echo [1/5] Installing frontend dependencies without lifecycle scripts...
call npm.cmd ci --ignore-scripts --no-audit --no-fund
if errorlevel 1 exit /b 1

echo [2/5] Installing WhatsApp sidecar dependencies without lifecycle scripts...
pushd sidecar
call npm.cmd ci --ignore-scripts --no-audit --no-fund
if errorlevel 1 exit /b 1
popd

echo [3/5] Building the isolated Telegram sidecar...
pushd telegram-sidecar
call build-windows.bat
if errorlevel 1 exit /b 1
popd

echo [4/5] Checking required local configuration...
if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo Created .env from the safe template. Configure it before running the app.
)

echo [5/5] Building the Windows installer...
call npm.cmd run tauri:build
if errorlevel 1 exit /b 1

echo Build complete. See src-tauri\target\release\bundle
endlocal
