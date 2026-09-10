JARVIS 2.6.0 / SCREEN-AWARE MINI VOICE

INSTALL
Extract the full ZIP to a new folder. Run INSTALL_JARVIS.bat for the new
PyAutoGUI dependency, then START_JARVIS.bat. Configure your Gemini key and an
image-capable Gemini model in the existing settings. No keys are bundled.
Voice recognition and TTS continue to use their existing configuration.

USE
Minimize JARVIS. The first time, allow or decline the screen-access prompt.
When allowed, capture starts while the mini icon is visible. The same session's
later minimizations reuse your decision. Right-click Screen access to stop or
request access again. Restoring the main window or pausing listening stops it.
Say "stop screen sharing" to disable access for the rest of the session.

Try: "What is on my screen?", "Click the search box", "Type hello".
Keep the target app in front. For a proposed input, a review window shows your
request, the exact action and screenshot (clicks are marked in red). Approve
Run this action or Cancel. Only one action runs; there is no autonomous loop.
Existing recognized Windows commands such as open Notepad or volume up still
execute normally without consulting screenshots.

WHAT IS SHARED
This is 1-frame-per-second local sampling, NOT continuous video streaming.
Only the latest frame is retained locally in memory. When a screen-aware or
unrecognized voice request is analyzed, a fresh screenshot of the foreground
app's monitor and the words you spoke go to Google Gemini. Other windows visible
on that monitor can be included. Hide private material before allowing access.
The AI reply may be spoken aloud. No screenshot/video files are written by this
feature. Gemini handles sent data under its own account/service policies.
An in-flight request may finish after you stop, but its proposed action is
invalidated. Exiting waits for active work to finish without executing it.

LIMITS AND SAFETY
- Current foreground monitor only; no secure desktop, UAC or lock-screen access.
- Supported proposals: click, double-click, small scroll, a limited key set,
  and short printable English text. No arbitrary shell or code-execution tool.
- Every model-proposed input requires confirmation, including Enter and typing.
- Large screen changes, moved windows, stale frames, failed focus or pause
  cancel execution. Visual comparison is conservative, not a semantic guarantee;
  always review the highlighted target and exact action before approval.
- This is not unrestricted full-PC autonomous control. Treat model suggestions
  as fallible. Do not approve unexpected sending, deletion, purchases or settings.
- PyAutoGUI's default failsafe is retained; moving the pointer to its supported
  screen corners aborts input. Short input operations may complete immediately.
- The app reports input sent, not that the requested task definitely succeeded.
- Screen analysis needs internet, an image-capable Gemini model and quota.
  Unsupported endpoints/models return an error rather than blind control.

VERIFICATION
Automated checks cover payloads, action validation, changed-screen rejection,
coordinate mapping, disabled capture, cancellation and existing app regressions.
No real desktop clicks, microphone session or live Gemini screenshot upload was
performed in these tests. Try a harmless action in Notepad first.
Inside payload:
py -m unittest test_screen_agent.py test_mini_jarvis.py test_launcher.py test_location_map.py test_google_location.py

Reference: https://ai.google.dev/gemini-api/docs/structured-output
