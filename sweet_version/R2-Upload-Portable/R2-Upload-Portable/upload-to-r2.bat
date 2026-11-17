@echo off
setlocal

if "%~1"=="" (
    echo Drag one or more files onto this script ^(or its Desktop shortcut^) to upload to Cloudflare R2.
    echo.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\upload-to-r2.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    pause
)

exit /b %EXIT_CODE%
