@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    python tools\set_version.py --show
    echo.
    echo Usage: Set_Version.bat ^<new_version^>
    echo Example: Set_Version.bat 0.1.1-beta
    echo.
    pause
    exit /b 0
)

python tools\set_version.py %1
echo.
pause
