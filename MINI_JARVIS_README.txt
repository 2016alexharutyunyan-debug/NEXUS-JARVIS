JARVIS 2.5.0 / FLOATING VOICE CONTROL

Extract the complete ZIP to a new folder. Run INSTALL_JARVIS.bat if needed,
configure your existing voice/API settings, then run START_JARVIS.bat.

Minimize JARVIS with the minus button in its main title bar. The small floating
JARVIS reactor appears. It does not open another microphone or voice session.
Existing voice commands continue while other applications are in front.
Click to restore; drag to move; right-click for pause/resume and Exit JARVIS.
The main app's previous normal/maximized state is restored. Restoring via the
taskbar hides the badge as well. X closes the app, rather than hiding it.

Try: open Chrome, open Notepad, volume up, open File Explorer, switch window,
scroll down, new tab, show Jarvis. App-specific keyboard commands affect the
foreground Windows application. This version supports the commands documented
in VOICE_COMMANDS.txt, not arbitrary unrestricted computer actions.

Privacy: the indicator is visible whenever the app is minimized. It displays
only the voice state, never your transcript. Pause stops the next recognition
cycle and ignores the recording in progress; current audio may finish.
The existing speech-recognition and TTS services/settings remain unchanged.
No new service, API key, startup registration or background installation is added.

Tests cover minimize/restore, maximized restoration, click/drag, non-activation
flags, status display, and ignoring paused recordings. Real microphone and
third-party application control depend on your Windows setup and were not
exercised by the automated tests.

Tests (inside payload):
py -m unittest test_mini_jarvis.py test_launcher.py test_location_map.py test_google_location.py
