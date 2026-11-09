@echo off
setlocal
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Run Setup_Windows.bat first with your selected Python.
  exit /b 2
)
"%~dp0.venv\Scripts\python.exe" -m effsuite.app_cli %*
exit /b %ERRORLEVEL%
