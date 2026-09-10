@echo off
setlocal EnableExtensions
title JARVIS Speaker Test
echo Testing Windows SAPI voice...
echo.
powershell.exe -NoLogo -NoProfile -STA -ExecutionPolicy Bypass -Command "$v=New-Object -ComObject SAPI.SpVoice; $v.Volume=100; $v.Rate=0; [void]$v.Speak('Hello Alex. JARVIS voice test is working.')"
if errorlevel 1 (
  echo.
  echo SAPI test failed.
  echo Send me a screenshot of this window.
  pause
  exit /b 1
)
echo.
echo If you heard the sentence, Windows speaker output works.
pause
