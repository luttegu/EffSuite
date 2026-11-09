@echo off
setlocal
pushd "%~dp0" >nul 2>&1
if errorlevel 1 goto :folder_failed
if not exist ".venv\Scripts\python.exe" goto :no_venv
".venv\Scripts\python.exe" -m publisher.gui
if errorlevel 1 goto :failed
popd
exit /b 0

:no_venv
echo.
echo Active virtual environment not found in .venv.
echo Please create the virtual environment and install dependencies:
echo   py -3 -m venv .venv
echo   .venv\Scripts\pip install -e ".[gui]"
pause
popd
exit /b 1

:failed
echo.
echo Could not start the publisher licence manager. Check python error above.
pause
popd
exit /b 1

:folder_failed
echo.
echo Could not access the application folder: "%~dp0"
pause
exit /b 1
