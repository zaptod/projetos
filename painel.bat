@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw painel_ui.py
) else (
    python painel_ui.py
)
