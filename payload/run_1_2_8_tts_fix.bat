@echo off
setlocal EnableExtensions
cd /d "%~dp0" || exit /b 1
title JARVIS HoloDesk 2.6.0

echo ==========================================
echo JARVIS HoloDesk 2.6.0 - SCREEN-AWARE VOICE CONTROL
echo Voice recognition: ON
echo Voice replies: ON
echo Hand control: OFF
echo ==========================================
echo.

for %%F in ("main.py" "pc_voice.py" "location_map.py" "google_location.py" "mini_jarvis.py" "screen_agent.py" "assets\location\index.html" "assets\location\location.js" "assets\location\leaflet.js" "assets\location\leaflet.css") do (
  if not exist "%%~F" (
    echo ERROR: Missing %%~F. Extract the complete ZIP first.
    if /I not "%~1"=="--check" pause
    exit /b 1
  )
)

if /I "%~1"=="--check" (
  echo JARVIS package check OK.
  exit /b 0
)

for /f "tokens=2,*" %%A in ('reg query HKCU\Environment /v GEMINI_API_KEY 2^>nul ^| findstr GEMINI_API_KEY') do set "GEMINI_API_KEY=%%B"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "main.py"
) else (
  python "main.py"
)

set "JARVIS_EXIT=%ERRORLEVEL%"
if not "%JARVIS_EXIT%"=="0" (
  echo.
  echo HoloDesk stopped with an error.
  pause
)
exit /b %JARVIS_EXIT%
