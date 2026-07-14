@echo off
chcp 65001 >nul
powershell -Command ^
  $wshell = New-Object -ComObject WScript.Shell; ^
  $desktop = [Environment]::GetFolderPath('Desktop'); ^
  $shortcut = $wshell.CreateShortcut($desktop + '\Signal Staff Control.lnk'); ^
  $shortcut.TargetPath = '%~dp0Signal Staff Control.exe'; ^
  $shortcut.WorkingDirectory = '%~dp0'; ^
  $shortcut.IconLocation = '%~dp0icon.ico, 0'; ^
  $shortcut.Description = 'Signal Staff Control'; ^
  $shortcut.Save()
echo Shortcut created on your desktop!
pause
