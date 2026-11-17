@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\create-desktop-shortcuts.ps1"
echo.
pause
exit /b %ERRORLEVEL%
