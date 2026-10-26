@echo off
cd /d "%~dp0"
echo Installing pynput...
python -m pip install pynput
if errorlevel 1 (
    echo.
    echo Install failed. Please make sure Python and pip are available.
) else (
    echo.
    echo Done. You can now run the application.
)
pause
