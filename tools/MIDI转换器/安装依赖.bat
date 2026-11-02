@echo off
cd /d "%~dp0"
echo Installing numpy, soundfile and lameenc...
python -m pip install --upgrade numpy soundfile lameenc
if errorlevel 1 (
    echo.
    echo Install failed. Please make sure Python and pip are available.
) else (
    echo.
    echo Done. You can now run the app.
)
pause
