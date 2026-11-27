@echo off
rem Drag a posts\*.json file onto this file to render card PNGs.
if "%~1"=="" (
  echo Drag a .json file from the posts folder onto make.bat
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0render.ps1" -Content "%~1"
if errorlevel 1 (
  pause
  exit /b 1
)
start "" "%~dp0out\%~n1"
