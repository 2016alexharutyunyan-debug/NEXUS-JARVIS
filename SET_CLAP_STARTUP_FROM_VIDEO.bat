@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Set JARVIS Clap Startup Sound

if not exist "payload\.venv\Scripts\python.exe" (
  echo ERROR: Run INSTALL_JARVIS.bat first.
  pause
  exit /b 1
)

set "VIDEO=%~1"
if not defined VIDEO (
  echo Drag your video into this window, then press Enter.
  set /p "VIDEO=Video: "
)
set "VIDEO=%VIDEO:"=%"

"payload\.venv\Scripts\python.exe" "payload\set_startup_from_video.py" "%VIDEO%"
if errorlevel 1 goto :fail

echo.
echo Ready. Start START_WAKE_LAUNCHER.bat and clap once near the microphone.
pause
exit /b 0

:fail
echo.
echo Could not create the startup sound. Check the video path and try again.
pause
exit /b 1
