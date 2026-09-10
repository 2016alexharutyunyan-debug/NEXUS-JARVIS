@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Set ElevenLabs Voice Key for JARVIS

echo ==========================================
echo Set ElevenLabs Voice Key for JARVIS
echo ==========================================
echo.
echo Create a new key on ElevenLabs, copy the complete key, then paste it below.
echo The key stays in this JARVIS folder and is never printed after saving.
echo.

set /p "ELEVEN_KEY=ElevenLabs API key: "
if not defined ELEVEN_KEY (
  echo.
  echo ERROR: No key was entered.
  pause
  exit /b 1
)

>"VOICE_API_KEY.txt" echo # JARVIS ElevenLabs voice settings
>>"VOICE_API_KEY.txt" echo VOICE_PROVIDER=elevenlabs
>>"VOICE_API_KEY.txt" echo ELEVENLABS_API_KEY=%ELEVEN_KEY%
>>"VOICE_API_KEY.txt" echo ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
>>"VOICE_API_KEY.txt" echo ELEVENLABS_MODEL_ID=eleven_flash_v2_5

set "ELEVEN_KEY="
echo.
echo Saved. Now run TEST_ELEVENLABS_VOICE.bat.
pause
