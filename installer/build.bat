@echo off
setlocal

echo ===============================
echo  RemoteHub Agent - Full Rebuild
echo ===============================

cd /d "%~dp0"

echo.
echo [0/4] Activating virtual environment...
call "..\.venv\Scripts\activate.bat"
if errorlevel 1 (
    echo FAILED - could not activate venv
    pause
    exit /b 1
)

echo.
echo [1/4] Cleaning old build artifacts...
if exist "..\dist" rmdir /s /q "..\dist"
if exist "..\build" rmdir /s /q "..\build"

echo.
echo [2/4] Building EXE with PyInstaller...
pyinstaller RemoteHubAgent.spec --clean --distpath ..\dist --workpath ..\build
if errorlevel 1 (
    echo BUILD FAILED - PyInstaller error
    pause
    exit /b 1
)

if not exist "..\dist\RemoteHubAgent.exe" (
    echo BUILD FAILED - dist\RemoteHubAgent.exe not found
    pause
    exit /b 1
)

echo.
echo [3/4] Building installer with Inno Setup...
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
%ISCC% "RemoteHubAgent.iss"
if errorlevel 1 (
    echo BUILD FAILED - Inno Setup error
    pause
    exit /b 1
)

echo.
echo [4/4] Done! Installer created at Output\RemoteHubAgentSetup.exe
echo.
pause