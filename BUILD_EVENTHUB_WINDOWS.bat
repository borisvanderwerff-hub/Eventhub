@echo off
setlocal
cd /d "%~dp0"

echo EventHub Windows-build
if not exist "settings_gear.png" (
    echo settings_gear.png ontbreekt.
    pause
    exit /b 1
)

if not exist "eventhub_logo.png" (
    echo eventhub_logo.png ontbreekt.
    pause
    exit /b 1
)

if not exist "eventhub.ico" (
    echo eventhub.ico ontbreekt.
    pause
    exit /b 1
)

if not exist "server\web\app.py" (
    echo De Event Control-servercomponenten ontbreken.
    pause
    exit /b 1
)

where py >nul 2>&1
if errorlevel 1 (
    echo Python 3.12 of nieuwer is niet gevonden.
    echo Installeer Python vanaf https://www.python.org/downloads/windows/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 goto :python_error
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 goto :install_error
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :install_error

".venv\Scripts\python.exe" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    EventHub.spec
if errorlevel 1 goto :build_error

xcopy /E /I /Y "browser_extension" "dist\EventHub\Browserassistent" >nul
if errorlevel 1 goto :build_error

xcopy /E /I /Y "assets" "dist\EventHub\assets" >nul
if errorlevel 1 goto :build_error
".venv\Scripts\python.exe" verify_windows_assets.py "dist\EventHub"
if errorlevel 1 goto :build_error

".venv\Scripts\python.exe" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    "EventHub Server.spec"
if errorlevel 1 goto :build_error

echo.
".venv\Scripts\python.exe" verify_windows_packages.py
if errorlevel 1 goto :build_error
echo Klaar: dist\EventHub\EventHub.exe
echo Standalone: dist\EventHub Server\EventHub Server.exe
if /I "%~1"=="--no-start" exit /b 0
start "" "dist\EventHub\EventHub.exe"
exit /b 0

:python_error
echo Python kon niet worden voorbereid.
pause
exit /b 1

:install_error
echo De benodigde pakketten konden niet worden geinstalleerd.
pause
exit /b 1

:build_error
echo De Windows-build is mislukt.
pause
exit /b 1
