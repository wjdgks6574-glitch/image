@echo off
cd /d "%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw "wafer_search_v2.py"
    goto :eof
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "wafer_search_v2.py"
    goto :eof
)
start "" python "wafer_search_v2.py"
