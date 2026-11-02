@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if errorlevel 1 (
    echo Python not found. Please install Python 3.8+ first.
    pause
    exit /b 1
)
for %%f in ("MIDI*.pyw") do start "" pythonw "%%~ff"
