@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title JARVIS ElevenLabs Voice Test

if exist "payload\.venv\Scripts\python.exe" (
  set "PY=payload\.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

"%PY%" "payload\test_elevenlabs_voice.py"
echo.
pause
