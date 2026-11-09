@echo off
setlocal
if not exist "%~dp0.venv\Scripts\python.exe" exit /b 2
"%~dp0.venv\Scripts\python.exe" -m effsuite.lab_comparison %*
