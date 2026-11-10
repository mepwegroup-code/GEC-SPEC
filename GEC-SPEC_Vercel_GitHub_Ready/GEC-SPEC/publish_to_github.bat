@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish_to_github.ps1"
if errorlevel 1 (
  echo.
  echo GEC Specifications publish failed. See the message above.
  pause
  exit /b 1
)
echo.
echo GitHub upload completed.
pause
