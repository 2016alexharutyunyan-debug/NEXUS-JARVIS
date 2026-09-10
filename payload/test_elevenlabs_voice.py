from __future__ import annotations

from main import SpeechWorker, elevenlabs_api_key, elevenlabs_voice_id


def main() -> int:
    if not elevenlabs_api_key():
        print("ElevenLabs API key is not set.")
        print("Open VOICE_API_KEY.txt and paste the key after ELEVENLABS_API_KEY=.")
        return 1

    print(f"Testing ElevenLabs voice ID: {elevenlabs_voice_id()}")
    worker = SpeechWorker("Hello. JARVIS ElevenLabs voice is online.")
    ok, error = worker._run_elevenlabs_tts()
    if ok:
        print("ElevenLabs voice test OK.")
        return 0
    print(f"ElevenLabs voice test failed: {error}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
