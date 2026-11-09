@echo off
setlocal
if not exist "%~dp0.venv\Scripts\python.exe" exit /b 2
pushd "%~dp0"
set QT_QPA_PLATFORM=offscreen
".venv\Scripts\python.exe" -m unittest discover -s tests -v
set "EFFSUITE_TEST_EXIT=%ERRORLEVEL%"
popd
exit /b %EFFSUITE_TEST_EXIT%
