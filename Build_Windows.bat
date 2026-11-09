@echo off
setlocal
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo Run Setup_Windows.bat first.
  pause
  exit /b 2
)
pushd "%~dp0"
".venv\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean EffSuite.spec
if errorlevel 1 goto failed
for %%F in (README.md USER_GUIDE.md MATERIALS.md VALIDATION.md THIRD_PARTY_NOTICES.md) do copy /y "%%F" "dist\EffSuite\%%F" >nul
copy /y "src\effsuite\assets\templates\Material_Composition.xlsx" "dist\EffSuite\Material_Composition.xlsx" >nul
echo GUI and CLI executables are in dist\EffSuite.
echo To create an installer, compile installer\EffSuite.iss with Inno Setup 7.
popd
pause
exit /b 0
:failed
popd
pause
exit /b 1
