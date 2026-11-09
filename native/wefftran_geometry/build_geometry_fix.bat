@echo off
setlocal
if not defined WEFFTRAN_FC set "WEFFTRAN_FC=gfortran"
"%WEFFTRAN_FC%" --version
if errorlevel 1 (
  echo GNU Fortran was not found. Set WEFFTRAN_FC to your selected compiler path.
  exit /b 1
)
set "WEFFTRAN_GEOMETRY_BUILD=%~dp0build_geometry_fix"
if not exist "%WEFFTRAN_GEOMETRY_BUILD%" mkdir "%WEFFTRAN_GEOMETRY_BUILD%"
for %%S in (total scatter eta) do (
  "%WEFFTRAN_FC%" -O3 -static -o "%WEFFTRAN_GEOMETRY_BUILD%\%%S.exe" "%~dp0%%S.f"
  if errorlevel 1 exit /b 1
)
echo Built geometry executables in "%WEFFTRAN_GEOMETRY_BUILD%".
echo The original WEFFTRAN installation has not been changed.
endlocal
