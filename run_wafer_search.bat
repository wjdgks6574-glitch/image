@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "wafer_search.py"
) else (
    start "" python "wafer_search.py"
)
