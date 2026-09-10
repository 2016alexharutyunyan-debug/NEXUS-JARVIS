@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title JARVIS Edge Neural Voice Test

if exist "payload\.venv\Scripts\python.exe" (
  set "PY=payload\.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

"%PY%" payload\test_edge_voice.py
pause
