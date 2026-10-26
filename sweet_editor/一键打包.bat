@echo off
chcp 936 >nul
title sweet_editor Android 一键打包
cd /d "%~dp0"
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo ============================================
echo   sweet_editor Android 一键打包（保留缓存）
echo   资源路径: android-build.config.json
echo   输出目录: %PROJECT_DIR%\Builds\Android
echo ============================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0BuildStandalone.ps1" -ProjectPath "%PROJECT_DIR%"
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
    echo 打包完成。
) else (
    echo 打包失败，请查看 Builds\Android\build.log
)
explorer "%PROJECT_DIR%\Builds\Android"
pause
exit /b %EXITCODE%
