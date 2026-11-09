@echo off
setlocal
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo Run Setup_Windows.bat first with your selected Python.
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0tools\entry_gui.py"
