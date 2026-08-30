@echo off
setlocal
cd /d "%~dp0"

echo EventHub 2.20.1 bouwen en verpakken...
call BUILD_EVENTHUB_WINDOWS.bat --no-start
if errorlevel 1 exit /b 1

set "ISCC_PATH="
where ISCC.exe >nul 2>&1
if not errorlevel 1 set "ISCC_PATH=ISCC.exe"
if not defined ISCC_PATH if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe" set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 7\ISCC.exe"

if not defined ISCC_PATH (
    echo Inno Setup 6 is niet gevonden.
    echo Installeer Inno Setup en start dit bestand opnieuw.
    pause
    exit /b 1
)

"%ISCC_PATH%" "EventHub_Installer.iss"
if errorlevel 1 (
    echo De installer kon niet worden gemaakt.
    pause
    exit /b 1
)

echo.
echo Klaar: installer\EventHub-Setup-v2.20.1.exe
start "" "installer"
pause
