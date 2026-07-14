@echo off
setlocal
python -m pip install --requirement requirements.txt pyinstaller==6.6.0
if errorlevel 1 exit /b 1
python -m PyInstaller --clean --noconfirm telegram-sidecar.spec
if errorlevel 1 exit /b 1
echo Telegram sidecar created at dist\telegram-sidecar.exe
