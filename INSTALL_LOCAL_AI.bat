@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Install Free Local AI for JARVIS

echo ==========================================
echo JARVIS Free Local AI Installer
echo ==========================================
echo.

if exist "payload\.venv\Scripts\python.exe" (
  set "PY=payload\.venv\Scripts\python.exe"
) else (
  echo ERROR: Install JARVIS first with INSTALL_JARVIS.bat.
  pause
  exit /b 1
)

echo Installing local Whisper and Piper packages...
"%PY%" -m pip install --upgrade faster-whisper piper-tts
if errorlevel 1 goto :fail

if not exist "local_models\piper" mkdir "local_models\piper"
pushd "local_models\piper"
echo Downloading the free English Piper voice...
"..\..\payload\.venv\Scripts\python.exe" -m piper.download_voices en_US-lessac-medium
popd

where ollama >nul 2>&1
if errorlevel 1 (
  echo.
  echo Ollama is not installed yet. Opening the official download page...
  start "" "https://ollama.com/download/windows"
  echo After installing Ollama, run this file again to download the local AI model.
) else (
  echo.
  echo Downloading the local qwen3:4b AI model. This can take a while...
  ollama pull qwen3:4b
)

echo.
echo Local components are ready.
echo Open JARVIS Settings, press Use Free Local AI, then Save Settings.
pause
exit /b 0

:fail
echo.
echo Local AI installation failed. Keep this window open and send a screenshot of the error.
pause
exit /b 1
