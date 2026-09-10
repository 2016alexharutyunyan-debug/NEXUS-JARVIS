@echo off
setlocal EnableExtensions
if not exist "%~dp0payload\run_1_2_8_tts_fix.bat" (
  echo ERROR: JARVIS payload is missing. Extract the complete ZIP first.
  if /I not "%~1"=="--check" pause
  exit /b 1
)
call "%~dp0payload\run_1_2_8_tts_fix.bat" %*
exit /b %ERRORLEVEL%
