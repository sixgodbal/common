@echo off
cd /d "%~dp0"
for %%f in (*.pyw) do start "" pythonw "%%~ff"
