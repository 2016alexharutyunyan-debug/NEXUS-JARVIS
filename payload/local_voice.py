"""Optional offline speech recognition and speech synthesis adapters."""
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import wave
from pathlib import Path


_WHISPER_MODELS = {}
_WHISPER_LOCK = threading.Lock()


def _whisper_model(name):
    model_name = (name or "base.en").strip() or "base.en"
    with _WHISPER_LOCK:
        model = _WHISPER_MODELS.get(model_name)
        if model is None:
            try:
                from faster_whisper import WhisperModel
            except Exception as exc:
                raise RuntimeError("faster-whisper is not installed") from exc
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            _WHISPER_MODELS.clear()
            _WHISPER_MODELS[model_name] = model
        return model


def transcribe_pcm(pcm16, sample_rate, model_name="base.en"):
    if not pcm16:
        raise RuntimeError("No microphone audio was recorded.")
    descriptor, filename = tempfile.mkstemp(prefix="jarvis_whisper_", suffix=".wav")
    os.close(descriptor)
    path = Path(filename)
    try:
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(int(sample_rate))
            output.writeframes(pcm16)
        model = _whisper_model(model_name)
        segments, _ = model.transcribe(
            str(path),
            language="en",
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        if not text:
            raise RuntimeError("No speech recognized by local Whisper.")
        return text
    finally:
        path.unlink(missing_ok=True)


def resolve_piper_executable(configured=""):
    value = (configured or "").strip()
    if value and Path(value).is_file():
        return str(Path(value))
    discovered = shutil.which(value or "piper")
    if discovered:
        return discovered
    venv_candidate = Path(sys.executable).with_name("piper.exe")
    return str(venv_candidate) if venv_candidate.is_file() else ""


def synthesize_piper(text, model_path, output_path, executable=""):
    piper = resolve_piper_executable(executable)
    model = Path(model_path or "").expanduser()
    if not piper:
        raise RuntimeError("Piper is not installed or was not found.")
    if not model.is_file() or model.suffix.lower() != ".onnx":
        raise RuntimeError("Choose a valid Piper .onnx voice model in Settings.")
    completed = subprocess.run(
        [piper, "--model", str(model), "--output_file", str(output_path)],
        input=str(text or ""),
        capture_output=True,
        text=True,
        timeout=45,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0 or not Path(output_path).is_file() or Path(output_path).stat().st_size < 44:
        detail = (completed.stderr or completed.stdout or "Piper failed.").strip()[-500:]
        raise RuntimeError(detail)
    return Path(output_path)
