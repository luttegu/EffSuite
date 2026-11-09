@echo off
setlocal
if not "%~1"=="" (
  "%~1" "%~dp0tools\setup_environment.py"
) else (
  python "%~dp0tools\setup_environment.py"
  if errorlevel 9009 py -3 "%~dp0tools\setup_environment.py"
)
if errorlevel 1 (
  echo Setup failed. Read the error above.
  pause
  exit /b 1
)
echo Ready. Double-click Start_GUI.bat.
pause
