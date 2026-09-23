JARVIS FREE LOCAL AI
====================

1. Run INSTALL_JARVIS.bat first.
2. Run INSTALL_LOCAL_AI.bat.
3. If the Ollama page opens, install Ollama and run INSTALL_LOCAL_AI.bat again.
4. Open JARVIS, open Settings, press Use Free Local AI, then Save Settings.

Local components
----------------
- Ollama + qwen3:4b: local chat and Agent planning.
- faster-whisper base.en: local English speech recognition.
- Piper en_US-lessac-medium: optional local English voice.

The first model downloads are large and need internet access. After the models
are installed, local AI and voice processing do not require paid API calls.
Performance depends on the computer. A small local model will not match the
knowledge and reasoning of the largest cloud models.

Piper is optional. If it is disabled or fails, JARVIS uses the existing Windows
male voice. If local Whisper fails, JARVIS falls back to the existing recognizer.
