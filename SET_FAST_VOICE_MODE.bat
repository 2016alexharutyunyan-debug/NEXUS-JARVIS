@echo off
setlocal EnableExtensions
title JARVIS Fast Voice Mode

echo Setting JARVIS voice priority to FAST.
echo Fast mode uses Edge neural voice first, then Gemini, then Windows fallback.
echo This is the best mode for 3-5 second responses.
echo.

setx JARVIS_VOICE_PRIORITY fast
setx JARVIS_VOICE_RECORD_SECONDS 3.0
setx JARVIS_AI_TIMEOUT_SECONDS 12
setx JARVIS_AI_MAX_OUTPUT_TOKENS 140
setx JARVIS_GEMINI_TTS_TIMEOUT_SECONDS 5
setx JARVIS_EDGE_TTS_TIMEOUT_SECONDS 10

echo.
echo Done. Close and reopen JARVIS.
pause
