# NEXUS-JARVIS

A Windows desktop assistant with an English voice interface, a dark HoloDesk reactor UI, Gemini chat and a floating mini assistant.

**Version 2.6.0 - experimental personal desktop software.** Not affiliated with Marvel, Google, Microsoft or ElevenLabs.

[Download ZIP](https://github.com/2016alexharutyunyan-debug/NEXUS-JARVIS/archive/refs/heads/main.zip) | [Voice commands](VOICE_COMMANDS.txt) | [Screen control](SCREEN_CONTROL_README.txt)

## Install on Windows

1. Install 64-bit Python 3.11 or 3.12 from https://www.python.org/downloads/windows/ and enable **Add Python to PATH**.
2. Download the ZIP above. Use **Extract All** and open the extracted folder. Do not run inside the ZIP.
3. Double-click `INSTALL_JARVIS.bat`. Internet access is needed to install dependencies into a local virtual environment.
4. For Gemini chat, run `SET_GEMINI_KEY.bat` with your own Gemini API key. In Settings, choose a model available to your account. Provider access, quotas and model availability vary.
5. For ElevenLabs speech, run `SET_ELEVENLABS_KEY.bat`, then `TEST_ELEVENLABS_VOICE.bat`. The key needs Text to Speech access. Voice services may incur charges.
6. Run `START_JARVIS.bat`. Allow microphone access in Windows when needed.

Never share keys in screenshots or issues. The installer creates `VOICE_API_KEY.txt` from the example only when no local file exists; Git ignores the actual key file. Gemini and ElevenLabs keys are separate and are not interchangeable. No keys are included here.

## Included features

- Text and English voice commands for supported apps, windows, volume and other common desktop operations.
- Gemini conversation with recent-session memory and a New Chat control.
- Project generation and reviewed file changes with backups and ZIP packaging. Review generated code before running it.
- An optional wake launcher for "welcome" / "welcome Jarvis". Run `START_WAKE_LAUNCHER.bat` separately. Startup installation is optional and has a matching uninstall script.
- A floating JARVIS badge when the main window is minimized. Click it to restore the main window; right-click to pause listening or exit.
- A dark location HUD using Windows position and OpenStreetMap, plus a separate embedded Google Maps view. Location accuracy depends on device permissions and available signals; IP estimates are explicitly labeled.
- Optional screen-aware voice commands with consent and one-action review, described below.

## Screen access and privacy

Screen mode asks for consent when first enabled in a session. It captures the foreground monitor locally at roughly one frame per second, not a continuous video stream. A fresh screenshot and your request are sent to Gemini when a screen-aware request is submitted. Frames stay in memory locally; this does not control the provider's retention policy.

Each model-proposed click, key, scroll or typing action requires a separate preview and approval. Known explicit desktop commands use the existing command handler. This is **not unrestricted autonomous control** and does not bypass Windows security prompts. Screen matching checks reduce mistakes but cannot guarantee every target is correct.

Restore the main window, pause listening, use **Screen access off**, or say **stop screen sharing** to stop capture. Keep private messages, passwords and confidential documents off the captured monitor. Turning screen mode off does not retract data already sent.

Speech recognition may send audio to Google's recognition service; cloud voices send reply text to their providers. This is not an offline-only assistant. Local settings are stored under `%APPDATA%\HoloDeskAI`. Cloud API keys and local settings are not encrypted by this application. Keep your Windows account secure.

## Troubleshooting

- **HTTP 401 / invalid key:** check the provider, the full key, its permissions and expiry. Do not post the key.
- **HTTP 404 / model unavailable:** choose an API model your account can access in Settings.
- **No voice or a different voice:** run the relevant voice test. Some configurations fall back to another speech provider or Windows speech when the preferred provider fails.
- **Wake phrase heard but no launch:** extract the whole folder and keep the launcher beside `payload`. Try `START_JARVIS.bat` directly first.
- **Microphone not available:** close other capture apps and check Windows microphone permissions. Use `TEST_MICROPHONE.bat`.
- **No precise position:** enable Windows Location; a desktop PC may not provide GPS-level accuracy.

## Development and verification

Application source and tests are in `payload/`. From that directory, after installing dependencies:

```powershell
.\.venv\Scripts\python.exe -m unittest test_screen_agent.py test_mini_jarvis.py test_launcher.py test_location_map.py test_google_location.py
```

The 44 focused tests cover mocked screen interactions, command helpers, launcher paths and UI state. They do not prove live microphone, Gemini, ElevenLabs or end-to-end real desktop behavior. Service integration and performance depend on network, account access and hardware; a fixed 3-5 second response time is not guaranteed.

## Distribution and assets

The public package does not include the earlier video-derived startup recording. The spoken greeting still works. You may add your own permitted `payload/assets/jarvis_startup.wav` locally; it is ignored by Git.

Leaflet is bundled with its license at `payload/assets/location/LEAFLET-LICENSE.txt`. Other dependencies retain their own licenses. Map attribution must remain visible. No blanket open-source license has been selected for the project's own code; public visibility alone is not a license grant.

See [SECURITY.md](SECURITY.md) before reporting a security problem.
