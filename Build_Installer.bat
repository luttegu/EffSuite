@echo off
setlocal EnableDelayedExpansion

pushd "%~dp0"

echo =====================================================================
echo  EffSuite - Inno Setup Installer Builder
echo =====================================================================
echo.

if not exist "dist\EffSuite\EffSuite_GUI.exe" (
    echo Binary distribution not found in dist\EffSuite.
    echo Running Build_Windows.bat first...
    call Build_Windows.bat
    if errorlevel 1 goto :failed
)

set "ISCC_PATH="
if exist "C:\Program Files\Inno Setup 7\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 7\ISCC.exe"
) else if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else (
    for /f "tokens=*" %%i in ('where iscc 2^>nul') do (
        set "ISCC_PATH=%%i"
    )
)

if "%ISCC_PATH%"=="" (
    echo [ERROR] Inno Setup compiler ^(ISCC.exe^) was not found.
    echo Please install Inno Setup 7 from https://jrsoftware.org/isdl.php
    pause
    popd
    exit /b 1
)

echo Using compiler: "!ISCC_PATH!"
echo Compiling installer\EffSuite.iss...
echo.

"!ISCC_PATH!" "installer\EffSuite.iss"
if errorlevel 1 goto :failed

echo.
echo =====================================================================
echo  BUILD SUCCESSFUL!
echo  Installer output: %~dp0installer_output\EffSuite_0.1.0-beta_Setup.exe
echo =====================================================================
echo.
pause
popd
exit /b 0

:failed
echo.
echo [ERROR] Installer build failed. See log messages above.
pause
popd
exit /b 1
