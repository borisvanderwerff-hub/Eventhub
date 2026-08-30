@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 goto :python_error
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto :install_error
)

".venv\Scripts\python.exe" bezoekerslijst_app.py
if errorlevel 1 pause
exit /b

:python_error
echo Python 3.12 is niet gevonden. Installeer Python 3.12 en probeer opnieuw.
pause
exit /b 1

:install_error
echo De benodigde Python-pakketten konden niet worden geinstalleerd.
pause
exit /b 1

