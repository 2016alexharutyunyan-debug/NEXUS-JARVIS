JARVIS HoloDesk 2.6.0 - Screen-Aware Voice Control
See README.md for the public package setup, privacy notes and limitations.

New Chat is available at the top of AI Assistant.
See VOICE_COMMANDS.txt for the new Windows voice commands.

WHAT JARVIS DOES
- Runs as an English-only Windows desktop assistant.
- Opens from the background when you say "welcome" or "welcome Jarvis".
- A sharp hand clap can also open JARVIS.
- Opens Chrome, Notepad, Calculator and the Windows default browser.
- Answers through Gemini when GEMINI_API_KEY is configured.
- Speaks with ElevenLabs when an ElevenLabs API key is written in VOICE_API_KEY.txt.
- Says "Welcome home, sir. JARVIS is online." on launch. The public package omits the video-derived sound clip.
- Starts microphone listening only after the startup greeting finishes.
- Remembers the recent conversation during the current session.
- Creates complete local apps and file packages with source code, README and ZIP.
- Opens the last generated project in Agent Workspace.
- Reads that project's source files and prepares exact code changes from your instruction.
- Shows a file diff before changing anything.
- Applies changes only after your approval.
- Creates a timestamped backup and a new updated ZIP after every approved edit.
- Checks generated Python files for syntax errors before enabling approval.
- Keeps the original HoloDesk futuristic interface.

FIRST INSTALL
1. Extract the complete ZIP to a normal folder.
2. Double-click INSTALL_JARVIS.bat.
3. Run SET_ELEVENLABS_KEY.bat and paste the complete newly created ElevenLabs key.
4. You can also paste it after ELEVENLABS_API_KEY= inside VOICE_API_KEY.txt.
5. Run TEST_ELEVENLABS_VOICE.bat to hear a short test.
6. For Gemini AI answers, run SET_GEMINI_KEY.bat separately with a Gemini key.
7. Close old JARVIS windows and run START_WAKE_LAUNCHER.bat.
8. Say "welcome Jarvis" or make one sharp clap.

CREATE AN APP
Say or type one of these:
- generate a random app
- build a project
- create an expense tracker with a local database
- build a study timer with a simple interface

JARVIS opens Mission Builder and prepares the project. Review the file plan, then approve
the build. New projects are saved under Documents\JARVIS Projects by default.

CHANGE THE APP LATER
After JARVIS creates an app, say or type instructions such as:
- make it blue
- add a reset button
- fix the timer
- change the title to Focus Flow
- edit the last app

JARVIS opens Agent Workspace with the last project selected. Press Plan Changes, review
the diff, then press Approve and Apply. The original files are backed up before writing.
JARVIS never applies or runs generated code without a separate confirmation.

WAKE LAUNCHER
- START_WAKE_LAUNCHER.bat: listen now for "welcome Jarvis" or a clap.
- INSTALL_WAKE_LAUNCHER_STARTUP.bat: start listening automatically with Windows.
- UNINSTALL_WAKE_LAUNCHER_STARTUP.bat: remove automatic startup.

VOICE
- ElevenLabs key: VOICE_API_KEY.txt
- Easy ElevenLabs setup: SET_ELEVENLABS_KEY.bat
- ElevenLabs voice test: TEST_ELEVENLABS_VOICE.bat
- Default voice: George (voice ID JBFqnCBsd6RMkjVDRZzb)
- Fast voice model: eleven_flash_v2_5
- Fast mode: SET_FAST_VOICE_MODE.bat
- Gemini quality voice: SET_GEMINI_QUALITY_VOICE_MODE.bat
- Voice test: TEST_GEMINI_VOICE.bat or TEST_EDGE_VOICE.bat
- Microphone test: TEST_MICROPHONE.bat

SECURITY
- The Gemini key can stay in the Windows user environment.
- VOICE_API_KEY.example.txt contains only placeholders. The installer creates a local VOICE_API_KEY.txt.
- Agent Workspace never reads .env, credential, secret, virtual-environment or Git files.
- Absolute paths, parent-folder paths, file deletion and oversized changes are rejected.
- Backups are stored under AppData\Roaming\HoloDeskAI\agent_backups.
