# NEXUS JARVIS - AI Voice Assistant for Windows

NEXUS JARVIS is a free, experimental **AI voice assistant for Windows**. It combines English voice commands, Gemini AI chat, PC controls, a futuristic HoloDesk interface and a floating mini assistant in one Python desktop app.

Use it as a voice-controlled PC assistant to open apps, manage windows and volume, ask questions, search the web, create notes, build small projects, view your location and review screen-aware actions before they run.

**Version 3.3.1 - experimental personal desktop software.** Not affiliated with Marvel, Google, Microsoft, Binance or ElevenLabs.

[Download ZIP](https://github.com/2016alexharutyunyan-debug/NEXUS-JARVIS/archive/refs/heads/main.zip) | [Voice commands](VOICE_COMMANDS.txt) | [Screen control](SCREEN_CONTROL_README.txt)

## Why NEXUS JARVIS?

- **Jarvis-style Windows assistant:** a dark reactor dashboard, mini mode and wake phrase support.
- **Voice control for your PC:** open supported applications, control windows and change volume with English commands.
- **Faster local speech:** the default English male Windows voice speaks slightly faster while remaining clear.
- **Gemini AI desktop chat:** ask questions while keeping recent conversation context in the current session.
- **Fast Agent Mode:** common natural-language actions are planned locally; ambiguous requests use Gemini.
- **Persistent conversation memory:** optionally keep up to 20 recent exchanges across restarts and clear them at any time.
- **Remembered startup routines:** say `I work with crypto` once, and future launches open a Google market search plus a live BTC/ETH/SOL dashboard.
- **Free Local AI Mode:** optional Ollama chat, faster-whisper speech recognition and Piper speech with no paid API calls.
- **Natural text-to-speech:** optional ElevenLabs voice with provider fallback when unavailable.
- **Reviewed screen actions:** JARVIS can inspect a screenshot for a requested task, then shows the proposed action for approval.
- **Python source included:** inspect, test and customize the Windows assistant locally.

## Install on Windows

1. Install 64-bit Python 3.11 or 3.12 from https://www.python.org/downloads/windows/ and enable **Add Python to PATH**.
2. Download the ZIP above. Use **Extract All** and open the extracted folder. Do not run inside the ZIP.
3. Double-click `INSTALL_JARVIS.bat`. Internet access is needed to install dependencies into a local virtual environment.
4. For Gemini chat, run `SET_GEMINI_KEY.bat` with your own Gemini API key. In Settings, choose a model available to your account. Provider access, quotas and model availability vary.
5. For ElevenLabs speech, run `SET_ELEVENLABS_KEY.bat`, then `TEST_ELEVENLABS_VOICE.bat`. The key needs Text to Speech access. Voice services may incur charges.
6. Run `START_JARVIS.bat`. Allow microphone access in Windows when needed.

For clap startup, run `SET_CLAP_STARTUP_FROM_VIDEO.bat` and drag in a video you own or have permission to use. It privately saves the first seven seconds as the startup sound. Then keep `START_WAKE_LAUNCHER.bat` running or install the wake launcher at Windows startup. One sharp clap opens JARVIS maximized and plays the startup sequence. The selected audio is ignored by Git and is never included in the public package.

For an optional API-free setup, run `INSTALL_LOCAL_AI.bat` after the normal installer. Install Ollama from the official page if prompted, run the local installer again, then open Settings and press **Use Free Local AI**. See `LOCAL_AI_README.txt`. The first model downloads are large and local speed depends on CPU, GPU and memory.

Never share keys in screenshots or issues. The installer creates `VOICE_API_KEY.txt` from the example only when no local file exists; Git ignores the actual key file. Gemini and ElevenLabs keys are separate and are not interchangeable. No keys are included here.

## Included features

- Text and English voice commands for supported apps, windows, volume and other common desktop operations.
- Gemini conversation with up to 20 recent exchanges, optional memory across restarts, and a New Chat control.
- Safe Agent Mode for voice and typed requests: open supported apps and sites, search Google, create notes, and start reviewed project or screen tasks.
- Project generation and reviewed file changes with backups and ZIP packaging. Review generated code before running it.
- An optional wake launcher for "welcome" / "welcome Jarvis" or one sharp clap. A clap bypasses cloud speech recognition and opens JARVIS maximized. Run `START_WAKE_LAUNCHER.bat` separately. Startup installation is optional and has a matching uninstall script.
- A floating JARVIS badge when the main window is minimized. Click it to restore the main window; right-click to pause listening or exit.
- A dark location HUD using Windows position and OpenStreetMap, plus a separate embedded Google Maps view. Location accuracy depends on device permissions and available signals; IP estimates are explicitly labeled.
- Optional screen-aware voice commands with consent and one-action review, described below.
- Optional local Ollama reasoning, local Whisper recognition and Piper speech. If Ollama is unavailable, JARVIS silently uses configured cloud AI or its basic offline reply and waits five minutes before retrying.

## Easy voice examples

- `Google`, `open Google`, `in Google`, or `on Google`
- `Telegram`, `open Telegram`, `in Telegram`, or `on Telegram`
- `open YouTube in Google`
- `search weather on Google`
- `find football news`
- `I work with crypto`
- `stop showing crypto on startup`

Common pronunciations such as `gogle`, `gugle`, `tele gram`, and `my locesn` are accepted. Unknown website names used with `in Google` or `on Google` are searched safely instead of being executed as programs.

The crypto startup routine is saved locally after the first matching voice or chat message. On later launches it opens Google and shows public Binance 24-hour market data inside JARVIS. Disable it with the stop command above or the checkbox in Settings. Prices can be delayed or unavailable and are informational only, not financial advice.

## Agent Mode examples

- `Create a note called Shopping with milk and bread`
- `Search Google for affordable laptops and open YouTube`
- `Build a small focus timer app`
- `Edit my last project and add a dark mode button`
- `Read the screen and click the Settings button`

Agent Mode turns a natural English request into at most five supported actions. Common commands are planned locally for a near-instant start; ambiguous requests use Gemini. Follow-ups such as `then open YouTube` are understood. Broad ambitions such as `change the world` stay in conversation mode instead of generating a random app. It does not run arbitrary shell commands, delete files, make purchases, send messages, change accounts, handle credentials or disable security. Project files and screen input are still shown for review and require confirmation before they are applied.

## Screen access and privacy

Screen mode asks for consent when first enabled in a session. It captures the foreground monitor locally at roughly one frame per second, not a continuous video stream. A fresh screenshot and your request are sent to Gemini when a screen-aware request is submitted. Frames stay in memory locally; this does not control the provider's retention policy.

Each model-proposed click, key, scroll or typing action requires a separate preview and approval. Known explicit desktop commands use the existing command handler. This is **not unrestricted autonomous control** and does not bypass Windows security prompts. Screen matching checks reduce mistakes but cannot guarantee every target is correct.

Restore the main window, pause listening, use **Screen access off**, or say **stop screen sharing** to stop capture. Keep private messages, passwords and confidential documents off the captured monitor. Turning screen mode off does not retract data already sent.

Speech recognition may send audio to Google's recognition service; cloud voices send reply text to their providers. This is not an offline-only assistant. Local settings and optional conversation memory are stored under `%APPDATA%\HoloDeskAI` and are not encrypted. Lines that look like passwords or API keys are excluded from saved conversation memory, but you should still avoid speaking or typing secrets into chat. Keep your Windows account secure.

## Troubleshooting

- **HTTP 401 / invalid key:** check the provider, the full key, its permissions and expiry. Do not post the key.
- **HTTP 404 / model unavailable:** choose an API model your account can access in Settings.
- **No voice or a different voice:** run the relevant voice test. Some configurations fall back to another speech provider or Windows speech when the preferred provider fails.
- **Wake phrase heard but no launch:** extract the whole folder and keep the launcher beside `payload`. Try `START_JARVIS.bat` directly first.
- **Microphone not available:** close other capture apps and check Windows microphone permissions. Use `TEST_MICROPHONE.bat`.
- **No precise position:** enable Windows Location; a desktop PC may not provide GPS-level accuracy.

## Frequently asked questions

### How do I install a Jarvis AI assistant on Windows?

Download the repository ZIP, extract it, run `INSTALL_JARVIS.bat`, add your own optional API keys and start it with `START_JARVIS.bat`. Python 3.11 or 3.12 is required.

### Can JARVIS control my Windows PC by voice?

It supports direct English voice commands plus safe natural-language Agent Mode for applications, websites, Google search, notes, projects and reviewed screen actions. Screen-aware model actions always require a separate preview and approval.

### Does this Windows AI assistant require an API key?

Basic local commands work without API keys. The optional Ollama, Whisper and Piper setup can also run without paid API calls after its models are downloaded. Gemini chat and ElevenLabs voice require your own provider keys, which remain outside the public Git repository.

## Development and verification

Application source and tests are in `payload/`. From that directory, after installing dependencies:

```powershell
.\.venv\Scripts\python.exe -m unittest test_startup_routines.py test_local_ai.py test_local_voice.py test_wake_clap.py test_conversation_memory.py test_agent_mode.py test_zip_builder.py test_screen_agent.py test_mini_jarvis.py test_launcher.py test_location_map.py test_google_location.py test_windows_voice.py test_voice_stream.py
```

The 86 focused tests cover startup routine persistence, crypto data parsing, instant clap wake handling, local AI configuration and fallback, local voice adapters, persistent memory, secret redaction, fast local Agent Mode planning, validation, mocked screen interactions, command helpers, launcher paths and UI state. They do not prove every microphone, external market service, downloaded Ollama/Whisper/Piper model, Gemini, cloud speech or end-to-end real desktop behavior. Service integration and performance depend on network, account access and hardware; a fixed 3-5 second response time is not guaranteed.

## Distribution and assets

The public package does not include the earlier video-derived startup recording. The spoken greeting still works. You may add your own permitted `payload/assets/jarvis_startup.wav` locally; it is ignored by Git.

Leaflet is bundled with its license at `payload/assets/location/LEAFLET-LICENSE.txt`. Other dependencies retain their own licenses. Map attribution must remain visible. No blanket open-source license has been selected for the project's own code; public visibility alone is not a license grant.

See [SECURITY.md](SECURITY.md) before reporting a security problem.
