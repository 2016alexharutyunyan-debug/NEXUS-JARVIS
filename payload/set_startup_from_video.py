"""Create a private JARVIS startup sound from a user-owned video."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def extract_startup_audio(video: Path, output: Path, seconds: float = 7.0) -> Path:
    if not video.is_file():
        raise FileNotFoundError(f"Video not found: {video}")
    try:
        import imageio_ffmpeg
    except Exception as exc:
        raise RuntimeError("imageio-ffmpeg is not installed. Run INSTALL_JARVIS.bat first.") from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video),
        "-t",
        str(max(1.0, min(float(seconds), 7.5))),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "44100",
        "-ac",
        "2",
        str(output),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=90)
    if completed.returncode != 0 or not output.is_file() or output.stat().st_size < 1000:
        detail = (completed.stderr or completed.stdout or "Audio extraction failed.").strip()
        raise RuntimeError(detail[-600:])
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Use the first seconds of a video as JARVIS startup audio.")
    parser.add_argument("video", type=Path)
    parser.add_argument("--seconds", type=float, default=7.0)
    args = parser.parse_args()
    output = Path(__file__).resolve().parent / "assets" / "jarvis_startup.wav"
    extract_startup_audio(args.video.expanduser().resolve(), output, args.seconds)
    print(f"Startup sound ready: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
