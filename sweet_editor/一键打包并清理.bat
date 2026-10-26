@echo off
chcp 936 >nul
title sweet_editor Android 一键打包（清理缓存）
cd /d "%~dp0"
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo ============================================
echo   sweet_editor Android 一键打包（清理缓存）
echo   资源路径: android-build.config.json
echo   输出目录: %PROJECT_DIR%\Builds\Android
echo.
echo   打包成功后会删除 Library / Temp 和 MapEditorSeed.zip，
echo   但不会删除工程、Assets、ProjectSettings、APK。
echo   下次打包会重新导入资源并重新生成 zip，速度会慢一些。
echo ============================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0BuildStandalone.ps1" -ProjectPath "%PROJECT_DIR%" -DeleteSeedAfterBuild -CleanLibraryAfterBuild
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
    echo 打包完成，缓存和临时资源已清理。
) else (
    echo 打包失败，请查看 Builds\Android\build.log
)
explorer "%PROJECT_DIR%\Builds\Android"
pause
exit /b %EXITCODE%
