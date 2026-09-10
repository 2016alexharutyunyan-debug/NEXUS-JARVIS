from __future__ import annotations

import ast
import base64
import concurrent.futures
import ctypes
import difflib
import html
import json
import math
import os
import queue
import random
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
import zipfile
from pc_voice import parse_pc_command
from location_map import LocationMapWidget, location_intent, google_maps_intent
from google_location import GoogleLocationWidget
from mini_jarvis import MiniJarvis
from screen_agent import ScreenAgent
from dataclasses import dataclass, asdict
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional

import cv2
import mediapipe as mp
import numpy as np
from PySide6.QtCore import (
    Qt, QTimer, QPoint, QRect, QSize, QThread, Signal, QUrl, QObject,
    QEasingCurve, QPropertyAnimation, QEvent
)
from PySide6.QtGui import (
    QAction, QColor, QImage, QPainter, QPen, QBrush, QPixmap,
    QTransform, QDesktopServices, QGuiApplication, QFont
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QTextEdit, QLineEdit,
    QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QCalendarWidget, QLCDNumber, QSlider,
    QCheckBox, QSpinBox, QTabWidget, QProgressBar, QGraphicsDropShadowEffect,
    QMenu, QInputDialog, QAbstractItemView, QStackedWidget
)

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except Exception:
    QWebEngineView = None
    WEBENGINE_AVAILABLE = False

try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_AVAILABLE = True
except Exception:
    QMediaPlayer = None
    QAudioOutput = None
    QVideoWidget = None
    MULTIMEDIA_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except Exception:
    psutil = None
    PSUTIL_AVAILABLE = False

IS_WINDOWS = sys.platform.startswith("win")
if IS_WINDOWS:
    try:
        import win32api
        import win32con
        import win32gui
        import win32process
        WIN32_AVAILABLE = True
    except Exception:
        win32api = win32con = win32gui = win32process = None
        WIN32_AVAILABLE = False
else:
    win32api = win32con = win32gui = win32process = None
    WIN32_AVAILABLE = False


APP_NAME = "JARVIS HoloDesk"
APP_VERSION = "2.6.0-screen-voice"
DEFAULT_AI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_AI_MODEL = "gemini-3.5-flash-lite"
AI_TIMEOUT_SECONDS = int(os.environ.get("JARVIS_AI_TIMEOUT_SECONDS", "12"))
AI_MAX_OUTPUT_TOKENS = int(os.environ.get("JARVIS_AI_MAX_OUTPUT_TOKENS", "140"))
VOICE_RECORD_SECONDS = float(os.environ.get("JARVIS_VOICE_RECORD_SECONDS", "3.0"))
GEMINI_TTS_TIMEOUT_SECONDS = int(os.environ.get("JARVIS_GEMINI_TTS_TIMEOUT_SECONDS", "5"))
EDGE_TTS_TIMEOUT_SECONDS = int(os.environ.get("JARVIS_EDGE_TTS_TIMEOUT_SECONDS", "10"))
ELEVENLABS_TTS_TIMEOUT_SECONDS = int(os.environ.get("JARVIS_ELEVENLABS_TTS_TIMEOUT_SECONDS", "12"))
VOICE_PRIORITY = os.environ.get("JARVIS_VOICE_PRIORITY", "fast").strip().lower()
DEFAULT_JARVIS_PROMPT = (
    "You are JARVIS, a friendly and clear voice assistant. "
    "Speak like Gemini: simple, natural, calm, and easy to understand. "
    "Reply only in English, even if the user uses another language. "
    "Keep answers short unless the user asks for detail. Usually use 1 short sentence, maximum 2. "
    "Do not use markdown, bullet points, code blocks, emojis, or technical formatting. "
    "For desktop commands, confirm briefly and naturally."
)


def resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def voice_config_from_file() -> dict[str, str]:
    """Read local voice configuration without logging or exposing secret values."""
    payload_dir = Path(__file__).resolve().parent
    candidates = (
        payload_dir.parent / "VOICE_API_KEY.txt",
        payload_dir / "VOICE_API_KEY.txt",
    )
    config: dict[str, str] = {}
    for path in candidates:
        try:
            for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    name, value = line.split("=", 1)
                    name = name.strip().upper()
                    value = value.strip().strip('"').strip("'")
                else:
                    name, value = "API_KEY", line
                upper = value.upper()
                if value and "PASTE" not in upper and "YOUR_API_KEY" not in upper:
                    config.setdefault(name, value)
        except OSError:
            continue
    return config


def api_key_from_file() -> str:
    """Read only a Gemini key; never send an ElevenLabs key to Gemini."""
    config = voice_config_from_file()
    explicit = config.get("GEMINI_API_KEY", "")
    generic = config.get("VOICE_API_KEY", "") or config.get("API_KEY", "")
    provider = config.get("VOICE_PROVIDER", "").lower()
    if explicit:
        return explicit
    if provider == "gemini" or (generic and not generic.lower().startswith(("sk_", "sk-"))):
        return generic
    return ""


def elevenlabs_api_key() -> str:
    config = voice_config_from_file()
    explicit = (
        os.environ.get("ELEVENLABS_API_KEY", "").strip()
        or config.get("ELEVENLABS_API_KEY", "")
    )
    if explicit:
        return explicit
    generic = config.get("VOICE_API_KEY", "") or config.get("API_KEY", "")
    provider = config.get("VOICE_PROVIDER", "").lower()
    if provider == "elevenlabs" or generic.lower().startswith(("sk_", "sk-")):
        return generic
    return ""


def elevenlabs_voice_id() -> str:
    config = voice_config_from_file()
    return (
        os.environ.get("JARVIS_ELEVENLABS_VOICE_ID", "").strip()
        or config.get("ELEVENLABS_VOICE_ID", "")
        or "JBFqnCBsd6RMkjVDRZzb"
    )


def app_data_dir() -> Path:
    if IS_WINDOWS:
        root = Path(os.getenv("APPDATA", Path.home()))
    else:
        root = Path.home() / ".config"
    path = root / "HoloDeskAI"
    path.mkdir(parents=True, exist_ok=True)
    return path


HAND_MODEL_PATH = resource_path("models", "hand_landmarker.task")
FACE_MODEL_PATH = resource_path("models", "face_landmarker.task")
SETTINGS_PATH = app_data_dir() / "settings.json"
WORKSPACE_PATH = app_data_dir() / "workspace.json"
WORLD_MAP_PATH = app_data_dir() / "world_map.json"
SELF_EDIT_PATH = app_data_dir() / "self_edit.json"
AGENT_STATE_PATH = app_data_dir() / "agent_state.json"
AGENT_BACKUP_PATH = app_data_dir() / "agent_backups"
PROJECTS_PATH = Path.home() / "Documents" / "JARVIS Projects"


def load_agent_state() -> dict[str, str]:
    try:
        data = json.loads(AGENT_STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {"last_project": str(data.get("last_project", ""))}
    except Exception:
        pass
    return {"last_project": ""}


def save_last_project(path: Path) -> None:
    AGENT_STATE_PATH.write_text(
        json.dumps({"last_project": str(path.resolve())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def last_project_path() -> Optional[Path]:
    raw = load_agent_state().get("last_project", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.exists() and path.is_dir() else None


def project_edit_intent(text: str) -> bool:
    normalized = "".join(char if char.isalnum() else " " for char in text.lower())
    words = set(normalized.split())
    action = bool(words & {"add", "change", "update", "edit", "fix", "improve", "remove", "redesign", "modify"})
    target = bool(words & {"app", "application", "program", "project", "code", "it"})
    make_it = "make" in words and "it" in words
    return (action and target) or make_it


def project_followup_intent(text: str) -> bool:
    if last_project_path() is None:
        return False
    normalized = "".join(char if char.isalnum() else " " for char in text.lower())
    words = set(normalized.split())
    action = bool(words & {"add", "change", "update", "edit", "fix", "improve", "remove", "redesign", "modify", "make"})
    system_target = bool(words & {"voice", "memory", "window", "browser", "settings", "volume"})
    return action and not system_target


def safe_project_name(value: str, default: str = "jarvis_project") -> str:
    cleaned = "".join(char if char.isalnum() or char in "-_ " else " " for char in value)
    cleaned = "_".join(cleaned.split()).strip("._-")
    return (cleaned or default)[:64]


def safe_relative_path(value: str) -> Path:
    raw = value.strip().replace("\\", "/")
    if not raw or "\x00" in raw or ":" in raw:
        raise ValueError("Invalid file path in the generated plan.")
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe file path rejected: {value}")
    parts = [part for part in path.parts if part not in {"", "."}]
    if not parts:
        raise ValueError("The generated plan contains an empty file path.")
    return Path(*parts)


def json_object_from_text(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Gemini did not return a project plan.")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("The project plan is not a JSON object.")
    return data


def normalize_project_plan(data: dict[str, Any], request: str) -> dict[str, Any]:
    project_name = safe_project_name(str(data.get("project_name", "jarvis_project")))
    summary = str(data.get("summary", request)).strip()[:1000]
    raw_files = data.get("files", [])
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("The project plan does not contain files.")
    if len(raw_files) > 18:
        raise ValueError("The project plan contains too many files. Maximum: 18.")

    files: list[dict[str, str]] = []
    total_size = 0
    seen: set[str] = set()
    for item in raw_files:
        if not isinstance(item, dict):
            raise ValueError("A project file entry is invalid.")
        relative = safe_relative_path(str(item.get("path", "")))
        key = relative.as_posix().lower()
        if key in seen:
            raise ValueError(f"Duplicate file path: {relative.as_posix()}")
        seen.add(key)
        content = str(item.get("content", ""))
        total_size += len(content.encode("utf-8"))
        if total_size > 700_000:
            raise ValueError("The generated project is too large. Maximum: 700 KB.")
        files.append({"path": relative.as_posix(), "content": content})

    run_file = str(data.get("run_file", "")).strip()
    if run_file:
        run_file = safe_relative_path(run_file).as_posix()
    return {
        "project_name": project_name,
        "summary": summary,
        "files": files,
        "run_file": run_file,
        "request": request.strip(),
    }


def local_starter_plan(request: str) -> dict[str, Any]:
    low = request.lower()
    name_words = [word for word in request.split() if word.isalnum()][:5]
    name = safe_project_name(" ".join(name_words), "jarvis_project")
    if any(word in low for word in ("website", "web site", "html", "landing page")):
        data = {
            "project_name": name,
            "summary": "A local starter website generated by JARVIS.",
            "run_file": "index.html",
            "files": [
                {"path": "index.html", "content": "<!doctype html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"utf-8\">\n  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n  <title>JARVIS Project</title>\n  <link rel=\"stylesheet\" href=\"styles.css\">\n</head>\n<body>\n  <main>\n    <h1>JARVIS Project</h1>\n    <p id=\"brief\"></p>\n    <button id=\"action\">Activate</button>\n  </main>\n  <script src=\"app.js\"></script>\n</body>\n</html>\n"},
                {"path": "styles.css", "content": "body{margin:0;min-height:100vh;display:grid;place-items:center;background:#071018;color:#dffaff;font-family:Segoe UI,sans-serif}main{width:min(680px,calc(100% - 40px));border:1px solid #36b9db;padding:32px}button{padding:10px 18px;background:#123e52;color:#eaffff;border:1px solid #58cdea}h1{letter-spacing:0}\n"},
                {"path": "app.js", "content": f"document.querySelector('#brief').textContent = {json.dumps(request)};\ndocument.querySelector('#action').addEventListener('click',()=>alert('Project activated.'));\n"},
                {"path": "README.md", "content": f"# {name}\n\nGenerated by JARVIS Mission Builder.\n\n## Request\n\n{request}\n\nOpen `index.html` to run it.\n"},
            ],
        }
    else:
        data = {
            "project_name": name,
            "summary": "A local Python starter generated by JARVIS.",
            "run_file": "run.bat",
            "files": [
                {"path": "main.py", "content": f"from __future__ import annotations\n\nPROJECT_BRIEF = {request!r}\n\n\ndef main() -> None:\n    print('JARVIS project ready.')\n    print(PROJECT_BRIEF)\n\n\nif __name__ == '__main__':\n    main()\n"},
                {"path": "run.bat", "content": "@echo off\ncd /d \"%~dp0\"\npython main.py\npause\n"},
                {"path": "README.md", "content": f"# {name}\n\nGenerated by JARVIS Mission Builder.\n\n## Request\n\n{request}\n\nRun `run.bat`.\n"},
            ],
        }
    return normalize_project_plan(data, request)


def project_text_snapshot(root: Path) -> list[dict[str, str]]:
    allowed_suffixes = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json",
        ".md", ".txt", ".toml", ".yaml", ".yml", ".bat", ".cmd",
    }
    blocked_parts = {
        ".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build",
        ".next", ".pytest_cache", "agent_backups",
    }
    blocked_names = {".env", ".env.local", "credentials.json", "secrets.json"}
    candidates = [
        path for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in allowed_suffixes
        and path.name.lower() not in blocked_names
        and not any(part.lower() in blocked_parts for part in path.parts)
    ]
    priority = {"main.py": 0, "app.py": 1, "index.html": 2, "package.json": 3, "readme.md": 4}
    candidates.sort(key=lambda path: (priority.get(path.name.lower(), 10), path.as_posix().lower()))
    snapshot: list[dict[str, str]] = []
    total = 0
    for path in candidates:
        if len(snapshot) >= 16:
            break
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        encoded_size = len(content.encode("utf-8"))
        if encoded_size > 80_000 or total + encoded_size > 240_000:
            continue
        snapshot.append({"path": path.relative_to(root).as_posix(), "content": content})
        total += encoded_size
    return snapshot


def normalize_agent_patch(data: dict[str, Any], request: str) -> dict[str, Any]:
    summary = str(data.get("summary", request)).strip()[:1000]
    raw_files = data.get("files", [])
    if not isinstance(raw_files, list) or not raw_files:
        raise ValueError("The agent did not return any file changes.")
    if len(raw_files) > 16:
        raise ValueError("The agent returned too many changed files. Maximum: 16.")
    files: list[dict[str, str]] = []
    total = 0
    seen: set[str] = set()
    for item in raw_files:
        if not isinstance(item, dict):
            raise ValueError("The agent returned an invalid file entry.")
        relative = safe_relative_path(str(item.get("path", "")))
        key = relative.as_posix().lower()
        if key in seen:
            raise ValueError(f"Duplicate changed file: {relative.as_posix()}")
        seen.add(key)
        content = str(item.get("content", ""))
        total += len(content.encode("utf-8"))
        if total > 900_000:
            raise ValueError("The proposed update is too large. Maximum: 900 KB.")
        files.append({"path": relative.as_posix(), "content": content})
    return {"summary": summary, "files": files, "request": request.strip()}


def ensure_project_launcher(target: Path, requested: str = "") -> str:
    run_path: Optional[Path] = None
    if requested.strip():
        candidate = target / safe_relative_path(requested)
        if candidate.exists() and candidate.suffix.lower() not in {".md", ".txt"}:
            run_path = candidate
    if run_path is None:
        for name in ("main.py", "app.py", "index.html", "run.bat", "start.bat"):
            candidate = target / name
            if candidate.exists():
                run_path = candidate
                break
    if run_path is None:
        return ""

    relative = run_path.relative_to(target).as_posix()
    if run_path.name.lower() == "run_app.bat":
        return relative
    suffix = run_path.suffix.lower()
    windows_relative = relative.replace("/", "\\")
    if suffix == ".py":
        command = f'python "{windows_relative}"'
    elif suffix in {".html", ".htm", ".exe"}:
        command = f'start "" "{windows_relative}"'
    elif suffix in {".bat", ".cmd"}:
        command = f'call "{windows_relative}"'
    else:
        return relative
    (target / "RUN_APP.bat").write_text(
        "@echo off\n"
        "setlocal EnableExtensions\n"
        "cd /d \"%~dp0\"\n"
        f"{command}\n"
        "if errorlevel 1 (\n"
        "  echo.\n"
        "  echo The generated app stopped with an error.\n"
        "  pause\n"
        ")\n",
        encoding="utf-8",
    )
    return "RUN_APP.bat"


def load_self_edit_config() -> dict[str, Any]:
    defaults = {
        "center_text": "JARVIS",
        "voice_style": "simple",
        "custom_prompt": "",
        "aliases": "mission => future self\npackage project => zip builder\nmy map => world map",
    }
    if not SELF_EDIT_PATH.exists():
        return defaults
    try:
        data = json.loads(SELF_EDIT_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            defaults.update({key: str(value) for key, value in data.items() if key in defaults})
    except Exception:
        pass
    return defaults


def current_jarvis_prompt() -> str:
    config = load_self_edit_config()
    prompt = config.get("custom_prompt", "").strip()
    if prompt:
        return prompt
    style = config.get("voice_style", "simple").strip().lower()
    if style == "cool":
        return DEFAULT_JARVIS_PROMPT + " Sound calm, confident, and slightly futuristic, but never dramatic."
    if style == "teacher":
        return DEFAULT_JARVIS_PROMPT + " Explain like a helpful teacher, with simple examples when useful."
    if style == "fast":
        return DEFAULT_JARVIS_PROMPT + " Be extra brief. Prefer one short sentence."
    return DEFAULT_JARVIS_PROMPT


def is_armenian_text(text: str) -> bool:
    return False


def choose_language(text: str) -> str:
    return "en"


def localized(en: str, hy: str, source: str) -> str:
    return en


def project_generation_intent(text: str) -> bool:
    normalized = "".join(char if char.isalnum() else " " for char in text.lower())
    words = set(normalized.split())
    action = bool(words & {"generate", "create", "build", "make", "design", "develop"})
    project = bool(words & {"app", "application", "program", "project", "software"})
    speech_misheard_app = bool(words & {"random", "randam", "randomly"}) and bool(words & {"map", "up"})
    return action and (project or speech_misheard_app)


def random_app_intent(text: str) -> bool:
    normalized = "".join(char if char.isalnum() else " " for char in text.lower())
    words = set(normalized.split())
    return project_generation_intent(text) and bool(words & {"random", "randam", "randomly"})


def dist(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def button_style() -> str:
    return """
        QPushButton {
            color: #EAFBFF;
            background: rgba(42, 91, 115, 190);
            border: 1px solid rgba(100, 230, 255, 80);
            border-radius: 9px;
            padding: 7px 10px;
        }
        QPushButton:hover { background: rgba(76, 143, 170, 225); }
        QPushButton:pressed { background: rgba(32, 74, 94, 240); }
        QPushButton:disabled { color: #6F8790; background: rgba(20, 35, 45, 160); }
    """


def input_style() -> str:
    return """
        QLineEdit, QTextEdit, QComboBox, QSpinBox {
            color: #EAFBFF;
            background: rgba(7, 13, 22, 220);
            border: 1px solid rgba(100, 220, 250, 90);
            border-radius: 8px;
            padding: 7px;
            selection-background-color: #28708A;
        }
    """


@dataclass
class AppSettings:
    show_camera: bool = True
    performance_mode: bool = False
    eye_tracking: bool = False
    eye_cursor: bool = False
    phone_port: int = 8765
    ai_endpoint: str = ""
    ai_model: str = ""
    ai_key: str = ""

    @classmethod
    def load(cls) -> "AppSettings":
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            allowed = {k: data[k] for k in cls.__annotations__ if k in data}
            return cls(**allowed)
        except Exception:
            return cls()

    def save(self) -> None:
        SETTINGS_PATH.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")


class ExponentialSmoother:
    def __init__(self, alpha: float = 0.42, deadzone: float = 0.0025):
        self.alpha = alpha
        self.deadzone = deadzone
        self.value: Optional[tuple[float, float]] = None

    def update(self, point: tuple[float, float]) -> tuple[float, float]:
        if self.value is None:
            self.value = point
            return point
        dx = point[0] - self.value[0]
        dy = point[1] - self.value[1]
        if abs(dx) < self.deadzone:
            dx = 0.0
        if abs(dy) < self.deadzone:
            dy = 0.0
        speed = math.hypot(dx, dy)
        adaptive_alpha = clamp(self.alpha + speed * 2.4, self.alpha, 0.82)
        self.value = (
            self.value[0] + dx * adaptive_alpha,
            self.value[1] + dy * adaptive_alpha,
        )
        return self.value


class PinchHysteresis:
    def __init__(self, start_threshold: float = 0.060, release_threshold: float = 0.085):
        self.start_threshold = start_threshold
        self.release_threshold = release_threshold
        self.active = False

    def update(self, distance: float) -> bool:
        if self.active:
            self.active = distance < self.release_threshold
        else:
            self.active = distance < self.start_threshold
        return self.active


class HandTracker:
    """Phase 2: two-hand MediaPipe tracking with smoothing, jitter filtering and pinch hysteresis."""

    def __init__(self, model_path: Path):
        if not model_path.exists():
            raise FileNotFoundError(f"Hand model not found: {model_path}")
        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.55,
            min_hand_presence_confidence=0.55,
            min_tracking_confidence=0.55,
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self.timestamp_ms = 0
        self.smoothers = [ExponentialSmoother(), ExponentialSmoother()]
        self.pinch_filters = [PinchHysteresis(), PinchHysteresis()]

    @staticmethod
    def _finger_map(points: list[tuple[float, float, float]]) -> dict[str, bool]:
        wrist = points[0]
        return {
            "thumb": dist(points[4], wrist) > dist(points[3], wrist) * 1.03,
            "index": points[8][1] < points[6][1],
            "middle": points[12][1] < points[10][1],
            "ring": points[16][1] < points[14][1],
            "pinky": points[20][1] < points[18][1],
        }

    @staticmethod
    def _palm_open(points: list[tuple[float, float, float]], fingers: dict[str, bool]) -> bool:
        spread = dist(points[8], points[20])
        return sum(fingers.values()) >= 4 and spread > 0.18

    @staticmethod
    def _gesture(fingers: dict[str, bool], pinch: bool, palm_open: bool) -> str:
        extended = sum(fingers.values())
        if pinch:
            return "pinch"
        if palm_open:
            return "open"
        if extended <= 1 and fingers.get("index"):
            return "point"
        if extended == 0:
            return "fist"
        if fingers.get("index") and fingers.get("middle") and extended == 2:
            return "victory"
        return "hand"

    def process(self, bgr_frame: np.ndarray) -> list[dict[str, Any]]:
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self.timestamp_ms += 33
        result = self.landmarker.detect_for_video(mp_image, self.timestamp_ms)

        raw_hands: list[dict[str, Any]] = []
        for index, landmarks in enumerate(result.hand_landmarks):
            points = [(lm.x, lm.y, lm.z) for lm in landmarks]
            handedness = "Unknown"
            if index < len(result.handedness) and result.handedness[index]:
                handedness = result.handedness[index][0].category_name or "Unknown"
            raw_hands.append({"points": points, "handedness": handedness})

        raw_hands.sort(key=lambda item: item["points"][0][0])
        hands: list[dict[str, Any]] = []
        for slot, item in enumerate(raw_hands[:2]):
            points = item["points"]
            fingers = self._finger_map(points)
            pinch_distance = dist(points[4], points[8])
            pinching = self.pinch_filters[slot].update(pinch_distance)
            palm_open = self._palm_open(points, fingers)
            sx, sy = self.smoothers[slot].update((points[8][0], points[8][1]))
            gesture = self._gesture(fingers, pinching, palm_open)
            hands.append({
                "points": points,
                "handedness": item["handedness"],
                "index": (sx, sy, points[8][2]),
                "thumb": points[4],
                "palm": points[9],
                "fingers": fingers,
                "pinch_distance": pinch_distance,
                "pinch_strength": clamp(1.0 - pinch_distance / 0.10, 0.0, 1.0),
                "pinching": pinching,
                "palm_open": palm_open,
                "gesture": gesture,
            })
        return hands

    def close(self) -> None:
        self.landmarker.close()


class FaceTracker:
    """Phase 8: optional MediaPipe iris/head tracking."""

    def __init__(self, model_path: Path):
        if not model_path.exists():
            raise FileNotFoundError(f"Face model not found: {model_path}")
        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)
        self.timestamp_ms = 0
        self.gaze_smoother = ExponentialSmoother(alpha=0.22, deadzone=0.0015)

    @staticmethod
    def _mean(points: list[Any], ids: list[int]) -> tuple[float, float]:
        valid = [points[i] for i in ids if i < len(points)]
        if not valid:
            return 0.5, 0.5
        return sum(p.x for p in valid) / len(valid), sum(p.y for p in valid) / len(valid)

    def process(self, bgr_frame: np.ndarray) -> Optional[dict[str, Any]]:
        rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self.timestamp_ms += 33
        result = self.landmarker.detect_for_video(mp_image, self.timestamp_ms)
        if not result.face_landmarks:
            return None
        points = result.face_landmarks[0]
        nose = points[1]
        left_iris = self._mean(points, [474, 475, 476, 477])
        right_iris = self._mean(points, [469, 470, 471, 472])
        iris = ((left_iris[0] + right_iris[0]) / 2, (left_iris[1] + right_iris[1]) / 2)

        # Face-relative gaze estimate. It is intentionally conservative to reduce drift.
        left_corner = self._mean(points, [33, 133])
        right_corner = self._mean(points, [362, 263])
        eye_center = ((left_corner[0] + right_corner[0]) / 2, (left_corner[1] + right_corner[1]) / 2)
        gaze_x = clamp(0.5 + (iris[0] - eye_center[0]) * 8.0 + (nose.x - 0.5) * 0.75, 0.0, 1.0)
        gaze_y = clamp(0.5 + (iris[1] - eye_center[1]) * 11.0 + (nose.y - 0.5) * 0.45, 0.0, 1.0)
        gaze_x, gaze_y = self.gaze_smoother.update((gaze_x, gaze_y))
        return {
            "gaze": (gaze_x, gaze_y),
            "head": (nose.x - 0.5, nose.y - 0.5),
            "nose": (nose.x, nose.y),
        }

    def close(self) -> None:
        self.landmarker.close()


class CameraWorker(threading.Thread):
    """Continuously captures only the newest webcam frame outside the Qt UI thread."""

    def __init__(self, camera_index: int = 0, width: int = 640, height: int = 360, target_fps: int = 30):
        super().__init__(name="HoloDeskCamera", daemon=True)
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._sequence = 0
        self._fps = 0.0
        self._opened = False
        self._status = "Starting camera…"
        self._cap: Optional[cv2.VideoCapture] = None

    def run(self) -> None:
        backend = cv2.CAP_DSHOW if IS_WINDOWS else cv2.CAP_ANY
        cap = cv2.VideoCapture(self.camera_index, backend)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(self.camera_index)
        self._cap = cap
        if not cap.isOpened():
            with self._lock:
                self._status = "Camera not found"
            return

        # MJPG + one-frame buffer prevents an old-frame queue from building up.
        try:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.target_fps)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        with self._lock:
            self._opened = True
            self._status = "Camera active"

        frames = 0
        started = time.perf_counter()
        try:
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    with self._lock:
                        self._status = "Camera frame unavailable"
                    time.sleep(0.01)
                    continue

                frame = cv2.flip(frame, 1)
                frames += 1
                now = time.perf_counter()
                elapsed = now - started
                with self._lock:
                    self._latest_frame = frame
                    self._sequence += 1
                    self._status = "Camera active"
                    if elapsed >= 1.0:
                        self._fps = frames / elapsed
                        frames = 0
                        started = now
        finally:
            cap.release()
            with self._lock:
                self._opened = False
                if self._status == "Camera active":
                    self._status = "Camera stopped"

    def snapshot(self) -> tuple[Optional[np.ndarray], int, float, str, bool]:
        with self._lock:
            return self._latest_frame, self._sequence, self._fps, self._status, self._opened

    def stop(self) -> None:
        self._stop_event.set()


class TrackingWorker(threading.Thread):
    """Runs MediaPipe at its own cadence and publishes the newest result only."""

    def __init__(
        self,
        camera: CameraWorker,
        performance_mode: Callable[[], bool],
        eye_tracking_enabled: Callable[[], bool],
    ):
        super().__init__(name="HoloDeskTracking", daemon=True)
        self.camera = camera
        self.performance_mode = performance_mode
        self.eye_tracking_enabled = eye_tracking_enabled
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._hands: list[dict[str, Any]] = []
        self._face: Optional[dict[str, Any]] = None
        self._sequence = 0
        self._fps = 0.0
        self._status = "Starting hand tracker…"
        self._hand_tracker: Optional[HandTracker] = None
        self._face_tracker: Optional[FaceTracker] = None
        self._eye_model_failed = False

    def _set_status(self, status: str) -> None:
        with self._lock:
            self._status = status

    def run(self) -> None:
        try:
            self._hand_tracker = HandTracker(HAND_MODEL_PATH)
        except Exception as exc:
            self._set_status(f"Hand model: {exc}")
            return

        last_camera_sequence = -1
        next_process_at = 0.0
        processed = 0
        fps_started = time.perf_counter()
        eye_cycle = 0
        self._set_status("Hand tracking active")

        try:
            while not self._stop_event.is_set():
                performance = bool(self.performance_mode())
                interval = 1.0 / (15.0 if performance else 20.0)
                now = time.perf_counter()
                if now < next_process_at:
                    time.sleep(min(0.004, next_process_at - now))
                    continue

                frame, camera_sequence, _, camera_status, opened = self.camera.snapshot()
                if frame is None or camera_sequence == last_camera_sequence:
                    if not opened and camera_status == "Camera not found":
                        self._set_status(camera_status)
                    time.sleep(0.005)
                    continue

                last_camera_sequence = camera_sequence
                next_process_at = now + interval
                target_size = (384, 216) if performance else (512, 288)
                tracking_frame = cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)

                try:
                    hands = self._hand_tracker.process(tracking_frame)
                except Exception as exc:
                    self._set_status(f"Tracking error: {exc}")
                    time.sleep(0.05)
                    continue

                face: Optional[dict[str, Any]] = None
                face_processed = False
                eye_enabled = bool(self.eye_tracking_enabled())
                if eye_enabled:
                    if self._face_tracker is None and not self._eye_model_failed:
                        try:
                            self._face_tracker = FaceTracker(FACE_MODEL_PATH)
                        except Exception as exc:
                            self._eye_model_failed = True
                            self._set_status(f"Eye model: {exc}")
                    eye_cycle += 1
                    # Face/iris inference is heavier, so run it at half the hand cadence.
                    if self._face_tracker is not None and eye_cycle % 2 == 0:
                        face_processed = True
                        try:
                            face = self._face_tracker.process(tracking_frame)
                        except Exception:
                            face = None
                else:
                    self._eye_model_failed = False
                    if self._face_tracker is not None:
                        try:
                            self._face_tracker.close()
                        except Exception:
                            pass
                        self._face_tracker = None

                processed += 1
                elapsed = time.perf_counter() - fps_started
                with self._lock:
                    self._hands = hands
                    if face_processed or not eye_enabled:
                        self._face = face
                    self._sequence += 1
                    if not eye_enabled or not self._eye_model_failed:
                        self._status = "Hand tracking active"
                    if elapsed >= 1.0:
                        self._fps = processed / elapsed
                        processed = 0
                        fps_started = time.perf_counter()
        finally:
            if self._hand_tracker is not None:
                try:
                    self._hand_tracker.close()
                except Exception:
                    pass
            if self._face_tracker is not None:
                try:
                    self._face_tracker.close()
                except Exception:
                    pass

    def snapshot(self) -> tuple[list[dict[str, Any]], Optional[dict[str, Any]], int, float, str]:
        with self._lock:
            return self._hands, self._face, self._sequence, self._fps, self._status

    def stop(self) -> None:
        self._stop_event.set()


class WindowsController:
    """Phase 1: enumerate and control real Windows application windows."""

    def __init__(self):
        self.available = bool(IS_WINDOWS and WIN32_AVAILABLE)

    def list_windows(self) -> list[dict[str, Any]]:
        if not self.available:
            return []
        rows: list[dict[str, Any]] = []

        def callback(hwnd: int, _: Any) -> None:
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                title = win32gui.GetWindowText(hwnd).strip()
                if not title:
                    return
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process_name = ""
                if PSUTIL_AVAILABLE:
                    try:
                        process_name = psutil.Process(pid).name()
                    except Exception:
                        process_name = ""
                rect = win32gui.GetWindowRect(hwnd)
                rows.append({
                    "hwnd": hwnd,
                    "title": title,
                    "pid": pid,
                    "process": process_name,
                    "rect": rect,
                    "minimized": bool(win32gui.IsIconic(hwnd)),
                    "maximized": bool(win32gui.IsZoomed(hwnd)),
                })
            except Exception:
                return

        win32gui.EnumWindows(callback, None)
        rows.sort(key=lambda row: row["title"].lower())
        return rows

    def _valid(self, hwnd: int) -> bool:
        return bool(self.available and hwnd and win32gui.IsWindow(hwnd))

    def bring_to_front(self, hwnd: int) -> bool:
        if not self._valid(hwnd):
            return False
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                # Windows foreground-lock workaround.
                ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
                win32gui.SetForegroundWindow(hwnd)
                ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
            return True
        except Exception:
            return False

    def action(self, hwnd: int, action: str) -> bool:
        if not self._valid(hwnd):
            return False
        try:
            actions = {
                "minimize": win32con.SW_MINIMIZE,
                "maximize": win32con.SW_MAXIMIZE,
                "restore": win32con.SW_RESTORE,
            }
            if action in actions:
                win32gui.ShowWindow(hwnd, actions[action])
            elif action == "close":
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            elif action in {"snap_left", "snap_right"}:
                screen_w = win32api.GetSystemMetrics(0)
                screen_h = win32api.GetSystemMetrics(1)
                x = 0 if action == "snap_left" else screen_w // 2
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.MoveWindow(hwnd, x, 0, screen_w // 2, screen_h, True)
            else:
                return False
            return True
        except Exception:
            return False

    def launch(self, executable: str) -> bool:
        try:
            if executable == "chrome":
                executable = shutil.which("chrome") or next((str(path) for path in (
                    Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
                    Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
                    Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Google/Chrome/Application/chrome.exe",
                ) if path.is_file()), "chrome")
            subprocess.Popen([executable], shell=False)
            return True
        except Exception:
            return False

    def voice_command(self, command: tuple) -> bool:
        kind, value, _ = command
        try:
            if kind == "launch":
                return self.launch(value)
            if kind == "folder":
                folder = Path.home() / value
                if not folder.is_dir():
                    return False
                subprocess.Popen(["explorer.exe", str(folder)], shell=False)
                return True
            if not self.available:
                return False
            if kind == "window":
                return self.action(win32gui.GetForegroundWindow(), value)
            if kind == "keys":
                pressed = []
                try:
                    for key in value:
                        win32api.keybd_event(key, 0, 0, 0)
                        pressed.append(key)
                finally:
                    for key in reversed(pressed):
                        win32api.keybd_event(key, 0, win32con.KEYEVENTF_KEYUP, 0)
                return True
        except Exception:
            return False
        return False

    def move_cursor(self, dx: int, dy: int) -> None:
        if not self.available:
            return
        try:
            x, y = win32api.GetCursorPos()
            win32api.SetCursorPos((x + dx, y + dy))
        except Exception:
            pass

    def click(self) -> None:
        if not self.available:
            return
        try:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        except Exception:
            pass


class AIClient:
    """Phase 4: OpenAI-compatible endpoint with a safe local fallback."""

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self._history: list[dict[str, str]] = []
        self._history_lock = threading.Lock()
        self._history_limit = 12
        self._conversation_generation = 0

    def clear_memory(self) -> None:
        with self._history_lock:
            self._history.clear()
            self._conversation_generation += 1

    def memory_size(self) -> int:
        with self._history_lock:
            return len(self._history) // 2

    def _memory_snapshot(self) -> list[dict[str, str]]:
        with self._history_lock:
            return [dict(item) for item in self._history]

    def _remember(self, user_message: str, assistant_message: str, generation: Optional[int] = None) -> None:
        with self._history_lock:
            if generation is not None and generation != self._conversation_generation:
                return
            self._history.extend([
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            ])
            if len(self._history) > self._history_limit:
                self._history = self._history[-self._history_limit:]

    @property
    def configured(self) -> bool:
        endpoint = self.effective_endpoint
        local_endpoint = "localhost" in endpoint or "127.0.0.1" in endpoint
        return bool(endpoint and self.effective_model and (self.effective_key or local_endpoint))

    @property
    def effective_endpoint(self) -> str:
        return (
            self.settings.ai_endpoint.strip()
            or os.environ.get("JARVIS_AI_ENDPOINT", "").strip()
            or DEFAULT_AI_ENDPOINT
        )

    @property
    def effective_model(self) -> str:
        return (
            self.settings.ai_model.strip()
            or os.environ.get("JARVIS_AI_MODEL", "").strip()
            or DEFAULT_AI_MODEL
        )

    @property
    def effective_key(self) -> str:
        return (
            os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
            or os.environ.get("JARVIS_AI_API_KEY", "").strip()
            or self.settings.ai_key.strip()
            or api_key_from_file()
        )

    def chat(
        self,
        message: str,
        system_prompt: str = "",
        max_output_tokens: Optional[int] = None,
        clean: bool = True,
        use_memory: bool = True,
    ) -> str:
        message = message.strip()
        if not message:
            return "Type a question or command."
        if not self.configured:
            return self.local_response(message)

        with self._history_lock:
            generation = self._conversation_generation
            history = [dict(item) for item in self._history] if use_memory else []
        endpoint = self.effective_endpoint.rstrip("/")
        if "generativelanguage.googleapis.com" in endpoint:
            result = self._chat_gemini_native(message, system_prompt, max_output_tokens, clean, history)
        else:
            result = self._chat_openai_compatible(message, system_prompt, max_output_tokens, clean, history)
        if use_memory and result and not result.startswith("AI connection error:"):
            self._remember(message, result, generation)
        return result

    @staticmethod
    def _normalize_gemini_endpoint(endpoint: str) -> str:
        endpoint = endpoint.rstrip("/")
        for suffix in ("/openai/chat/completions", "/chat/completions", "/openai"):
            if endpoint.endswith(suffix):
                endpoint = endpoint[: -len(suffix)].rstrip("/")
        if endpoint.endswith("/v1") or endpoint.endswith("/v1beta"):
            return endpoint
        return DEFAULT_AI_ENDPOINT

    def _chat_gemini_native(
        self,
        message: str,
        system_prompt: str = "",
        max_output_tokens: Optional[int] = None,
        clean: bool = True,
        history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        endpoint = self._normalize_gemini_endpoint(self.effective_endpoint)
        model = self.effective_model
        key = self.effective_key
        url = f"{endpoint}/models/{urllib.parse.quote(model, safe='')}:generateContent?key={urllib.parse.quote(key)}"
        contents = [
            {
                "role": "model" if item.get("role") == "assistant" else "user",
                "parts": [{"text": str(item.get("content", ""))}],
            }
            for item in (history or [])
            if item.get("content")
        ]
        contents.append({"role": "user", "parts": [{"text": message}]})
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": system_prompt
                        or current_jarvis_prompt()
                    }
                ]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.55,
                "maxOutputTokens": max_output_tokens or AI_MAX_OUTPUT_TOKENS,
            },
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=AI_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts).strip()
            if not text:
                return self.local_response(message)
            return self._clean_assistant_text(text) if clean else text
        except urllib.error.HTTPError as exc:
            return self._http_error_text(exc, message)
        except Exception as exc:
            return f"AI connection error: {exc}\n\nLocal fallback:\n{self.local_response(message)}"

    def _chat_openai_compatible(
        self,
        message: str,
        system_prompt: str = "",
        max_output_tokens: Optional[int] = None,
        clean: bool = True,
        history: Optional[list[dict[str, str]]] = None,
    ) -> str:
        endpoint = self.effective_endpoint.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        payload = {
            "model": self.effective_model,
            "messages": (
                [{"role": "system", "content": system_prompt or current_jarvis_prompt()}]
                + [dict(item) for item in (history or [])]
                + [{"role": "user", "content": message}]
            ),
            "temperature": 0.55,
        }
        if max_output_tokens:
            payload["max_tokens"] = max_output_tokens
        headers = {"Content-Type": "application/json"}
        if self.effective_key:
            headers["Authorization"] = f"Bearer {self.effective_key}"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=AI_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"].strip()
            return self._clean_assistant_text(text) if clean else text
        except urllib.error.HTTPError as exc:
            return self._http_error_text(exc, message)
        except Exception as exc:
            return f"AI connection error: {exc}\n\nLocal fallback:\n{self.local_response(message)}"

    def _http_error_text(self, exc: urllib.error.HTTPError, message: str) -> str:
        details = ""
        try:
            details = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            details = ""
        if details:
            details = details[:900]
            return f"AI connection error: HTTP {exc.code}\n{details}\n\nLocal fallback:\n{self.local_response(message)}"
        return f"AI connection error: HTTP {exc.code}: {exc.reason}\n\nLocal fallback:\n{self.local_response(message)}"

    def project_plan(self, request: str) -> dict[str, Any]:
        request = request.strip()
        if not request:
            raise ValueError("Describe what JARVIS should build.")
        if not self.configured:
            return local_starter_plan(request)

        system_prompt = (
            "You are the planning engine inside JARVIS Mission Builder. "
            "Create a small, complete, runnable project for the user's request. "
            "Return only one valid JSON object with this exact schema: "
            '{"project_name":"short_name","summary":"one sentence","run_file":"relative/path",'
            '"files":[{"path":"relative/path","content":"complete text content"}]}. '
            "Use only relative file paths. Include all source files and a README with exact run instructions. "
            "Create at most 12 text files. Do not include binary data, secrets, API keys, destructive scripts, "
            "credential theft, persistence, evasion, or commands that alter files outside the project folder. "
            "Do not use markdown fences or add commentary outside the JSON."
        )
        response = self.chat(
            request,
            system_prompt,
            max_output_tokens=4096,
            clean=False,
            use_memory=False,
        )
        if response.startswith("AI connection error:"):
            raise RuntimeError(response.split("\n", 1)[0])
        return normalize_project_plan(json_object_from_text(response), request)

    def project_patch(self, root: Path, request: str) -> dict[str, Any]:
        request = request.strip()
        if not request:
            raise ValueError("Describe the change JARVIS should make.")
        if not root.exists() or not root.is_dir():
            raise ValueError("Choose a valid project folder.")
        if not self.configured:
            raise RuntimeError("Connect Gemini before asking JARVIS to edit an existing project.")
        snapshot = project_text_snapshot(root)
        if not snapshot:
            raise ValueError("No supported text source files were found in this project.")
        system_prompt = (
            "You are the coding agent inside JARVIS. Modify an existing local project to satisfy the request. "
            "Return only one valid JSON object with this schema: "
            '{"summary":"what changed","files":[{"path":"relative/path","content":"complete replacement content"}]}. '
            "Include only files that must be created or completely replaced. Preserve unrelated behavior. "
            "Use only relative paths. Do not delete files. Do not include binary data, secrets, credentials, "
            "persistence, evasion, destructive commands, or writes outside the project folder. "
            "Do not use markdown fences or commentary outside the JSON."
        )
        payload = json.dumps(
            {"request": request, "project_files": snapshot},
            ensure_ascii=False,
        )
        response = self.chat(
            payload,
            system_prompt,
            max_output_tokens=8192,
            clean=False,
            use_memory=False,
        )
        if response.startswith("AI connection error:"):
            raise RuntimeError(response.split("\n", 1)[0])
        return normalize_agent_patch(json_object_from_text(response), request)

    @staticmethod
    def _clean_assistant_text(text: str) -> str:
        lines = [line.strip().lstrip("-*• ").strip() for line in text.splitlines()]
        return " ".join(line for line in lines if line).strip()

    @staticmethod
    def local_response(message: str) -> str:
        low = message.lower()
        now = datetime.now()
        if any(word in low for word in ["help", "commands", "what can you do"]):
            return "I can control Windows, create complete projects, and safely edit the last app with backups. Say build project or tell me what to change."
        if any(word in low for word in ["your name", "who are you"]):
            return "I am JARVIS, your Windows assistant."
        if any(word in low for word in ["time", "what time"]):
            return f"The time is {now.strftime('%H:%M:%S')}."
        if any(word in low for word in ["weather"]):
            return "Weather is not fully connected yet. I can open the weather window, and later we can add live data."
        if any(word in low for word in ["summarize"]):
            clean = " ".join(message.split())
            return clean[:420] + ("…" if len(clean) > 420 else "")
        if any(word in low for word in ["rewrite"]):
            return "I can help in a simple way now, but full rewriting needs Gemini to be connected."
        return "I am here. You can ask a question or tell me what to open on the computer."


class AIWorker(QThread):
    finished_text = Signal(str)

    def __init__(self, client: AIClient, message: str, system_prompt: str = ""):
        super().__init__()
        self.client = client
        self.message = message
        self.system_prompt = system_prompt

    def run(self) -> None:
        self.finished_text.emit(self.client.chat(self.message, self.system_prompt))


class ProjectPlanWorker(QThread):
    planned = Signal(object)
    failed = Signal(str)

    def __init__(self, client: AIClient, request: str):
        super().__init__()
        self.client = client
        self.request = request

    def run(self) -> None:
        try:
            self.planned.emit(self.client.project_plan(self.request))
        except Exception as exc:
            self.failed.emit(str(exc))


class ProjectPatchWorker(QThread):
    planned = Signal(object)
    failed = Signal(str)

    def __init__(self, client: AIClient, root: Path, request: str):
        super().__init__()
        self.client = client
        self.root = root
        self.request = request

    def run(self) -> None:
        try:
            self.planned.emit(self.client.project_patch(self.root, self.request))
        except Exception as exc:
            self.failed.emit(str(exc))


class WeatherWorker(QThread):
    finished_data = Signal(dict)
    failed = Signal(str)

    def __init__(self, city: str):
        super().__init__()
        self.city = city

    def run(self) -> None:
        try:
            geo_url = (
                "https://geocoding-api.open-meteo.com/v1/search?"
                + urllib.parse.urlencode({"name": self.city, "count": 1, "language": "en", "format": "json"})
            )
            with urllib.request.urlopen(geo_url, timeout=15) as response:
                geo = json.loads(response.read().decode("utf-8"))
            if not geo.get("results"):
                raise RuntimeError("City not found")
            place = geo["results"][0]
            weather_url = (
                "https://api.open-meteo.com/v1/forecast?"
                + urllib.parse.urlencode({
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
                    "timezone": "auto",
                })
            )
            with urllib.request.urlopen(weather_url, timeout=15) as response:
                weather = json.loads(response.read().decode("utf-8"))
            self.finished_data.emit({"place": place, "current": weather.get("current", {})})
        except Exception as exc:
            self.failed.emit(str(exc))


class VoiceWorker(QThread):
    heard = Signal(str)
    failed = Signal(str)

    @staticmethod
    def _choose_recognition_result(results: list[tuple[str, str]]) -> str:
        if not results:
            return ""
        by_lang = {language: text.strip() for language, text in results if text.strip()}
        english = by_lang.get("en-US", "")
        if english:
            return english
        return results[0][1].strip()

    def _recognize_from_microphone(self) -> str:
        """Primary voice path: record directly from the default Windows microphone."""
        try:
            import sounddevice as sd
            import speech_recognition as sr
            import numpy as np
        except Exception as exc:
            raise RuntimeError(f"Voice packages missing: {exc}")

        try:
            device = sd.query_devices(kind="input")
            sample_rate = int(float(device.get("default_samplerate", 44100)))
            sample_rate = sample_rate if sample_rate >= 8000 else 44100
        except Exception:
            sample_rate = 44100

        seconds = max(2.0, min(6.0, VOICE_RECORD_SECONDS))
        try:
            recording = sd.rec(
                int(seconds * sample_rate),
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocking=True,
            )
        except Exception as exc:
            raise RuntimeError(f"Microphone could not start: {exc}")

        samples = np.asarray(recording, dtype=np.float32).reshape(-1)
        if samples.size == 0:
            raise RuntimeError("Microphone returned no audio.")

        # Remove DC offset and amplify quiet microphones without clipping.
        samples = samples - float(np.mean(samples))
        peak = float(np.max(np.abs(samples))) if samples.size else 0.0
        rms = float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0

        if peak < 0.002 or rms < 0.0004:
            raise RuntimeError("No speech recognized.")

        target_peak = 0.85
        gain = min(12.0, target_peak / max(peak, 1e-6))
        samples = np.clip(samples * gain, -1.0, 1.0)
        pcm16 = (samples * 32767.0).astype(np.int16).tobytes()

        recognizer = sr.Recognizer()
        recognizer.operation_timeout = 4
        audio = sr.AudioData(pcm16, sample_rate, 2)

        errors: list[str] = []
        results: list[tuple[str, str]] = []

        def recognize(language: str) -> tuple[str, str, str]:
            try:
                result = recognizer.recognize_google(audio, language=language)
                if result and result.strip():
                    return language, result.strip(), ""
                return language, "", f"No {language} speech recognized"
            except sr.UnknownValueError:
                return language, "", f"No {language} speech recognized"
            except sr.RequestError as exc:
                return language, "", f"Speech service error: {exc}"
            except Exception as exc:
                return language, "", str(exc)

        # English-only recognition keeps the response path faster.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            futures = [executor.submit(recognize, "en-US")]
            try:
                for future in concurrent.futures.as_completed(futures, timeout=6):
                    language, result, error = future.result()
                    if result:
                        results.append((language, result))
                    elif error:
                        errors.append(error)
            except concurrent.futures.TimeoutError:
                errors.append("Speech recognition timed out")

        choice = self._choose_recognition_result(results)
        if choice:
            return choice

        raise RuntimeError("; ".join(errors) or "No speech recognized.")

    def _recognize_windows(self) -> str:
        if not IS_WINDOWS:
            raise RuntimeError("Windows speech fallback requires Windows.")
        windir = os.environ.get("WINDIR", r"C:\\Windows")
        powershell = os.path.join(windir, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
        if not os.path.exists(powershell):
            powershell = "powershell.exe"
        ps_script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Speech
$installed = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()
if (-not $installed -or $installed.Count -eq 0) { throw 'No Windows speech recognizer is installed.' }
$choice = $installed | Where-Object { $_.Culture.Name -eq 'en-US' } | Select-Object -First 1
if (-not $choice) { $choice = $installed | Select-Object -First 1 }
$recognizer = [System.Speech.Recognition.SpeechRecognitionEngine]::new($choice)
$recognizer.SetInputToDefaultAudioDevice()
$grammar = [System.Speech.Recognition.DictationGrammar]::new()
$recognizer.LoadGrammar($grammar)
$result = $recognizer.Recognize([TimeSpan]::FromSeconds(7))
if ($result -and $result.Text) { Write-Output $result.Text } else { throw 'No speech recognized.' }
$recognizer.Dispose()
"""
        completed = subprocess.run(
            [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, timeout=12, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0,
        )
        if completed.returncode == 0 and (completed.stdout or "").strip():
            return completed.stdout.strip().splitlines()[-1].strip()
        raise RuntimeError((completed.stderr or "Windows speech failed").strip()[-500:])

    def run(self) -> None:
        errors = []
        try:
            text = self._recognize_from_microphone()
            self.heard.emit(text)
            return
        except Exception as exc:
            errors.append(f"Direct mic: {exc}")

        try:
            text = self._recognize_windows()
            self.heard.emit(text)
            return
        except Exception as exc:
            errors.append(f"Windows fallback: {exc}")

        self.failed.emit(" | ".join(errors))




class SpeechWorker(QThread):
    """Speak assistant replies without blocking the HoloDesk UI.

    Windows TTS order:
      1) ElevenLabs -- natural cloud voice when its key is configured.
      2) Gemini TTS -- cloud voice when GEMINI_API_KEY is set.
      3) Edge neural TTS -- natural no-extra-key fallback.
      4) SAPI.SpVoice COM -- reliable on normal Windows desktops.
      5) System.Speech.Synthesis fallback.
    """
    finished_speaking = Signal()
    failed = Signal(str)
    engine_used = Signal(str)

    def __init__(self, text: str):
        super().__init__()
        self.original_text = (text or "").strip()
        self.text = self._make_speakable(self.original_text)
        self.edge_text = self._edge_speakable_text(self.original_text)

    @staticmethod
    def _has_armenian(text: str) -> bool:
        return any("\u0531" <= char <= "\u058f" for char in text)

    @classmethod
    def _edge_speakable_text(cls, text: str) -> str:
        return text or ""

    @staticmethod
    def _make_speakable(text: str) -> str:
        return text

    def _powershell_path(self) -> str:
        windir = os.environ.get("WINDIR", r"C:\Windows")
        classic = os.path.join(
            windir, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"
        )
        return classic if os.path.exists(classic) else "powershell.exe"

    def _run_ps(self, script: str, timeout: int = 60) -> tuple[bool, str]:
        completed = subprocess.run(
            [
                self._powershell_path(),
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-STA",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            input=self.text,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if IS_WINDOWS else 0,
        )
        if completed.returncode == 0:
            return True, ""
        return False, (completed.stderr or completed.stdout or "TTS failed").strip()[-900:]

    def _play_audio_file(self, audio_path: Path, timeout: int = 60) -> tuple[bool, str]:
        uri = audio_path.resolve().as_uri()
        escaped_uri = uri.replace("'", "''")
        script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName PresentationCore
$player = [System.Windows.Media.MediaPlayer]::new()
$player.Open([Uri]'{escaped_uri}')
$player.Volume = 1
$player.Play()
$deadline = [DateTime]::Now.AddSeconds({int(timeout)})
while (-not $player.NaturalDuration.HasTimeSpan -and [DateTime]::Now -lt $deadline) {{
    Start-Sleep -Milliseconds 100
}}
if ($player.NaturalDuration.HasTimeSpan) {{
    $sleepMs = [Math]::Min([int]$player.NaturalDuration.TimeSpan.TotalMilliseconds + 350, {int(timeout)} * 1000)
    Start-Sleep -Milliseconds $sleepMs
}} else {{
    Start-Sleep -Seconds 3
}}
$player.Stop()
$player.Close()
"""
        return self._run_ps(script, timeout=timeout + 5)

    def _write_wave_file(
        self,
        filename: Path,
        pcm: bytes,
        channels: int = 1,
        rate: int = 24000,
        sample_width: int = 2,
    ) -> None:
        with wave.open(str(filename), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm)

    @staticmethod
    def _find_audio_data(value: Any) -> Optional[str]:
        if isinstance(value, dict):
            output_audio = value.get("output_audio") or value.get("outputAudio")
            if isinstance(output_audio, dict) and isinstance(output_audio.get("data"), str):
                return output_audio["data"]
            inline_data = value.get("inlineData") or value.get("inline_data")
            if isinstance(inline_data, dict) and isinstance(inline_data.get("data"), str):
                return inline_data["data"]
            for item in value.values():
                found = SpeechWorker._find_audio_data(item)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = SpeechWorker._find_audio_data(item)
                if found:
                    return found
        return None

    def _run_elevenlabs_tts(self) -> tuple[bool, str]:
        key = elevenlabs_api_key()
        if not key:
            return False, "ElevenLabs API key is not set."

        text = self.original_text.strip()
        if not text:
            return True, ""

        voice_id = elevenlabs_voice_id()
        config = voice_config_from_file()
        model = (
            os.environ.get("JARVIS_ELEVENLABS_MODEL", "").strip()
            or config.get("ELEVENLABS_MODEL_ID", "")
            or "eleven_flash_v2_5"
        )
        fd, raw_path = tempfile.mkstemp(prefix="jarvis_elevenlabs_voice_", suffix=".mp3")
        os.close(fd)
        audio_path = Path(raw_path)

        try:
            payload = {
                "text": text,
                "model_id": model,
                "language_code": "en",
                "voice_settings": {
                    "stability": 0.52,
                    "similarity_boost": 0.82,
                    "style": 0.18,
                    "use_speaker_boost": True,
                },
            }
            url = (
                "https://api.elevenlabs.io/v1/text-to-speech/"
                f"{urllib.parse.quote(voice_id, safe='')}"
                "?output_format=mp3_44100_128&optimize_streaming_latency=3"
            )
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": key,
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=ELEVENLABS_TTS_TIMEOUT_SECONDS) as response:
                audio = response.read()
            if len(audio) < 256:
                return False, "ElevenLabs returned an empty audio response."
            audio_path.write_bytes(audio)
            return self._play_audio_file(audio_path, timeout=ELEVENLABS_TTS_TIMEOUT_SECONDS)
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:400]
            except Exception:
                detail = exc.reason
            return False, f"HTTP {exc.code}: {detail}"
        except Exception as exc:
            return False, str(exc)
        finally:
            try:
                audio_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _run_gemini_tts(self) -> tuple[bool, str]:
        key = (
            os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
            or os.environ.get("JARVIS_AI_API_KEY", "").strip()
            or api_key_from_file()
        )
        if not key:
            return False, "Gemini API key is not set. Add it to VOICE_API_KEY.txt."

        text = self.original_text.strip()
        if not text:
            return True, ""

        model = os.environ.get("JARVIS_GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview").strip()
        voice = os.environ.get("JARVIS_GEMINI_TTS_VOICE", "Kore").strip() or "Kore"
        prompt = (
            "Say clearly in a calm, natural, futuristic AI assistant voice. "
            "Keep the same language as the transcript. Do not add extra words.\n\n"
            f"Transcript: {text}"
        )
        fd, raw_path = tempfile.mkstemp(prefix="jarvis_gemini_voice_", suffix=".wav")
        os.close(fd)
        audio_path = Path(raw_path)

        try:
            payload = {
                "model": model,
                "input": prompt,
                "response_format": {"type": "audio"},
                "generation_config": {"speech_config": [{"voice": voice}]},
            }
            request = urllib.request.Request(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": key,
                },
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=GEMINI_TTS_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))

            audio_data = self._find_audio_data(data)
            if not audio_data:
                return False, "Gemini did not return audio."

            pcm = base64.b64decode(audio_data)
            self._write_wave_file(audio_path, pcm)
            return self._play_audio_file(audio_path, timeout=EDGE_TTS_TIMEOUT_SECONDS)
        except Exception as exc:
            return False, str(exc)
        finally:
            try:
                audio_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _run_edge_tts(self) -> tuple[bool, str]:
        try:
            import edge_tts
        except Exception as exc:
            return False, "edge-tts is not installed: " + str(exc)

        text = self.edge_text.strip()
        if not text:
            return True, ""

        voice = os.environ.get("JARVIS_EDGE_VOICE", "en-US-GuyNeural").strip() or "en-US-GuyNeural"
        rate = os.environ.get("JARVIS_EDGE_RATE", "+0%").strip() or "+0%"
        pitch = os.environ.get("JARVIS_EDGE_PITCH", "+0Hz").strip() or "+0Hz"
        fd, raw_path = tempfile.mkstemp(prefix="jarvis_voice_", suffix=".mp3")
        os.close(fd)
        audio_path = Path(raw_path)

        try:
            async def save_voice() -> None:
                communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
                await communicate.save(str(audio_path))

            import asyncio
            asyncio.run(asyncio.wait_for(save_voice(), timeout=EDGE_TTS_TIMEOUT_SECONDS))
            return self._play_audio_file(audio_path, timeout=EDGE_TTS_TIMEOUT_SECONDS)
        except Exception as exc:
            return False, str(exc)
        finally:
            try:
                audio_path.unlink(missing_ok=True)
            except Exception:
                pass

    def run(self) -> None:
        if not self.original_text:
            self.finished_speaking.emit()
            return

        if not IS_WINDOWS:
            self.failed.emit("Speech output requires Windows.")
            self.finished_speaking.emit()
            return

        errors = []

        if elevenlabs_api_key():
            try:
                ok, err = self._run_elevenlabs_tts()
                if ok:
                    self.engine_used.emit("ElevenLabs voice")
                    self.finished_speaking.emit()
                    return
                errors.append("ElevenLabs voice: " + err)
            except Exception as exc:
                errors.append("ElevenLabs voice: " + str(exc))

        if VOICE_PRIORITY in {"gemini", "quality"}:
            try:
                ok, err = self._run_gemini_tts()
                if ok:
                    self.engine_used.emit("Gemini voice")
                    self.finished_speaking.emit()
                    return
                errors.append("Gemini voice: " + err)
            except Exception as exc:
                errors.append("Gemini voice: " + str(exc))

        # Fast mode uses Edge first. It is more likely to stay under 3-5s.
        try:
            ok, err = self._run_edge_tts()
            if ok:
                self.engine_used.emit("Edge neural voice")
                self.finished_speaking.emit()
                return
            errors.append("Edge neural voice: " + err)
        except Exception as exc:
            errors.append("Edge neural voice: " + str(exc))

        if VOICE_PRIORITY not in {"gemini", "quality"}:
            try:
                ok, err = self._run_gemini_tts()
                if ok:
                    self.engine_used.emit("Gemini voice")
                    self.finished_speaking.emit()
                    return
                errors.append("Gemini voice: " + err)
            except Exception as exc:
                errors.append("Gemini voice: " + str(exc))

        # 3) SAPI.SpVoice -- uses the normal Windows desktop speech/audio path.
        sapi_script = r"""
$ErrorActionPreference = 'Stop'
$text = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($text)) { exit 0 }

$voice = New-Object -ComObject SAPI.SpVoice
$voice.Volume = 100
$voice.Rate = 0

# Prefer a female/available voice if Windows has multiple voices, otherwise
# keep the default voice when Windows has only one installed voice.
try {
    $voices = @($voice.GetVoices())
    if ($voices.Count -gt 0) {
        $voice.Voice = $voices[0]
    }
} catch {}

[void]$voice.Speak($text, 0)
"""
        try:
            ok, err = self._run_ps(sapi_script, timeout=EDGE_TTS_TIMEOUT_SECONDS)
            if ok:
                self.engine_used.emit("Windows SAPI voice")
                self.finished_speaking.emit()
                return
            errors.append("SAPI: " + err)
        except Exception as exc:
            errors.append("SAPI: " + str(exc))

        # 4) .NET System.Speech fallback.
        dotnet_script = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$text = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($text)) { exit 0 }

$synth = [System.Speech.Synthesis.SpeechSynthesizer]::new()
$synth.Volume = 100
$synth.Rate = 0
$synth.SetOutputToDefaultAudioDevice()
$synth.Speak($text)
$synth.Dispose()
"""
        try:
            ok, err = self._run_ps(dotnet_script, timeout=EDGE_TTS_TIMEOUT_SECONDS)
            if ok:
                self.engine_used.emit("Windows fallback voice")
                self.finished_speaking.emit()
                return
            errors.append("System.Speech: " + err)
        except Exception as exc:
            errors.append("System.Speech: " + str(exc))

        self.failed.emit(" | ".join(errors) or "Windows TTS failed.")
        self.finished_speaking.emit()


class AudioFileWorker(QThread):
    """Play a local sound without blocking the interface."""

    completed = Signal()
    failed = Signal(str)

    def __init__(self, path: Path, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.path = path

    def run(self) -> None:
        try:
            helper = SpeechWorker("")
            ok, error = helper._play_audio_file(self.path, timeout=8)
            if not ok:
                self.failed.emit(error)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.completed.emit()


class VoiceAIWorker(QThread):
    answered = Signal(str)

    def __init__(self, client: AIClient, question: str):
        super().__init__()
        self.client = client
        self.question = question

    def run(self) -> None:
        prompt = current_jarvis_prompt() + " The assistant is in English-only mode. Reply only in English."
        try:
            self.answered.emit(self.client.chat(self.question, prompt))
        except Exception as exc:
            self.answered.emit(f"I could not answer the question. {exc}")


class AutoVoiceController(QObject):
    """Always-on talking voice assistant for HoloDesk."""
    status_changed = Signal(str)

    def __init__(
        self,
        canvas: "HoloCanvas",
        parent: Optional[QObject] = None,
        start_immediately: bool = True,
    ):
        super().__init__(parent)
        self.canvas = canvas
        self.worker: Optional[VoiceWorker] = None
        self.speaker: Optional[SpeechWorker] = None
        self.ai_worker: Optional[VoiceAIWorker] = None
        self.enabled = True
        self._closing = False
        self._restart_delay_ms = 350
        self._last_error = ""
        self._busy_reply = False
        self._discard_recording = False
        self._pending_spoken = ''

        # Rate-limit / loop protection.
        self._last_heard_norm = ""
        self._last_heard_at = 0.0
        self._last_spoken_norm = ""
        self._last_spoken_at = 0.0
        self._last_user_language = "en"
        self._ai_cooldown_until = 0.0
        self._duplicate_window_sec = 8.0
        self._self_echo_window_sec = 7.0
        self._rate_limit_cooldown_sec = 45.0

        if start_immediately:
            QTimer.singleShot(250, self._start_listening)

    def _start_listening(self) -> None:
        if not self.enabled or self._closing or self._busy_reply:
            return
        if self.worker is not None:
            return
        self.status_changed.emit("VOICE • LISTENING")
        self._discard_recording = False
        self.worker = VoiceWorker()
        self.worker.heard.connect(self._heard)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    @staticmethod
    def _norm(text: str) -> str:
        return " ".join(text.lower().replace("-", " ").replace("_", " ").split())

    def _command_reply(self, text: str) -> tuple[bool, str]:
        if self._norm(text).strip(' .!?') in {'show jarvis', 'restore jarvis', 'open jarvis'}:
            self.canvas.window().restore_from_mini()
            return True, 'JARVIS is open.'
        if self._norm(text).strip(' .!?') in {'minimize jarvis', 'hide jarvis'}:
            self.canvas.window().showMinimized()
            return True, 'JARVIS is listening in the background.'
        if google_maps_intent(text):
            ok = self.canvas.open_google_location()
            return True, "Opening Google Maps inside JARVIS. Use My location and allow access." if ok else "I could not open the map."
        if location_intent(text):
            self.canvas.add_location_window()
            return True, "Opening your location display."
        pc_command = parse_pc_command(text)
        if pc_command:
            ok = self.canvas.windows_controller.voice_command(pc_command)
            return True, pc_command[2] if ok else "I could not complete that Windows command."
        n = self._norm(text)
        command_words = set(n.split())
        def has(*items: str) -> bool:
            return any(x in n for x in items)

        # Wake / greeting.
        if has(
            "hello jarvis", "hey jarvis", "hi jarvis",
            "hello holodesk", "hey holodesk", "hi holodesk",
        ):
            return True, "Hello Alex. JARVIS is online."
        if has("clear memory", "forget conversation", "forget our conversation"):
            self.canvas.ai_client.clear_memory()
            return True, "Conversation memory cleared."
        if has("help", "commands", "what can you do"):
            return True, "I can control Windows, build complete projects, and edit the last app with backups."
        if has("what is your name", "who are you"):
            return True, "I am JARVIS v0.1, your local Windows assistant."
        if "time" in command_words or has("what time is it"):
            return True, f"The time is {datetime.now().strftime('%H:%M')}."
        if project_generation_intent(n):
            ok = self.canvas.execute_command(text, silent=True)
            if ok:
                return True, "I am generating a random app." if random_app_intent(n) else "I am generating the app."
            return True, "I could not start the app generator."
        if project_edit_intent(n) or project_followup_intent(n):
            ok = self.canvas.execute_command(text, silent=True)
            if ok:
                return True, "I am preparing the code changes for your last project."
            return True, "I could not open the coding agent."

        mappings = [
            (("open chrome",), "Chrome is open."),
            (("open notepad", "notepad"), "Notepad is open."),
            (("open calculator", "open calc", "calc", "calculator"), "Calculator is open."),
            (("open windows browser", "windows browser", "open default browser", "default browser"), "Windows browser is open."),
            (("open browser", "browser"), "JARVIS browser is open."),
            (("open ai", "ai assistant"), "AI Assistant is open."),
            (("world map", "digital twin", "my world"), "World Map is open."),
            (("future self", "future simulator", "simulate future"), "Future Self simulator is open."),
            (("zip builder", "make zip", "build zip", "create zip", "package files"), "ZIP Builder is open."),
            (("generate a random app", "generate random app", "make a random app", "make random app", "create a random app", "create random app"), "I am generating a random app."),
            (("mission builder", "build project", "create project", "make project", "generate app", "build app", "create app"), "Mission Builder is open."),
            (("self edit", "self editor", "edit yourself", "change yourself"), "Self Edit Center is open."),
            (("windows manager", "window manager"), "Window Manager is open."),
            (("notes", "note"), "Notes are open."),
            (("calendar",), "Calendar is open."),
            (("weather",), "Weather is open."),
            (("clock",), "Clock is open."),
            (("video",), "Video is open."),
            (("music",), "Music is open."),
            (("phone",), "Phone window is open."),
            (("air menu",), "Air Menu is open."),
            (("close window",), "Window closed."),
            (("maximize",), "Window maximized."),
            (("minimize",), "Window minimized."),
            (("restore",), "Window restored."),
            (("snap left",), "Window moved left."),
            (("snap right",), "Window moved right."),
        ]
        for phrases, reply in mappings:
            if has(*phrases):
                ok = self.canvas.execute_command(text, silent=True)
                if ok:
                    return True, reply
                return True, "I could not run that command."
        return False, ""

    def _heard(self, text: str) -> None:
        if not self.enabled or self._closing or self._discard_recording:
            return
        clean = text.strip()
        if not clean:
            return
        screen = getattr(self, 'screen_agent', None)
        if self._norm(clean).strip(' .!?') in {'stop screen sharing', 'stop screen control', 'screen off'}:
            if screen:
                screen.granted = False
                screen.disable()
            self._speak('Screen access is off.')
            return
        if screen and screen.dialog is not None:
            return

        now = time.monotonic()
        norm = self._norm(clean)

        # Ignore the same recognition result for a few seconds. This prevents
        # one spoken sentence from being submitted to the API multiple times.
        if norm and norm == self._last_heard_norm and (now - self._last_heard_at) < self._duplicate_window_sec:
            self.status_changed.emit("VOICE • DUPLICATE IGNORED")
            return

        # Ignore HoloDesk hearing its own TTS immediately after speaking.
        if norm and self._last_spoken_norm and (now - self._last_spoken_at) < self._self_echo_window_sec:
            if norm == self._last_spoken_norm or norm in self._last_spoken_norm or self._last_spoken_norm in norm:
                self.status_changed.emit("VOICE • SELF-ECHO IGNORED")
                return

        self._last_heard_norm = norm
        self._last_heard_at = now
        self._last_user_language = choose_language(clean)
        self.status_changed.emit(f"VOICE • HEARD: {clean[:64]}")
        try:
            reactor = getattr(self.canvas, "reactor_console", None)
            if reactor is not None and hasattr(reactor, "log"):
                reactor.log("HEARD", clean)
        except Exception:
            pass

        visual_request = self._norm(clean).startswith(('click ', 'double click ', 'type ', 'read the screen', 'what is on my screen', 'what do you see'))
        if screen and screen.active and visual_request and screen.submit(clean):
            return
        handled, reply = self._command_reply(clean)
        if handled:
            self._speak(reply)
            return

        # If the API recently returned 429, do not keep retrying every time the
        # microphone produces a result.
        if now < self._ai_cooldown_until:
            remaining = max(1, int(self._ai_cooldown_until - now))
            self.status_changed.emit(f"AI • COOLDOWN {remaining}s")
            return

        if self.ai_worker is not None and self.ai_worker.isRunning():
            self.status_changed.emit("AI • BUSY")
            return

        if screen and screen.submit(clean):
            return

        # Unknown speech is treated as a question for the HoloDesk AI assistant.
        self._busy_reply = True
        self.status_changed.emit("AI • THINKING")
        self.ai_worker = VoiceAIWorker(self.canvas.ai_client, clean)
        self.ai_worker.answered.connect(self._ai_answered)
        self.ai_worker.finished.connect(self._ai_finished)
        self.ai_worker.start()

    def _ai_answered(self, answer: str) -> None:
        if not self.enabled or self._closing:
            self._busy_reply = False
            return
        answer = (answer or "").strip()
        if not answer:
            answer = "I could not find an answer."

        lowered = answer.lower()
        if "http error 429" in lowered or "too many requests" in lowered or "rate_limit" in lowered or "insufficient_quota" in lowered:
            self._ai_cooldown_until = time.monotonic() + self._rate_limit_cooldown_sec
            self.status_changed.emit(f"AI • RATE LIMIT • WAIT {int(self._rate_limit_cooldown_sec)}s")
            self._speak("The request limit was reached. Wait a little, then try again.")
            return

        if "ai connection error" in lowered or "http " in lowered:
            self.status_changed.emit(f"AI • ERROR: {answer[:90]}")
            self._speak("I could not connect to Gemini. Try again in a moment.")
            return

        self.status_changed.emit(f"AI • ANSWER: {answer[:64]}")
        self._speak(answer)

    def _ai_finished(self) -> None:
        worker = self.ai_worker
        self.ai_worker = None
        if worker is not None:
            worker.deleteLater()

    def _speak(self, text: str) -> None:
        if self._closing:
            return
        if self.speaker is not None:
            self._pending_spoken = text
            return
        self._busy_reply = True
        self._last_spoken_norm = self._norm(text)
        self._last_spoken_at = time.monotonic()
        self.status_changed.emit(f"JARVIS • SPEAKING: {text[:64]}")
        self.speaker = SpeechWorker(text)
        self.speaker.engine_used.connect(lambda engine: self.status_changed.emit(f"VOICE ENGINE • {engine}"))
        self.speaker.failed.connect(lambda e: self.status_changed.emit(f"TTS ERROR • {e[:90]}"))
        self.speaker.finished_speaking.connect(self._speech_finished)
        self.speaker.start()

    def _speech_finished(self) -> None:
        speaker = self.speaker
        self.speaker = None
        if speaker is not None:
            speaker.deleteLater()
        self._busy_reply = False
        if self.enabled and not self._closing:
            if self._pending_spoken:
                text, self._pending_spoken = self._pending_spoken, ''
                self._speak(text)
                return
            QTimer.singleShot(450, self._start_listening)

    def _failed(self, error: str) -> None:
        if not self.enabled or self._closing:
            return
        lowered = (error or "").lower()
        quiet_cases = (
            "no speech recognized",
            "no hy-am speech recognized",
            "no en-us speech recognized",
            "unknownvalue",
        )
        if any(token in lowered for token in quiet_cases):
            self._last_error = ""
            self.status_changed.emit("VOICE • LISTENING")
            return
        self._last_error = error
        self.status_changed.emit(f"VOICE ERROR • {error[:120]}")

    def _finished(self) -> None:
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        if self.enabled and not self._closing and not self._busy_reply:
            QTimer.singleShot(self._restart_delay_ms, self._start_listening)

    def stop(self) -> None:
        self.enabled = False
        self._closing = True
        self.status_changed.emit("VOICE • OFF")

    def set_listening_enabled(self, enabled: bool) -> None:
        if self._closing:
            return
        self.enabled = enabled
        if not enabled and self.worker is not None and self.worker.isRunning():
            self._discard_recording = True
        if not enabled:
            self._pending_spoken = ''
        self.status_changed.emit('VOICE READY' if enabled else 'VOICE PAUSED')
        if enabled:
            self._start_listening()


class CompanionState:
    def __init__(self):
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.latest_camera_jpeg: Optional[bytes] = None
        self.lock = threading.Lock()
        self.token = f"{random.randint(100000, 999999)}"


COMPANION_HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>HoloDesk Companion</title><style>
body{margin:0;background:#061019;color:#dffaff;font-family:Arial,sans-serif;overflow:hidden}header{padding:14px 16px;border-bottom:1px solid #237a95;background:#0b1e2a}h2{margin:0;font-size:19px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:12px}button{padding:14px;border:1px solid #36a9c9;border-radius:12px;background:#12394b;color:#eaffff;font-weight:700}#pad{height:42vh;margin:12px;border:1px solid #36a9c9;border-radius:18px;background:radial-gradient(circle,#123849,#081923);touch-action:none;display:flex;align-items:center;justify-content:center;color:#68aabd}.cam{padding:12px}video{width:100%;max-height:22vh;border-radius:12px;background:#000}.small{font-size:12px;color:#83aeb9}</style></head>
<body><header><h2>HoloDesk Companion</h2><div class="small">Touchpad • Remote • Phone camera</div></header>
<div id="pad">TOUCHPAD</div><div class="grid">
<button onclick="sendCmd('click')">Click</button><button onclick="sendCmd('air_menu')">Air Menu</button>
<button onclick="sendCmd('browser')">Browser</button><button onclick="sendCmd('ai')">AI Assistant</button>
<button onclick="sendCmd('maximize')">Maximize</button><button onclick="sendCmd('close_window')">Close Window</button>
<button onclick="sendCmd('save_workspace')">Save Workspace</button><button onclick="sendCmd('next_monitor')">Next Monitor</button>
</div><div class="cam"><video id="video" autoplay muted playsinline></video><button style="width:100%;margin-top:8px" onclick="startCamera()">Start phone camera</button><input id="photo" type="file" accept="image/*" capture="environment" style="width:100%;margin-top:8px" onchange="uploadPhoto(this.files[0])"></div>
<script>
const token=new URLSearchParams(location.search).get('token')||'';
function post(path,data){fetch(path+'?token='+encodeURIComponent(token),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}).catch(()=>{});}
function sendCmd(command){post('/event',{type:'command',command});}
const pad=document.getElementById('pad');let last=null;
pad.addEventListener('pointerdown',e=>{last={x:e.clientX,y:e.clientY};pad.setPointerCapture(e.pointerId)});
pad.addEventListener('pointermove',e=>{if(!last)return;let dx=e.clientX-last.x,dy=e.clientY-last.y;last={x:e.clientX,y:e.clientY};post('/event',{type:'move',dx,dy});});
pad.addEventListener('pointerup',()=>last=null);pad.addEventListener('dblclick',()=>sendCmd('click'));
async function startCamera(){try{const stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'},audio:false});const v=document.getElementById('video');v.srcObject=stream;const c=document.createElement('canvas');setInterval(()=>{if(!v.videoWidth)return;c.width=320;c.height=240;c.getContext('2d').drawImage(v,0,0,320,240);c.toBlob(b=>{if(b)fetch('/camera?token='+encodeURIComponent(token),{method:'POST',body:b})},'image/jpeg',.55)},700)}catch(e){alert('Live camera needs browser permission/secure context. Use the camera file control below as a fallback.')}}
function uploadPhoto(file){if(file)fetch('/camera?token='+encodeURIComponent(token),{method:'POST',body:file}).catch(()=>{});}
</script></body></html>'''


class CompanionServer:
    """Phase 9: local mobile web companion (touchpad, remote and camera stream)."""

    def __init__(self, state: CompanionState):
        self.state = state
        self.server: Optional[ThreadingHTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.port = 0

    @property
    def running(self) -> bool:
        return self.server is not None

    def start(self, port: int) -> tuple[bool, str]:
        if self.running:
            return True, self.url()
        state = self.state

        class Handler(BaseHTTPRequestHandler):
            def _authorized(self) -> bool:
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                return query.get("token", [""])[0] == state.token

            def _send(self, status: int, data: bytes, content_type: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:
                path = urllib.parse.urlparse(self.path).path
                if path == "/":
                    self._send(200, COMPANION_HTML.encode("utf-8"), "text/html; charset=utf-8")
                elif path == "/camera.jpg" and self._authorized():
                    with state.lock:
                        data = state.latest_camera_jpeg
                    if data:
                        self._send(200, data, "image/jpeg")
                    else:
                        self._send(404, b"No frame", "text/plain")
                else:
                    self._send(404, b"Not found", "text/plain")

            def do_POST(self) -> None:
                if not self._authorized():
                    self._send(403, b"Forbidden", "text/plain")
                    return
                path = urllib.parse.urlparse(self.path).path
                length = safe_int(self.headers.get("Content-Length"), 0)
                body = self.rfile.read(min(length, 2_000_000))
                if path == "/event":
                    try:
                        payload = json.loads(body.decode("utf-8"))
                        state.events.put(payload)
                        self._send(200, b"OK", "text/plain")
                    except Exception:
                        self._send(400, b"Bad JSON", "text/plain")
                elif path == "/camera":
                    with state.lock:
                        state.latest_camera_jpeg = body
                    state.events.put({"type": "camera"})
                    self._send(200, b"OK", "text/plain")
                else:
                    self._send(404, b"Not found", "text/plain")

            def log_message(self, format: str, *args: Any) -> None:
                return

        try:
            self.server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
            self.port = self.server.server_address[1]
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            return True, self.url()
        except Exception as exc:
            self.server = None
            return False, str(exc)

    def url(self) -> str:
        return f"http://{local_ip()}:{self.port}/?token={self.state.token}"

    def stop(self) -> None:
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
        self.server = None
        self.thread = None


class ImageView(QLabel):
    def __init__(self, path: str = ""):
        super().__init__()
        self.path = path
        self.original = QPixmap(path) if path else QPixmap()
        self.angle = 0
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background: rgba(4, 8, 14, 230); color:#9FC9D5;")
        self.update_pixmap()

    def rotate_by(self, degrees: int) -> None:
        self.angle = (self.angle + degrees) % 360
        self.update_pixmap()

    def update_pixmap(self) -> None:
        if self.original.isNull():
            self.setText("Image unavailable")
            return
        rotated = self.original.transformed(QTransform().rotate(self.angle), Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(rotated.scaled(
            max(100, self.width() - 16), max(80, self.height() - 16),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def resizeEvent(self, event) -> None:
        self.update_pixmap()
        super().resizeEvent(event)


class ResizeHandle(QFrame):
    def __init__(self, owner: "VirtualWindow"):
        super().__init__(owner)
        self.owner = owner
        self.dragging = False
        self.start_global = QPoint()
        self.start_size = QSize()
        self.setFixedSize(18, 18)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setStyleSheet("background: rgba(104,225,255,120); border-bottom-right-radius:8px;")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.start_global = event.globalPosition().toPoint()
            self.start_size = self.owner.size()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self.dragging:
            delta = event.globalPosition().toPoint() - self.start_global
            self.owner.resize(
                max(self.owner.minimumWidth(), self.start_size.width() + delta.x()),
                max(self.owner.minimumHeight(), self.start_size.height() + delta.y()),
            )
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self.dragging = False
        event.accept()


class VirtualWindow(QFrame):
    def __init__(
        self,
        canvas: "HoloCanvas",
        title: str,
        content_widget: QWidget,
        width: int = 390,
        height: int = 270,
        content_type: str = "generic",
        content_data: Optional[dict[str, Any]] = None,
    ):
        super().__init__(canvas)
        self.canvas = canvas
        self.content_widget = content_widget
        self.content_type = content_type
        self.content_data = content_data or {}
        self.dragging = False
        self.drag_offset = QPoint()
        self.normal_geometry = QRect(80, 100, width, height)
        self.maximized = False
        self.minimized = False
        self.rotation_angle = 0
        self.window_id = f"w-{int(time.time() * 1000)}-{random.randint(100,999)}"
        self.setObjectName("virtualWindow")
        self.setMinimumSize(250, 150)
        self.resize(width, height)
        self._apply_style()

        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(34)
        glow.setOffset(0, 4)
        glow.setColor(QColor(40, 205, 255, 105))
        self.setGraphicsEffect(glow)

        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)
        root.setSpacing(0)

        self.titlebar = QFrame()
        self.titlebar.setFixedHeight(38)
        self.titlebar.setStyleSheet("""
            QFrame { background: rgba(13, 43, 59, 238); border-top-left-radius:15px; border-top-right-radius:15px; }
            QPushButton { color:#DDF9FF; background:transparent; border:none; border-radius:7px; font-weight:700; }
            QPushButton:hover { background:rgba(255,255,255,35); }
        """)
        title_layout = QHBoxLayout(self.titlebar)
        title_layout.setContentsMargins(11, 0, 6, 0)
        title_layout.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color:#EAFBFF;font-weight:700;")
        self.state_label = QLabel("")
        self.state_label.setStyleSheet("color:#72CFE8;font-size:10px;")
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.state_label)
        title_layout.addStretch()

        for label, callback in [
            ("—", self.minimize_window),
            ("□", self.toggle_maximize),
            ("×", self.close),
        ]:
            button = QPushButton(label)
            button.setFixedSize(27, 26)
            button.clicked.connect(callback)
            title_layout.addWidget(button)

        root.addWidget(self.titlebar)
        root.addWidget(content_widget, 1)
        self.resize_handle = ResizeHandle(self)
        self.resize_handle.raise_()
        self.show()
        self.fade_in()

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QFrame#virtualWindow {
                background: rgba(11, 18, 29, 244);
                border: 1px solid rgba(86, 224, 255, 190);
                border-radius: 16px;
            }
        """)

    def fade_in(self) -> None:
        self.setWindowOpacity(0.3)
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(260)
        animation.setStartValue(0.3)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._fade_animation = animation

    def title(self) -> str:
        return self.title_label.text()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() <= self.titlebar.height():
            self.raise_()
            self.canvas.active_window = self
            self.dragging = True
            self.drag_offset = event.position().toPoint()
            if self.maximized:
                self.restore_window()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.position().y() <= self.titlebar.height():
            self.toggle_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.dragging:
            global_point = event.globalPosition().toPoint()
            parent_point = self.canvas.mapFromGlobal(global_point) - self.drag_offset
            self.move_clamped(parent_point.x(), parent_point.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.dragging = False
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event) -> None:
        self.resize_handle.move(self.width() - 19, self.height() - 19)
        super().resizeEvent(event)

    def move_clamped(self, x: int, y: int) -> None:
        self.move(
            int(clamp(x, 0, max(0, self.canvas.width() - self.width()))),
            int(clamp(y, 72, max(72, self.canvas.height() - self.height()))),
        )

    def minimize_window(self) -> None:
        if self.minimized:
            self.restore_window()
            return
        self.normal_geometry = self.geometry()
        self.minimized = True
        self.maximized = False
        self.content_widget.hide()
        self.setFixedHeight(40)
        self.state_label.setText("MIN")

    def toggle_maximize(self) -> None:
        if self.maximized:
            self.restore_window()
        else:
            self.maximize_window()

    def maximize_window(self) -> None:
        if not self.maximized:
            self.normal_geometry = self.geometry()
        self.setMinimumSize(250, 150)
        self.setMaximumSize(16777215, 16777215)
        self.content_widget.show()
        self.minimized = False
        self.maximized = True
        self.setGeometry(8, 78, max(300, self.canvas.width() - 16), max(200, self.canvas.height() - 86))
        self.state_label.setText("MAX")
        self.raise_()
        self.canvas.active_window = self

    def restore_window(self) -> None:
        self.setMinimumSize(250, 150)
        self.setMaximumSize(16777215, 16777215)
        self.content_widget.show()
        self.minimized = False
        self.maximized = False
        self.setGeometry(self.normal_geometry)
        self.state_label.setText("")
        self.move_clamped(self.x(), self.y())

    def snap_left(self) -> None:
        self.normal_geometry = self.geometry()
        self.setGeometry(8, 78, max(280, self.canvas.width() // 2 - 12), max(200, self.canvas.height() - 86))
        self.minimized = False
        self.maximized = False
        self.content_widget.show()
        self.state_label.setText("LEFT")

    def snap_right(self) -> None:
        width = max(280, self.canvas.width() // 2 - 12)
        self.normal_geometry = self.geometry()
        self.setGeometry(self.canvas.width() - width - 8, 78, width, max(200, self.canvas.height() - 86))
        self.minimized = False
        self.maximized = False
        self.content_widget.show()
        self.state_label.setText("RIGHT")

    def rotate_by(self, degrees: int) -> None:
        self.rotation_angle = (self.rotation_angle + degrees) % 360
        if isinstance(self.content_widget, ImageView):
            self.content_widget.rotate_by(degrees)
        self.state_label.setText(f"{self.rotation_angle}°")
        effect = self.graphicsEffect()
        if isinstance(effect, QGraphicsDropShadowEffect):
            rad = math.radians(self.rotation_angle)
            effect.setOffset(math.cos(rad) * 7, math.sin(rad) * 7)

    def serialize(self) -> dict[str, Any]:
        geometry = self.normal_geometry if self.minimized else self.geometry()
        data = dict(self.content_data)
        if self.content_type in {"text", "notes"} and isinstance(self.content_widget, QTextEdit):
            data["text"] = self.content_widget.toPlainText()
        return {
            "title": self.title(),
            "type": self.content_type,
            "data": data,
            "geometry": [geometry.x(), geometry.y(), geometry.width(), geometry.height()],
            "rotation": self.rotation_angle,
            "maximized": self.maximized,
        }

    def closeEvent(self, event) -> None:
        self.canvas.unregister_window(self)
        super().closeEvent(event)


class CalculatorWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.display = QLineEdit()
        self.display.setPlaceholderText("2 + 2 * 5")
        self.display.returnPressed.connect(self.calculate)
        layout.addWidget(self.display)
        grid = QGridLayout()
        buttons = ["7", "8", "9", "/", "4", "5", "6", "*", "1", "2", "3", "-", "0", ".", "(", ")", "C", "⌫", "+", "="]
        for index, text in enumerate(buttons):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, t=text: self.press(t))
            grid.addWidget(button, index // 4, index % 4)
        layout.addLayout(grid)
        self.setStyleSheet(button_style() + input_style())

    def press(self, text: str) -> None:
        if text == "C":
            self.display.clear()
        elif text == "⌫":
            self.display.setText(self.display.text()[:-1])
        elif text == "=":
            self.calculate()
        else:
            self.display.insert(text)

    @staticmethod
    def safe_eval(expression: str) -> float:
        allowed_binops = {
            ast.Add: lambda a, b: a + b,
            ast.Sub: lambda a, b: a - b,
            ast.Mult: lambda a, b: a * b,
            ast.Div: lambda a, b: a / b,
            ast.Mod: lambda a, b: a % b,
            ast.Pow: lambda a, b: a ** b,
        }
        allowed_unary = {ast.UAdd: lambda a: a, ast.USub: lambda a: -a}

        def visit(node: ast.AST) -> float:
            if isinstance(node, ast.Expression):
                return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            if isinstance(node, ast.BinOp) and type(node.op) in allowed_binops:
                return allowed_binops[type(node.op)](visit(node.left), visit(node.right))
            if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_unary:
                return allowed_unary[type(node.op)](visit(node.operand))
            raise ValueError("Unsupported expression")

        tree = ast.parse(expression, mode="eval")
        return visit(tree)

    def calculate(self) -> None:
        try:
            result = self.safe_eval(self.display.text())
            self.display.setText(str(int(result)) if result.is_integer() else str(round(result, 10)))
        except Exception:
            self.display.setText("Error")


class ClockWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.clock = QLCDNumber()
        self.clock.setDigitCount(8)
        self.clock.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
        self.clock.setStyleSheet("color:#8BE9FF;background:rgba(4,9,15,220);border:none;")
        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_label.setStyleSheet("color:#CDEFF8;font-size:16px;")
        layout.addWidget(self.clock, 1)
        layout.addWidget(self.date_label)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def refresh(self) -> None:
        now = datetime.now()
        self.clock.display(now.strftime("%H:%M:%S"))
        self.date_label.setText(now.strftime("%A, %d %B %Y"))


class WeatherWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker: Optional[WeatherWorker] = None
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.city = QLineEdit("Yerevan")
        button = QPushButton("Load")
        button.clicked.connect(self.load_weather)
        row.addWidget(self.city, 1)
        row.addWidget(button)
        self.result = QLabel("Enter a city and load current weather.")
        self.result.setWordWrap(True)
        self.result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result.setStyleSheet("color:#DDF7FF;font-size:16px;padding:15px;")
        layout.addLayout(row)
        layout.addWidget(self.result, 1)
        self.setStyleSheet(button_style() + input_style())

    def load_weather(self) -> None:
        city = self.city.text().strip()
        if not city:
            return
        self.result.setText("Loading…")
        self.worker = WeatherWorker(city)
        self.worker.finished_data.connect(self.show_weather)
        self.worker.failed.connect(lambda error: self.result.setText(f"Weather error: {error}"))
        self.worker.start()

    def show_weather(self, data: dict) -> None:
        place = data["place"]
        current = data["current"]
        self.result.setText(
            f"{place.get('name')}, {place.get('country', '')}\n\n"
            f"Temperature: {current.get('temperature_2m', '—')} °C\n"
            f"Feels like: {current.get('apparent_temperature', '—')} °C\n"
            f"Wind: {current.get('wind_speed_10m', '—')} km/h\n"
            f"Weather code: {current.get('weather_code', '—')}"
        )


class BrowserWidget(QWidget):
    def __init__(self, url: str = "https://www.google.com"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        row = QHBoxLayout()
        self.address = QLineEdit(url)
        go = QPushButton("Go")
        back = QPushButton("←")
        forward = QPushButton("→")
        reload_btn = QPushButton("↻")
        row.addWidget(back)
        row.addWidget(forward)
        row.addWidget(reload_btn)
        row.addWidget(self.address, 1)
        row.addWidget(go)
        layout.addLayout(row)
        if WEBENGINE_AVAILABLE:
            self.view = QWebEngineView()
            self.view.setUrl(QUrl(url))
            layout.addWidget(self.view, 1)
            go.clicked.connect(self.navigate)
            self.address.returnPressed.connect(self.navigate)
            back.clicked.connect(self.view.back)
            forward.clicked.connect(self.view.forward)
            reload_btn.clicked.connect(self.view.reload)
            self.view.urlChanged.connect(lambda value: self.address.setText(value.toString()))
        else:
            self.view = QLabel("Qt WebEngine is unavailable. Use Open External Browser.")
            self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.view, 1)
            go.setText("Open External")
            go.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromUserInput(self.address.text())))
            back.setEnabled(False)
            forward.setEnabled(False)
            reload_btn.setEnabled(False)
        self.setStyleSheet(button_style() + input_style())

    def navigate(self) -> None:
        if WEBENGINE_AVAILABLE:
            self.view.setUrl(QUrl.fromUserInput(self.address.text()))


class MediaWidget(QWidget):
    def __init__(self, kind: str = "video"):
        super().__init__()
        self.kind = kind
        self.media_path = ""
        layout = QVBoxLayout(self)
        self.status = QLabel(f"Choose a {kind} file")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("color:#D7F5FC;padding:10px;")
        if MULTIMEDIA_AVAILABLE:
            self.player = QMediaPlayer(self)
            self.audio = QAudioOutput(self)
            self.player.setAudioOutput(self.audio)
            if kind == "video":
                self.video = QVideoWidget()
                self.player.setVideoOutput(self.video)
                layout.addWidget(self.video, 1)
            else:
                self.art = QLabel("♫")
                self.art.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.art.setStyleSheet("font-size:70px;color:#8BE9FF;background:rgba(4,9,15,220);")
                layout.addWidget(self.art, 1)
        else:
            self.player = None
            layout.addWidget(self.status, 1)
        controls = QHBoxLayout()
        open_btn = QPushButton("Open")
        play_btn = QPushButton("Play / Pause")
        stop_btn = QPushButton("Stop")
        open_btn.clicked.connect(self.choose_file)
        play_btn.clicked.connect(self.toggle_play)
        stop_btn.clicked.connect(lambda: self.player.stop() if self.player else None)
        controls.addWidget(open_btn)
        controls.addWidget(play_btn)
        controls.addWidget(stop_btn)
        layout.addWidget(self.status)
        layout.addLayout(controls)
        self.setStyleSheet(button_style())

    def choose_file(self) -> None:
        filters = "Videos (*.mp4 *.mkv *.avi *.mov *.webm)" if self.kind == "video" else "Audio (*.mp3 *.wav *.m4a *.ogg *.flac)"
        path, _ = QFileDialog.getOpenFileName(self, "Choose media", "", filters)
        if not path:
            return
        self.media_path = path
        self.status.setText(Path(path).name)
        if self.player:
            self.player.setSource(QUrl.fromLocalFile(path))
            self.player.play()

    def toggle_play(self) -> None:
        if not self.player:
            self.status.setText("Qt Multimedia is unavailable.")
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()


class AIChatWidget(QWidget):
    def __init__(self, client: AIClient, canvas: "HoloCanvas"):
        super().__init__()
        self.client = client
        self.canvas = canvas
        self.worker: Optional[AIWorker] = None
        self._chat_generation = 0
        self._workers: list[AIWorker] = []
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("JARVIS CHAT"))
        toolbar.addStretch()
        self.new_chat_button = QPushButton("New Chat")
        self.new_chat_button.setToolTip("Start a new conversation")
        self.new_chat_button.clicked.connect(self.new_chat)
        toolbar.addWidget(self.new_chat_button)
        layout.addLayout(toolbar)
        self.chat_status = QLabel("")
        layout.addWidget(self.chat_status)
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.setHtml("<b style='color:#8BE9FF'>JARVIS:</b> HoloDesk assistant online.")
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask AI or type a desktop command…")
        send = QPushButton("Send")
        screen = QPushButton("Screen")
        clip = QPushButton("Clipboard AI")
        clear = QPushButton("Clear Memory")
        send.clicked.connect(self.send_message)
        self.input.returnPressed.connect(self.send_message)
        screen.clicked.connect(self.screen_context)
        clip.clicked.connect(self.clipboard_ai)
        clear.clicked.connect(self.clear_memory)
        row.addWidget(self.input, 1)
        row.addWidget(send)
        row.addWidget(screen)
        row.addWidget(clip)
        row.addWidget(clear)
        layout.addWidget(self.history, 1)
        layout.addLayout(row)
        self.setStyleSheet(button_style() + input_style())

    def append(self, who: str, text: str) -> None:
        color = "#8BE9FF" if who == "JARVIS" else "#FFE08A"
        self.history.append(f"<b style='color:{color}'>{html.escape(who)}:</b> {html.escape(text).replace(chr(10), '<br>')}")

    def new_chat(self) -> None:
        self._chat_generation += 1
        self.client.clear_memory()
        self.history.clear()
        self.input.clear()
        if self.worker is not None and self.worker.isRunning():
            self.chat_status.setText("Finishing previous request...")
        self.input.setFocus()

    def _request(self, message: str, clipboard: bool = False) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        generation = self._chat_generation
        worker = AIWorker(self.client, message)
        self.worker = worker
        self.chat_status.setText("Thinking...")
        self._workers.append(worker)

        def receive(text: str) -> None:
            if generation != self._chat_generation:
                return
            if clipboard:
                self._clipboard_result(text)
            else:
                self.append("JARVIS", text)

        def finished() -> None:
            self._workers.remove(worker)
            worker.deleteLater()
            if self.worker is worker:
                self.worker = None
                self.chat_status.clear()

        worker.finished_text.connect(receive)
        worker.finished.connect(finished)
        worker.start()

    def clear_memory(self) -> None:
        self.new_chat()
        self.append("JARVIS", "Conversation memory cleared.")

    def send_message(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        message = self.input.text().strip()
        if not message:
            return
        self.input.clear()
        self.append("YOU", message)
        if self.canvas.execute_command(message, silent=True):
            self.append("JARVIS", "Command executed.")
            return
        self._request(message)

    def screen_context(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        context = self.canvas.screen_context()
        self.append("SCREEN", context)
        self._request(f"Analyze this desktop context and suggest the next useful action:\n{context}")

    def clipboard_ai(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        text = QApplication.clipboard().text().strip()
        if not text:
            self.append("JARVIS", "Clipboard is empty.")
            return
        instruction, ok = QInputDialog.getItem(
            self, "Clipboard AI", "Action", ["Summarize", "Rewrite professionally", "Translate to English", "Extract tasks"], 0, False
        )
        if not ok:
            return
        self.append("YOU", f"{instruction}: [clipboard]")
        self._request(f"{instruction}:\n\n{text}", clipboard=True)

    def _clipboard_result(self, text: str) -> None:
        QApplication.clipboard().setText(text)
        self.append("JARVIS", text + "\nCopied to clipboard.")


class WindowsManagerWidget(QWidget):
    def __init__(self, controller: WindowsController):
        super().__init__()
        self.controller = controller
        self.rows: list[dict[str, Any]] = []
        layout = QVBoxLayout(self)
        self.status = QLabel()
        self.status.setStyleSheet("color:#9ED7E5;")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Application", "Window", "PID", "State"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        controls = QGridLayout()
        actions = [
            ("Refresh", self.refresh), ("Bring Front", lambda: self.perform("front")),
            ("Minimize", lambda: self.perform("minimize")), ("Maximize", lambda: self.perform("maximize")),
            ("Restore", lambda: self.perform("restore")), ("Close", lambda: self.perform("close")),
            ("Snap Left", lambda: self.perform("snap_left")), ("Snap Right", lambda: self.perform("snap_right")),
        ]
        for index, (label, callback) in enumerate(actions):
            button = QPushButton(label)
            button.clicked.connect(callback)
            controls.addWidget(button, index // 4, index % 4)
        layout.addWidget(self.status)
        layout.addWidget(self.table, 1)
        layout.addLayout(controls)
        self.setStyleSheet(button_style() + "QTableWidget{background:#08131D;color:#DDF7FF;gridline-color:#1D5365;}QHeaderView::section{background:#123241;color:#DDF7FF;padding:6px;}")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1500)
        self.refresh()

    def refresh(self) -> None:
        if not self.controller.available:
            self.status.setText("Real Windows integration is available only on Windows with pywin32 installed.")
            self.table.setRowCount(0)
            return
        selected_hwnd = self.selected_hwnd()
        self.rows = self.controller.list_windows()
        self.table.setRowCount(len(self.rows))
        selected_row = -1
        for row_index, row in enumerate(self.rows):
            state = "Minimized" if row["minimized"] else "Maximized" if row["maximized"] else "Normal"
            values = [row["process"], row["title"], str(row["pid"]), state]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row["hwnd"])
                self.table.setItem(row_index, column, item)
            if row["hwnd"] == selected_hwnd:
                selected_row = row_index
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        self.status.setText(f"Detected {len(self.rows)} open windows • live refresh every 1.5 sec")

    def selected_hwnd(self) -> int:
        row = self.table.currentRow()
        if row < 0:
            return 0
        item = self.table.item(row, 0)
        return safe_int(item.data(Qt.ItemDataRole.UserRole) if item else 0)

    def perform(self, action: str) -> None:
        hwnd = self.selected_hwnd()
        if not hwnd:
            self.status.setText("Select a window first.")
            return
        ok = self.controller.bring_to_front(hwnd) if action == "front" else self.controller.action(hwnd, action)
        self.status.setText("Action completed." if ok else "Action failed or was blocked by Windows.")
        QTimer.singleShot(250, self.refresh)


class VoiceControlWidget(QWidget):
    def __init__(self, canvas: "HoloCanvas"):
        super().__init__()
        self.canvas = canvas
        self.worker: Optional[VoiceWorker] = None
        self.speaker: Optional[SpeechWorker] = None
        layout = QVBoxLayout(self)
        self.status = QLabel("JARVIS voice is always on. You can also type a command or press Listen manually.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#CDEFF8;padding:8px;")
        self.input = QLineEdit()
        self.input.setPlaceholderText("Example: Hey Jarvis, open Chrome / time / open notepad")
        row = QHBoxLayout()
        run = QPushButton("Run Command")
        mic = QPushButton("Listen")
        test = QPushButton("Test Voice")
        run.clicked.connect(self.run_command)
        mic.clicked.connect(self.listen)
        test.clicked.connect(lambda: self.speak("JARVIS voice test is working."))
        self.input.returnPressed.connect(self.run_command)
        row.addWidget(run)
        row.addWidget(mic)
        row.addWidget(test)
        examples = QLabel(
            "English: Hey Jarvis • Open Chrome • Open Notepad • Open Calculator • Time • Help"
        )
        examples.setWordWrap(True)
        examples.setStyleSheet("color:#7EAFBC;padding:10px;")
        layout.addWidget(self.status)
        layout.addWidget(self.input)
        layout.addLayout(row)
        layout.addWidget(examples)
        layout.addStretch()
        self.setStyleSheet(button_style() + input_style())

    def run_command(self) -> None:
        command = self.input.text().strip()
        if not command:
            return
        ok = self.canvas.execute_command(command)
        if ok:
            reply = "Command executed."
        else:
            reply = self.canvas.ai_client.local_response(command)
        self.status.setText(reply)
        self.speak(reply)

    def listen(self) -> None:
        self.status.setText("Listening for up to 3 seconds...")
        self.worker = VoiceWorker()
        self.worker.heard.connect(self._heard)
        self.worker.failed.connect(lambda error: self.status.setText(f"Voice error: {error}"))
        self.worker.start()

    def _heard(self, text: str) -> None:
        self.input.setText(text)
        self.status.setText(f"Heard: {text}")
        self.run_command()

    def speak(self, text: str) -> None:
        if self.speaker is not None and self.speaker.isRunning():
            self.status.setText("JARVIS is already speaking. Try again in a second.")
            return
        self.speaker = SpeechWorker(text)
        self.speaker.engine_used.connect(lambda engine: self.status.setText(f"Voice engine: {engine}"))
        self.speaker.failed.connect(lambda error: self.status.setText(f"Voice output error: {error}"))
        self.speaker.finished_speaking.connect(self._speech_finished)
        self.speaker.start()

    def _speech_finished(self) -> None:
        speaker = self.speaker
        self.speaker = None
        if speaker is not None:
            speaker.deleteLater()


class PhoneCompanionWidget(QWidget):
    def __init__(self, canvas: "HoloCanvas"):
        super().__init__()
        self.canvas = canvas
        layout = QVBoxLayout(self)
        self.title = QLabel("Use any Android phone browser as a HoloDesk companion.")
        self.title.setWordWrap(True)
        self.url = QLineEdit()
        self.url.setReadOnly(True)
        self.url.setPlaceholderText("Server is stopped")
        row = QHBoxLayout()
        start = QPushButton("Start Companion")
        stop = QPushButton("Stop")
        copy = QPushButton("Copy URL")
        start.clicked.connect(self.start_server)
        stop.clicked.connect(self.stop_server)
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.url.text()))
        row.addWidget(start)
        row.addWidget(stop)
        row.addWidget(copy)
        self.camera = QLabel("Phone camera stream will appear here")
        self.camera.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera.setMinimumHeight(180)
        self.camera.setStyleSheet("background:#03070B;color:#7FA6B0;border:1px solid #195267;")
        layout.addWidget(self.title)
        layout.addWidget(self.url)
        layout.addLayout(row)
        layout.addWidget(self.camera, 1)
        self.setStyleSheet(button_style() + input_style())
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_camera)
        self.refresh_timer.start(700)

    def start_server(self) -> None:
        ok, value = self.canvas.start_companion()
        self.url.setText(value if ok else "")
        self.title.setText("Open this URL on a phone connected to the same Wi-Fi." if ok else f"Could not start: {value}")

    def stop_server(self) -> None:
        self.canvas.stop_companion()
        self.url.clear()
        self.title.setText("Companion server stopped.")

    def refresh_camera(self) -> None:
        with self.canvas.companion_state.lock:
            data = self.canvas.companion_state.latest_camera_jpeg
        if not data:
            return
        pix = QPixmap()
        if pix.loadFromData(data, "JPG"):
            self.camera.setPixmap(pix.scaled(self.camera.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))


class SettingsWidget(QWidget):
    settings_changed = Signal()

    def __init__(self, settings: AppSettings):
        super().__init__()
        self.settings = settings
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("AI endpoint settings. Default: Gemini 3.5 Flash-Lite."))
        self.endpoint = QLineEdit(settings.ai_endpoint)
        self.endpoint.setPlaceholderText(DEFAULT_AI_ENDPOINT)
        self.model = QLineEdit(settings.ai_model)
        self.model.setPlaceholderText(DEFAULT_AI_MODEL)
        self.key = QLineEdit(settings.ai_key)
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("Optional API key. Prefer GEMINI_API_KEY environment variable.")
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(settings.phone_port)
        form = QGridLayout()
        form.addWidget(QLabel("Endpoint"), 0, 0); form.addWidget(self.endpoint, 0, 1)
        form.addWidget(QLabel("Model"), 1, 0); form.addWidget(self.model, 1, 1)
        form.addWidget(QLabel("API key"), 2, 0); form.addWidget(self.key, 2, 1)
        form.addWidget(QLabel("Phone port"), 3, 0); form.addWidget(self.port, 3, 1)
        save = QPushButton("Save Settings")
        gemini = QPushButton("Use Gemini 3.5 Lite")
        save.clicked.connect(self.save)
        gemini.clicked.connect(self.use_gemini_defaults)
        note = QLabel("Leave Endpoint/Model empty to use Gemini defaults. Leave API key empty to read GEMINI_API_KEY from Windows. If no key exists, JARVIS uses local fallback mode.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#7FAAB5;")
        layout.addLayout(form)
        layout.addWidget(gemini)
        layout.addWidget(save)
        layout.addWidget(note)
        layout.addStretch()
        self.setStyleSheet(button_style() + input_style())

    def save(self) -> None:
        endpoint = self.endpoint.text().strip()
        if "generativelanguage.googleapis.com" in endpoint:
            endpoint = AIClient._normalize_gemini_endpoint(endpoint)
        self.settings.ai_endpoint = endpoint
        self.settings.ai_model = self.model.text().strip()
        self.settings.ai_key = self.key.text().strip()
        self.settings.phone_port = self.port.value()
        self.settings.save()
        self.settings_changed.emit()
        QMessageBox.information(self, APP_NAME, "Settings saved locally.")

    def use_gemini_defaults(self) -> None:
        self.endpoint.setText(DEFAULT_AI_ENDPOINT)
        self.model.setText(DEFAULT_AI_MODEL)
        self.key.clear()


class WorldMapWidget(QWidget):
    """Personal operating map: projects, goals, devices, ideas and skills."""

    DEFAULTS = {
        "projects": "JARVIS v0.1\nEDITH glasses\nHoloDesk",
        "goals": "Make JARVIS useful every day\nImprove English voice speed\nAdd screen awareness",
        "devices": "Windows PC\nMicrophone\nCamera",
        "ideas": "Mission Control\nFuture Self simulator\nCreator Lab",
        "skills": "Python\nAI assistants\nUI design\nWindows automation",
    }

    def __init__(self):
        super().__init__()
        self.editors: dict[str, QTextEdit] = {}
        layout = QVBoxLayout(self)
        title = QLabel("JARVIS WORLD MAP")
        title.setStyleSheet("color:#8BE9FF;font-size:18px;font-weight:800;padding:4px;")
        layout.addWidget(title)
        subtitle = QLabel("This is not chat memory. It is your local control map: projects, goals, devices, ideas and skills.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#86B9C8;padding:0 4px 8px 4px;")
        layout.addWidget(subtitle)

        tabs = QTabWidget()
        for key, label in [
            ("projects", "Projects"),
            ("goals", "Goals"),
            ("devices", "Devices"),
            ("ideas", "Ideas"),
            ("skills", "Skills"),
        ]:
            editor = QTextEdit()
            editor.setPlaceholderText(f"Write your {label.lower()} here, one per line.")
            editor.setStyleSheet(input_style() + "QTextEdit{font-size:13px;padding:10px;}")
            self.editors[key] = editor
            tabs.addTab(editor, label)
        layout.addWidget(tabs, 1)

        row = QHBoxLayout()
        save = QPushButton("Save Map")
        reset = QPushButton("Load Starter Map")
        copy = QPushButton("Copy Summary")
        save.clicked.connect(self.save)
        reset.clicked.connect(self.load_defaults)
        copy.clicked.connect(self.copy_summary)
        row.addWidget(save)
        row.addWidget(reset)
        row.addWidget(copy)
        layout.addLayout(row)
        self.status = QLabel("")
        self.status.setStyleSheet("color:#7FCDE2;padding:4px;")
        layout.addWidget(self.status)
        self.setStyleSheet(button_style() + input_style() + "QTabWidget::pane{border:1px solid #28758E;} QTabBar::tab{color:#DDF7FF;background:#102A38;padding:8px;}")
        self.load()

    def load(self) -> None:
        data = self.DEFAULTS.copy()
        if WORLD_MAP_PATH.exists():
            try:
                loaded = json.loads(WORLD_MAP_PATH.read_text(encoding="utf-8"))
                data.update({key: str(value) for key, value in loaded.items()})
            except Exception:
                pass
        for key, editor in self.editors.items():
            editor.setPlainText(data.get(key, ""))

    def save(self) -> None:
        data = {key: editor.toPlainText().strip() for key, editor in self.editors.items()}
        WORLD_MAP_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status.setText(f"Saved locally: {WORLD_MAP_PATH}")

    def load_defaults(self) -> None:
        for key, value in self.DEFAULTS.items():
            self.editors[key].setPlainText(value)
        self.status.setText("Starter map loaded. Press Save Map to keep it.")

    def copy_summary(self) -> None:
        parts = []
        for key, editor in self.editors.items():
            parts.append(f"{key.upper()}:\n{editor.toPlainText().strip()}")
        QApplication.clipboard().setText("\n\n".join(parts))
        self.status.setText("World Map summary copied.")


class FutureSelfWidget(QWidget):
    """Simulates a simple future timeline from one goal and one daily action."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("FUTURE SELF SIMULATOR")
        title.setStyleSheet("color:#8BE9FF;font-size:18px;font-weight:800;padding:4px;")
        layout.addWidget(title)

        form = QGridLayout()
        self.goal = QLineEdit("Build a useful JARVIS assistant")
        self.daily = QLineEdit("Work on it for 45 minutes")
        self.days = QSpinBox()
        self.days.setRange(1, 365)
        self.days.setValue(30)
        form.addWidget(QLabel("Goal"), 0, 0); form.addWidget(self.goal, 0, 1)
        form.addWidget(QLabel("Daily action"), 1, 0); form.addWidget(self.daily, 1, 1)
        form.addWidget(QLabel("Days"), 2, 0); form.addWidget(self.days, 2, 1)
        layout.addLayout(form)

        row = QHBoxLayout()
        simulate = QPushButton("Simulate")
        seven = QPushButton("7 Days")
        thirty = QPushButton("30 Days")
        ninety = QPushButton("90 Days")
        simulate.clicked.connect(self.simulate)
        seven.clicked.connect(lambda: self.set_days_and_simulate(7))
        thirty.clicked.connect(lambda: self.set_days_and_simulate(30))
        ninety.clicked.connect(lambda: self.set_days_and_simulate(90))
        for button in (simulate, seven, thirty, ninety):
            row.addWidget(button)
        layout.addLayout(row)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setStyleSheet(input_style() + "QTextEdit{font-size:13px;padding:10px;}")
        layout.addWidget(self.output, 1)

        copy = QPushButton("Copy Timeline")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.output.toPlainText()))
        layout.addWidget(copy)
        self.setStyleSheet(button_style() + input_style() + "QLabel{color:#CFF7FF;}")
        self.simulate()

    def set_days_and_simulate(self, days: int) -> None:
        self.days.setValue(days)
        self.simulate()

    def simulate(self) -> None:
        goal = self.goal.text().strip() or "your goal"
        daily = self.daily.text().strip() or "one focused action"
        days = self.days.value()
        total_hours = round(days * 0.75, 1)
        checkpoints = sorted({1, max(1, days // 4), max(1, days // 2), max(1, days * 3 // 4), days})
        lines = [
            f"Goal: {goal}",
            f"Daily action: {daily}",
            f"Time horizon: {days} days",
            "",
            "Future timeline:",
        ]
        for day in checkpoints:
            progress = int(day / days * 100)
            if day == 1:
                result = "You start the loop and remove the first friction."
            elif day < days // 2:
                result = "The habit becomes easier and the project gets visible structure."
            elif day < days:
                result = "You now have enough progress to test, show, or improve the system."
            else:
                result = "Your future self has a real version, not only an idea."
            lines.append(f"Day {day}: {progress}% - {result}")
        lines.extend([
            "",
            f"Estimated focused time: about {total_hours} hours.",
            "Risk: skipping days silently.",
            "Rule: if you miss a day, do a 10-minute recovery version the next day.",
            "Next action: start one small step now.",
        ])
        self.output.setPlainText("\n".join(lines))


class MissionBuilderWidget(QWidget):
    """Plans a local project, previews it, then writes and packages it with approval."""

    def __init__(self, client: AIClient, initial_request: str = "", auto_start: bool = False):
        super().__init__()
        self.client = client
        self.worker: Optional[ProjectPlanWorker] = None
        self.plan: Optional[dict[str, Any]] = None
        self.last_project: Optional[Path] = None
        self.last_run_file: Optional[Path] = None

        layout = QVBoxLayout(self)
        title = QLabel("JARVIS MISSION BUILDER")
        title.setStyleSheet("color:#8BE9FF;font-size:18px;font-weight:800;padding:4px;")
        note = QLabel(
            "Describe a project. JARVIS prepares the files, shows the plan, asks for approval, "
            "then creates the folder and ZIP. Generated projects are never run automatically."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#91C7D4;")
        layout.addWidget(title)
        layout.addWidget(note)

        self.request = QTextEdit()
        self.request.setPlaceholderText(
            "Example: Build a Windows expense tracker with a simple GUI, local JSON storage and a README."
        )
        self.request.setMaximumHeight(105)
        self.request.setPlainText(initial_request.strip())
        layout.addWidget(self.request)

        form = QGridLayout()
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("Generated from the plan")
        self.output_folder = QLineEdit(str(PROJECTS_PATH))
        choose = QPushButton("Choose Folder")
        choose.clicked.connect(self.choose_output_folder)
        form.addWidget(QLabel("Project name"), 0, 0)
        form.addWidget(self.project_name, 0, 1, 1, 2)
        form.addWidget(QLabel("Save in"), 1, 0)
        form.addWidget(self.output_folder, 1, 1)
        form.addWidget(choose, 1, 2)
        layout.addLayout(form)

        controls = QHBoxLayout()
        self.plan_button = QPushButton("Create Plan")
        self.build_button = QPushButton("Approve, Build and ZIP")
        self.run_button = QPushButton("Run App")
        self.open_button = QPushButton("Open Folder")
        self.build_button.setEnabled(False)
        self.run_button.setEnabled(False)
        self.open_button.setEnabled(False)
        self.plan_button.clicked.connect(self.create_plan)
        self.build_button.clicked.connect(self.build_project)
        self.run_button.clicked.connect(self.run_result)
        self.open_button.clicked.connect(self.open_result)
        controls.addWidget(self.plan_button)
        controls.addWidget(self.build_button)
        controls.addWidget(self.run_button)
        controls.addWidget(self.open_button)
        layout.addLayout(controls)

        self.status = QLabel("Ready. Gemini creates the full plan when connected; offline mode creates a starter project.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#72D7F2;padding:4px;")
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("The project plan and file list will appear here.")
        layout.addWidget(self.status)
        layout.addWidget(self.preview, 1)
        self.setStyleSheet(button_style() + input_style() + "QLabel{color:#CFF7FF;}")
        if initial_request.strip() and auto_start:
            QTimer.singleShot(350, self.create_plan)

    def choose_output_folder(self) -> None:
        current = self.output_folder.text().strip() or str(PROJECTS_PATH)
        folder = QFileDialog.getExistingDirectory(self, "Choose project folder", current)
        if folder:
            self.output_folder.setText(folder)

    def create_plan(self) -> None:
        request = self.request.toPlainText().strip()
        if not request:
            QMessageBox.information(self, APP_NAME, "Describe what JARVIS should build first.")
            return
        if self.worker is not None and self.worker.isRunning():
            return
        self.plan = None
        self.build_button.setEnabled(False)
        self.plan_button.setEnabled(False)
        self.preview.clear()
        self.status.setText("JARVIS is designing the project and preparing complete files...")
        self.worker = ProjectPlanWorker(self.client, request)
        self.worker.planned.connect(self._plan_ready)
        self.worker.failed.connect(self._plan_failed)
        self.worker.finished.connect(lambda: self.plan_button.setEnabled(True))
        self.worker.start()

    def _plan_ready(self, plan: object) -> None:
        if not isinstance(plan, dict):
            self._plan_failed("JARVIS returned an invalid plan.")
            return
        self.plan = plan
        self.project_name.setText(str(plan.get("project_name", "jarvis_project")))
        files = plan.get("files", [])
        lines = [
            f"PROJECT: {plan.get('project_name', '')}",
            f"SUMMARY: {plan.get('summary', '')}",
            f"RUN FILE: {plan.get('run_file', '') or 'See README'}",
            "",
            "FILES TO CREATE:",
        ]
        for item in files:
            content = str(item.get("content", ""))
            lines.append(f"  {item.get('path', '')}  ({len(content.encode('utf-8')):,} bytes)")
        lines.extend([
            "",
            "Nothing has been written yet.",
            "Review this list, then press Approve, Build and ZIP.",
        ])
        self.preview.setPlainText("\n".join(lines))
        self.status.setText(f"Plan ready: {len(files)} files. Waiting for your approval.")
        self.build_button.setEnabled(True)

    def _plan_failed(self, message: str) -> None:
        self.plan = None
        self.build_button.setEnabled(False)
        self.status.setText(f"Plan failed: {message}")
        self.preview.setPlainText(
            "Check the Gemini key/model in Settings, or continue without a key to create a basic starter project."
        )

    def build_project(self) -> None:
        if not self.plan:
            return
        project_name = safe_project_name(
            self.project_name.text(),
            str(self.plan.get("project_name", "jarvis_project")),
        )
        base = Path(self.output_folder.text().strip() or str(PROJECTS_PATH)).expanduser()
        target = base / project_name
        if target.exists():
            target = base / f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        zip_path = target.with_suffix(".zip")
        answer = QMessageBox.question(
            self,
            "Approve JARVIS mission",
            f"Create {len(self.plan['files'])} files in:\n{target}\n\nThen create:\n{zip_path}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.status.setText("Build cancelled. The plan is still available.")
            return

        try:
            target.mkdir(parents=True, exist_ok=False)
            for item in self.plan["files"]:
                relative = safe_relative_path(str(item["path"]))
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(str(item["content"]), encoding="utf-8")

            run_file = self._ensure_run_launcher(target)
            created_files = [
                path.relative_to(target).as_posix()
                for path in sorted(item for item in target.rglob("*") if item.is_file())
            ]
            manifest = {
                "created_by": APP_NAME,
                "jarvis_version": APP_VERSION,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "request": self.plan.get("request", ""),
                "summary": self.plan.get("summary", ""),
                "run_file": run_file,
                "files": created_files,
            }
            (target / "jarvis_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for file_path in sorted(path for path in target.rglob("*") if path.is_file()):
                    archive.write(file_path, file_path.relative_to(target).as_posix())
            self.last_project = target
            save_last_project(target)
            self.last_run_file = target / run_file if run_file else None
            self.open_button.setEnabled(True)
            self.run_button.setEnabled(bool(self.last_run_file and self.last_run_file.exists()))
            self.status.setText(f"Mission complete. Project and ZIP created: {zip_path}")
            self.preview.append(f"\nCREATED:\n  {target}\n  {zip_path}")
            QMessageBox.information(self, APP_NAME, f"Project created successfully.\n\n{target}\n\nZIP:\n{zip_path}")
        except Exception as exc:
            self.status.setText(f"Build failed: {exc}")
            QMessageBox.warning(self, APP_NAME, f"Could not build the project:\n{exc}")

    def open_result(self) -> None:
        if self.last_project and self.last_project.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_project)))

    def _ensure_run_launcher(self, target: Path) -> str:
        requested = str(self.plan.get("run_file", "") if self.plan else "").strip()
        return ensure_project_launcher(target, requested)

    def run_result(self) -> None:
        if not self.last_run_file or not self.last_run_file.exists():
            return
        answer = QMessageBox.question(
            self,
            "Run generated app",
            "This project was generated by AI. Run it only after reviewing the files.\n\nRun the app now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            suffix = self.last_run_file.suffix.lower()
            if suffix in {".html", ".htm", ".exe"}:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_run_file)))
            elif suffix == ".py":
                subprocess.Popen([sys.executable, str(self.last_run_file)], cwd=str(self.last_project))
            else:
                subprocess.Popen(
                    ["cmd.exe", "/c", str(self.last_run_file)],
                    cwd=str(self.last_project),
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                )
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not run the generated app:\n{exc}")


class AgentWorkspaceWidget(QWidget):
    """Approval-gated coding agent for the last generated or selected project."""

    def __init__(self, client: AIClient, initial_request: str = "", auto_start: bool = False):
        super().__init__()
        self.client = client
        self.worker: Optional[ProjectPatchWorker] = None
        self.plan: Optional[dict[str, Any]] = None
        self.last_run_file: Optional[Path] = None

        layout = QVBoxLayout(self)
        title = QLabel("JARVIS AGENT WORKSPACE")
        title.setStyleSheet("color:#8BE9FF;font-size:18px;font-weight:800;padding:4px;")
        note = QLabel(
            "JARVIS reads the selected project's source files, proposes exact changes, shows a diff, "
            "creates a backup, then applies only after approval."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#91C7D4;")
        layout.addWidget(title)
        layout.addWidget(note)

        form = QGridLayout()
        previous = last_project_path()
        self.project_folder = QLineEdit(str(previous) if previous else "")
        self.project_folder.setPlaceholderText("Choose an existing project folder")
        choose = QPushButton("Choose Project")
        choose.clicked.connect(self.choose_project)
        form.addWidget(QLabel("Project"), 0, 0)
        form.addWidget(self.project_folder, 0, 1)
        form.addWidget(choose, 0, 2)
        layout.addLayout(form)

        self.request = QTextEdit()
        self.request.setPlaceholderText("Example: Make the interface blue and add a reset button.")
        self.request.setMaximumHeight(95)
        self.request.setPlainText(initial_request.strip())
        layout.addWidget(self.request)

        controls = QHBoxLayout()
        self.plan_button = QPushButton("Plan Changes")
        self.apply_button = QPushButton("Approve and Apply")
        self.run_button = QPushButton("Run App")
        self.open_button = QPushButton("Open Folder")
        self.apply_button.setEnabled(False)
        self.run_button.setEnabled(False)
        self.plan_button.clicked.connect(self.plan_changes)
        self.apply_button.clicked.connect(self.apply_changes)
        self.run_button.clicked.connect(self.run_app)
        self.open_button.clicked.connect(self.open_folder)
        controls.addWidget(self.plan_button)
        controls.addWidget(self.apply_button)
        controls.addWidget(self.run_button)
        controls.addWidget(self.open_button)
        layout.addLayout(controls)

        self.status = QLabel("Ready. Select a project or use the last app created by JARVIS.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#72D7F2;padding:4px;")
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Proposed file changes and diffs appear here before anything is written.")
        self.preview.setStyleSheet(input_style() + "QTextEdit{font-family:Consolas;font-size:10px;}")
        layout.addWidget(self.status)
        layout.addWidget(self.preview, 1)
        self.setStyleSheet(button_style() + input_style() + "QLabel{color:#CFF7FF;}")

        if auto_start and initial_request.strip() and previous:
            QTimer.singleShot(400, self.plan_changes)

    def choose_project(self) -> None:
        current = self.project_folder.text().strip() or str(PROJECTS_PATH)
        folder = QFileDialog.getExistingDirectory(self, "Choose project for JARVIS", current)
        if folder:
            self.project_folder.setText(folder)
            save_last_project(Path(folder))

    def plan_changes(self) -> None:
        root = Path(self.project_folder.text().strip()).expanduser()
        request = self.request.toPlainText().strip()
        if not root.exists() or not root.is_dir():
            QMessageBox.warning(self, APP_NAME, "Choose a valid project folder first.")
            return
        if not request:
            QMessageBox.information(self, APP_NAME, "Describe the change JARVIS should make.")
            return
        if self.worker is not None and self.worker.isRunning():
            return
        save_last_project(root)
        self.plan = None
        self.apply_button.setEnabled(False)
        self.plan_button.setEnabled(False)
        self.preview.clear()
        self.status.setText("JARVIS is reading the project and designing the code changes...")
        self.worker = ProjectPatchWorker(self.client, root, request)
        self.worker.planned.connect(self._plan_ready)
        self.worker.failed.connect(self._plan_failed)
        self.worker.finished.connect(lambda: self.plan_button.setEnabled(True))
        self.worker.start()

    def _plan_ready(self, plan: object) -> None:
        if not isinstance(plan, dict):
            self._plan_failed("JARVIS returned an invalid change plan.")
            return
        root = Path(self.project_folder.text().strip()).expanduser()
        diff_lines = [f"SUMMARY: {plan.get('summary', '')}", "", "PROPOSED CHANGES:"]
        syntax_errors: list[str] = []
        for item in plan.get("files", []):
            relative = safe_relative_path(str(item.get("path", "")))
            destination = root / relative
            old = ""
            if destination.exists():
                try:
                    old = destination.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    old = ""
            new = str(item.get("content", ""))
            if destination.suffix.lower() == ".py":
                try:
                    ast.parse(new, filename=relative.as_posix())
                except SyntaxError as exc:
                    syntax_errors.append(f"{relative.as_posix()}: line {exc.lineno}: {exc.msg}")
            diff = list(difflib.unified_diff(
                old.splitlines(),
                new.splitlines(),
                fromfile=f"before/{relative.as_posix()}",
                tofile=f"after/{relative.as_posix()}",
                lineterm="",
            ))
            diff_lines.extend(["", f"=== {relative.as_posix()} ==="])
            diff_lines.extend(diff[:220] or ["New empty file"])
            if len(diff) > 220:
                diff_lines.append(f"... {len(diff) - 220} additional diff lines hidden")
        self.preview.setPlainText("\n".join(diff_lines))
        if syntax_errors:
            self.plan = None
            self.apply_button.setEnabled(False)
            self.status.setText("Python syntax check failed. Ask JARVIS to regenerate the change.")
            self.preview.append("\n\nSYNTAX ERRORS:\n" + "\n".join(syntax_errors))
            return
        self.plan = plan
        self.apply_button.setEnabled(True)
        self.status.setText(f"Plan ready: {len(plan.get('files', []))} files. Review the diff, then approve.")

    def _plan_failed(self, message: str) -> None:
        self.plan = None
        self.apply_button.setEnabled(False)
        self.status.setText(f"Agent plan failed: {message}")

    def apply_changes(self) -> None:
        if not self.plan:
            return
        root = Path(self.project_folder.text().strip()).expanduser()
        answer = QMessageBox.question(
            self,
            "Approve JARVIS code changes",
            f"Apply {len(self.plan['files'])} file changes to:\n{root}\n\nA backup will be created first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.status.setText("Update cancelled. No files were changed.")
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = AGENT_BACKUP_PATH / safe_project_name(root.name) / stamp
        try:
            changed: list[str] = []
            for item in self.plan["files"]:
                relative = safe_relative_path(str(item["path"]))
                destination = root / relative
                if destination.exists():
                    backup = backup_root / relative
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(destination, backup)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(str(item["content"]), encoding="utf-8")
                changed.append(relative.as_posix())

            requested_run = ""
            manifest_path = root / "jarvis_manifest.json"
            if manifest_path.exists():
                try:
                    requested_run = str(json.loads(manifest_path.read_text(encoding="utf-8")).get("run_file", ""))
                except Exception:
                    requested_run = ""
            run_file = ensure_project_launcher(root, requested_run)
            update_record = {
                "updated_by": APP_NAME,
                "jarvis_version": APP_VERSION,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "request": self.plan.get("request", ""),
                "summary": self.plan.get("summary", ""),
                "changed_files": changed,
                "backup": str(backup_root),
            }
            (root / "jarvis_last_update.json").write_text(
                json.dumps(update_record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            zip_path = root.parent / f"{root.name}_updated_{stamp}.zip"
            blocked = {".git", ".venv", "venv", "node_modules", "__pycache__"}
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(item for item in root.rglob("*") if item.is_file()):
                    if any(part.lower() in blocked for part in path.parts):
                        continue
                    archive.write(path, path.relative_to(root).as_posix())
            save_last_project(root)
            self.last_run_file = root / run_file if run_file else None
            self.run_button.setEnabled(bool(self.last_run_file and self.last_run_file.exists()))
            self.status.setText(f"Agent update complete. Backup saved and ZIP created: {zip_path}")
            QMessageBox.information(
                self,
                APP_NAME,
                f"Project updated successfully.\n\nBackup:\n{backup_root}\n\nZIP:\n{zip_path}",
            )
        except Exception as exc:
            self.status.setText(f"Agent update failed: {exc}")
            QMessageBox.warning(self, APP_NAME, f"Could not update the project:\n{exc}")

    def open_folder(self) -> None:
        root = Path(self.project_folder.text().strip()).expanduser()
        if root.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(root)))

    def run_app(self) -> None:
        if not self.last_run_file or not self.last_run_file.exists():
            return
        answer = QMessageBox.question(
            self,
            "Run updated app",
            "Run the updated project now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        root = Path(self.project_folder.text().strip()).expanduser()
        try:
            if self.last_run_file.suffix.lower() in {".html", ".htm", ".exe"}:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_run_file)))
            elif self.last_run_file.suffix.lower() == ".py":
                subprocess.Popen([sys.executable, str(self.last_run_file)], cwd=str(root))
            else:
                subprocess.Popen(
                    ["cmd.exe", "/c", str(self.last_run_file)],
                    cwd=str(root),
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                )
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not run the updated app:\n{exc}")


class ZipBuilderWidget(QWidget):
    """Builds ZIP files from local folders inside JARVIS."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("JARVIS ZIP BUILDER")
        title.setStyleSheet("color:#8BE9FF;font-size:18px;font-weight:800;padding:4px;")
        layout.addWidget(title)

        note = QLabel("Choose a folder, choose where the ZIP should be saved, then build it. Cache files are skipped by default.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#86B9C8;padding:0 4px 8px 4px;")
        layout.addWidget(note)

        form = QGridLayout()
        self.source = QLineEdit()
        self.output = QLineEdit()
        source_button = QPushButton("Browse")
        output_button = QPushButton("Save As")
        source_button.clicked.connect(self.choose_source)
        output_button.clicked.connect(self.choose_output)
        form.addWidget(QLabel("Source folder"), 0, 0)
        form.addWidget(self.source, 0, 1)
        form.addWidget(source_button, 0, 2)
        form.addWidget(QLabel("Output ZIP"), 1, 0)
        form.addWidget(self.output, 1, 1)
        form.addWidget(output_button, 1, 2)
        layout.addLayout(form)

        self.skip_cache = QCheckBox("Skip __pycache__, .pyc, .venv, node_modules and hidden temp folders")
        self.skip_cache.setChecked(True)
        layout.addWidget(self.skip_cache)

        row = QHBoxLayout()
        build = QPushButton("Build ZIP")
        jarvis = QPushButton("Use Current JARVIS Folder")
        build.clicked.connect(self.build_zip)
        jarvis.clicked.connect(self.use_current_jarvis_folder)
        row.addWidget(build)
        row.addWidget(jarvis)
        layout.addLayout(row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setStyleSheet(input_style() + "QTextEdit{font-family:Consolas;font-size:11px;padding:10px;}")
        layout.addWidget(self.log, 1)
        self.setStyleSheet(button_style() + input_style() + "QLabel{color:#CFF7FF;} QCheckBox{color:#DDF7FF;padding:6px;}")

    def choose_source(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose folder to ZIP", str(Path.home()))
        if not folder:
            return
        self.source.setText(folder)
        if not self.output.text().strip():
            self.output.setText(str(Path(folder).with_suffix(".zip")))

    def choose_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save ZIP as", str(Path.home() / "jarvis_package.zip"), "ZIP files (*.zip)")
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        self.output.setText(path)

    def use_current_jarvis_folder(self) -> None:
        root = Path(__file__).resolve().parent.parent
        self.source.setText(str(root))
        self.output.setText(str(root.parent / "JARVIS_HoloDesk_package.zip"))

    def _should_skip(self, path: Path) -> bool:
        if not self.skip_cache.isChecked():
            return False
        blocked_names = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".mypy_cache", ".pytest_cache"}
        if any(part in blocked_names for part in path.parts):
            return True
        if path.suffix.lower() in {".pyc", ".pyo", ".tmp", ".log"}:
            return True
        return False

    def build_zip(self) -> None:
        source_text = self.source.text().strip()
        output_text = self.output.text().strip()
        if not source_text:
            QMessageBox.warning(self, APP_NAME, "Choose a source folder first.")
            return
        if not output_text:
            QMessageBox.warning(self, APP_NAME, "Choose where the ZIP should be saved first.")
            return
        source = Path(source_text).expanduser()
        output = Path(output_text).expanduser()
        if not source.exists() or not source.is_dir():
            QMessageBox.warning(self, APP_NAME, "Choose a valid source folder first.")
            return
        if not output.name.lower().endswith(".zip"):
            output = output.with_suffix(".zip")
            self.output.setText(str(output))
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            count = 0
            total = 0
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for file_path in source.rglob("*"):
                    if not file_path.is_file() or self._should_skip(file_path):
                        continue
                    if file_path.resolve() == output.resolve():
                        continue
                    archive.write(file_path, file_path.relative_to(source).as_posix())
                    count += 1
                    total += file_path.stat().st_size
            self.log.append(f"ZIP created: {output}")
            self.log.append(f"Files: {count}")
            self.log.append(f"Source size: {round(total / 1024, 1)} KB")
            QMessageBox.information(self, APP_NAME, f"ZIP created:\n{output}")
        except Exception as exc:
            self.log.append(f"ERROR: {exc}")
            QMessageBox.warning(self, APP_NAME, f"Could not build ZIP:\n{exc}")


class SelfEditWidget(QWidget):
    """Safe self-editing for JARVIS behavior without arbitrary code changes."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("JARVIS SELF EDIT CENTER")
        title.setStyleSheet("color:#8BE9FF;font-size:18px;font-weight:800;padding:4px;")
        layout.addWidget(title)

        note = QLabel("Change JARVIS safely from inside the app. These edits are stored locally and do not rewrite Python code.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#86B9C8;padding:0 4px 8px 4px;")
        layout.addWidget(note)

        config = load_self_edit_config()
        form = QGridLayout()
        self.center_text = QLineEdit(config.get("center_text", "JARVIS"))
        self.voice_style = QComboBox()
        self.voice_style.addItems(["simple", "fast", "teacher", "cool"])
        index = self.voice_style.findText(config.get("voice_style", "simple"))
        self.voice_style.setCurrentIndex(max(0, index))
        form.addWidget(QLabel("Center text"), 0, 0)
        form.addWidget(self.center_text, 0, 1)
        form.addWidget(QLabel("Voice style"), 1, 0)
        form.addWidget(self.voice_style, 1, 1)
        layout.addLayout(form)

        tabs = QTabWidget()
        self.prompt = QTextEdit()
        self.prompt.setPlainText(config.get("custom_prompt", ""))
        self.prompt.setPlaceholderText("Optional. Leave empty to use the built-in Gemini-like JARVIS prompt.")
        self.aliases = QTextEdit()
        self.aliases.setPlainText(config.get("aliases", ""))
        self.aliases.setPlaceholderText("One per line, for example:\nmission => future self\npackage project => zip builder")
        tabs.addTab(self.prompt, "Prompt")
        tabs.addTab(self.aliases, "Command Aliases")
        layout.addWidget(tabs, 1)

        row = QHBoxLayout()
        save = QPushButton("Save Self Edits")
        defaults = QPushButton("Load Safe Defaults")
        save.clicked.connect(self.save)
        defaults.clicked.connect(self.load_defaults)
        row.addWidget(save)
        row.addWidget(defaults)
        layout.addLayout(row)

        self.status = QLabel("")
        self.status.setStyleSheet("color:#7FCDE2;padding:4px;")
        layout.addWidget(self.status)
        self.setStyleSheet(button_style() + input_style() + "QLabel{color:#CFF7FF;} QTabWidget::pane{border:1px solid #28758E;} QTabBar::tab{color:#DDF7FF;background:#102A38;padding:8px;}")

    def save(self) -> None:
        data = {
            "center_text": self.center_text.text().strip() or "JARVIS",
            "voice_style": self.voice_style.currentText().strip() or "simple",
            "custom_prompt": self.prompt.toPlainText().strip(),
            "aliases": self.aliases.toPlainText().strip(),
        }
        SELF_EDIT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status.setText(f"Saved locally: {SELF_EDIT_PATH}")
        QMessageBox.information(self, APP_NAME, "Self edits saved. Some changes appear immediately; prompt changes apply to the next AI answer.")

    def load_defaults(self) -> None:
        defaults = load_self_edit_config()
        defaults.update({
            "center_text": "JARVIS",
            "voice_style": "simple",
            "custom_prompt": "",
            "aliases": "mission => future self\npackage project => zip builder\nmy map => world map",
        })
        self.center_text.setText(defaults["center_text"])
        self.voice_style.setCurrentText(defaults["voice_style"])
        self.prompt.setPlainText(defaults["custom_prompt"])
        self.aliases.setPlainText(defaults["aliases"])
        self.status.setText("Safe defaults loaded. Press Save Self Edits to keep them.")


class ReactorCore(QWidget):
    """Animated circular HUD inspired by futuristic reactor/console interfaces."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase = 0.0
        self.pulse = 0.0
        self.setMinimumSize(420, 420)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(32)

    def _tick(self) -> None:
        self.phase = (self.phase + 2.2) % 360.0
        self.pulse = (self.pulse + 0.055) % (math.pi * 2)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() // 2, self.height() // 2
        radius = min(self.width(), self.height()) // 2 - 28
        for i in range(8, 0, -1):
            alpha = 8 + i * 4
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 145, 255, alpha))
            r = int(radius * (0.32 + i * 0.035))
            painter.drawEllipse(QPoint(cx, cy), r, r)
        for scale, width, alpha in [(1.00,2,100),(0.88,1,80),(0.76,2,130),(0.62,1,80),(0.49,2,160),(0.36,1,110)]:
            r = int(radius * scale)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(57, 190, 255, alpha), width))
            painter.drawEllipse(QPoint(cx, cy), r, r)
        for ring_index, (scale, segments, span, direction) in enumerate([(0.94,18,10,1),(0.72,14,14,-1),(0.55,10,20,1)]):
            r = int(radius * scale)
            rect = QRect(cx-r, cy-r, r*2, r*2)
            painter.setPen(QPen(QColor(88, 215, 255, 190), 4 if ring_index == 0 else 3))
            start_base = self.phase * direction + ring_index * 17
            for i in range(segments):
                start = int((start_base + i * (360/segments)) * 16)
                painter.drawArc(rect, start, int(span * 16))
        painter.setPen(QPen(QColor(85, 205, 242, 120), 2))
        for angle in range(0, 360, 15):
            a = math.radians(angle + self.phase * 0.15)
            outer = radius * 0.82
            inner = outer - (15 if angle % 45 == 0 else 7)
            painter.drawLine(int(cx + math.cos(a)*inner), int(cy + math.sin(a)*inner), int(cx + math.cos(a)*outer), int(cy + math.sin(a)*outer))
        core_r = int(radius * (0.22 + 0.015 * math.sin(self.pulse)))
        painter.setPen(QPen(QColor(131, 231, 255, 230), 2))
        painter.setBrush(QColor(0, 87, 180, 210))
        painter.drawEllipse(QPoint(cx, cy), core_r, core_r)
        painter.setBrush(QColor(22, 148, 255, 155))
        painter.drawEllipse(QPoint(cx, cy), int(core_r*0.68), int(core_r*0.68))
        font = painter.font(); font.setBold(True); font.setPointSize(13); painter.setFont(font)
        painter.setPen(QColor('#DDF8FF'))
        center_text = load_self_edit_config().get("center_text", "JARVIS").strip() or "JARVIS"
        painter.drawText(QRect(cx-120, cy-24, 240, 30), Qt.AlignmentFlag.AlignCenter, center_text[:18])
        font.setPointSize(9); font.setBold(False); painter.setFont(font); painter.setPen(QColor('#72D7F2'))
        painter.drawText(QRect(cx-120, cy+8, 240, 24), Qt.AlignmentFlag.AlignCenter, 'SYSTEM ONLINE')


class JarvisDashboard(QWidget):
    """Home HUD; existing HoloDesk tools open above it as virtual windows."""
    def __init__(self, canvas: 'HoloCanvas'):
        super().__init__(canvas)
        self.canvas = canvas
        self.setObjectName('jarvisDashboard')
        self.setStyleSheet("""
            QWidget#jarvisDashboard { background: transparent; }
            QFrame#hudPanel { background: rgba(3, 14, 23, 205); border: 1px solid rgba(54, 188, 235, 100); border-radius: 14px; }
            QLabel { color: #CFF7FF; }
            QLabel#hudTitle { color: #72DDF7; font-weight: 800; font-size: 13px; }
            QPushButton { color:#DDF8FF; background:rgba(9,49,72,210); border:1px solid rgba(67,199,238,100); border-radius:8px; padding:7px 10px; }
            QPushButton:hover { background:rgba(17,86,115,235); border-color:rgba(110,226,255,180); }
            QProgressBar { color:#CFF7FF; background:rgba(0,15,24,180); border:1px solid rgba(61,183,220,80); border-radius:5px; text-align:center; }
            QProgressBar::chunk { background:rgba(29,143,200,190); border-radius:4px; }
            QLineEdit { color:#DDF8FF; background:rgba(2,15,24,220); border:1px solid rgba(67,199,238,120); border-radius:8px; padding:8px; }
        """)
        root = QHBoxLayout(self); root.setContentsMargins(18,10,18,16); root.setSpacing(14)

        left = QFrame(); left.setObjectName('hudPanel'); left.setFixedWidth(260)
        left_l = QVBoxLayout(left); left_l.setContentsMargins(14,14,14,14)
        title = QLabel('SYSTEM TELEMETRY'); title.setObjectName('hudTitle'); left_l.addWidget(title)
        self.clock = QLabel('--:--:--'); self.clock.setStyleSheet('font-size:24px;font-weight:700;color:#E6FBFF;'); left_l.addWidget(self.clock)
        self.date = QLabel(''); self.date.setStyleSheet('color:#6FB8C9;'); left_l.addWidget(self.date)
        self.cpu = self._meter('CPU', left_l); self.ram = self._meter('MEMORY', left_l); self.disk = self._meter('DISK', left_l)
        left_l.addSpacing(8); self.net = QLabel('NETWORK  •  ONLINE'); left_l.addWidget(self.net)
        self.ip = QLabel(f'LOCAL IP  •  {local_ip()}'); self.ip.setStyleSheet('color:#6FB8C9;'); left_l.addWidget(self.ip)
        left_l.addStretch()
        for text, cb in [('AGENT WORKSPACE', canvas.add_agent_workspace_window), ('MISSION BUILDER', canvas.add_mission_builder_window), ('WINDOWS', canvas.add_windows_manager), ('SETTINGS', canvas.add_settings_window)]:
            b=QPushButton(text); b.clicked.connect(lambda checked=False, fn=cb: fn()); left_l.addWidget(b)

        center = QFrame(); center.setObjectName('hudPanel')
        center_l = QVBoxLayout(center); center_l.setContentsMargins(10,10,10,10)
        center_title = QLabel('HOLODESK / REACTOR CONSOLE'); center_title.setObjectName('hudTitle'); center_title.setAlignment(Qt.AlignmentFlag.AlignCenter); center_l.addWidget(center_title)
        self.reactor = ReactorCore(); center_l.addWidget(self.reactor, 1)
        status = QLabel('VOICE AUTO-LISTEN • WINDOWS CONTROL • AI CORE'); status.setAlignment(Qt.AlignmentFlag.AlignCenter); status.setStyleSheet('color:#5CBBD3;font-size:10px;'); center_l.addWidget(status)
        row=QHBoxLayout()
        for text, cb in [('AGENT', canvas.add_agent_workspace_window), ('MISSION', canvas.add_mission_builder_window), ('AIR MENU', canvas.open_air_menu), ('ZIP', canvas.add_zip_builder_window)]:
            b=QPushButton(text); b.clicked.connect(lambda checked=False, fn=cb: fn()); row.addWidget(b)
        center_l.addLayout(row)

        right = QFrame(); right.setObjectName('hudPanel'); right.setFixedWidth(310)
        right_l = QVBoxLayout(right); right_l.setContentsMargins(14,14,14,14)
        rt = QLabel('ACTIVITY / COMMAND'); rt.setObjectName('hudTitle'); right_l.addWidget(rt)
        self.activity = QTextEdit(); self.activity.setReadOnly(True); self.activity.setStyleSheet('QTextEdit{color:#85DDF2;background:rgba(0,8,14,180);border:1px solid rgba(60,170,210,60);border-radius:8px;padding:8px;font-family:Consolas;font-size:10px;}')
        self.activity.setHtml('<b>CORE</b> JARVIS reactor initialized.<br><b>VOICE</b> Auto-listen starting…<br><b>WIN32</b> Windows controller ready.'); right_l.addWidget(self.activity, 1)
        self.command = QLineEdit(); self.command.setPlaceholderText('Command: generate app / change it / open chrome ...'); self.command.returnPressed.connect(self.run_command); right_l.addWidget(self.command)
        hint=QLabel('VOICE • ALWAYS ON\nGenerate app • Change it • Fix the app\nOpen Chrome • Time • Notes'); hint.setStyleSheet('color:#78BCCC;'); right_l.addWidget(hint)
        root.addWidget(left); root.addWidget(center, 1); root.addWidget(right)
        self.stats_timer=QTimer(self); self.stats_timer.timeout.connect(self.refresh_stats); self.stats_timer.start(800); self.refresh_stats()

    def _meter(self, name: str, layout: QVBoxLayout) -> QProgressBar:
        label=QLabel(name); label.setStyleSheet('color:#6FB8C9;font-size:10px;'); layout.addWidget(label)
        bar=QProgressBar(); bar.setRange(0,100); bar.setValue(0); bar.setFormat('%p%'); bar.setFixedHeight(18); layout.addWidget(bar); return bar

    def refresh_stats(self) -> None:
        now=datetime.now(); self.clock.setText(now.strftime('%H:%M:%S')); self.date.setText(now.strftime('%A • %d %B %Y'))
        try:
            if PSUTIL_AVAILABLE:
                self.cpu.setValue(int(psutil.cpu_percent(interval=None))); self.ram.setValue(int(psutil.virtual_memory().percent)); self.disk.setValue(int(psutil.disk_usage(str(Path.home().anchor or '/')).percent))
                self.net.setText('NETWORK  •  ONLINE')
            else:
                self.net.setText('NETWORK  •  BASIC MODE')
        except Exception:
            pass

    def log(self, source: str, message: str) -> None:
        stamp=datetime.now().strftime('%H:%M:%S'); self.activity.append(f'<span style="color:#5B9FB2">{stamp}</span> <b>{source}</b> {message}')

    def run_command(self) -> None:
        cmd=self.command.text().strip(); self.command.clear()
        if not cmd: return
        if self.canvas.execute_command(cmd, silent=True):
            self.log('CMD', f'Executed: {cmd}')
        else:
            self.log('JARVIS', self.canvas.ai_client.local_response(cmd))


class HoloCanvas(QWidget):
    def __init__(self, settings: AppSettings):
        super().__init__()
        self.settings = settings
        self.setMouseTracking(True)
        self.windows: list[VirtualWindow] = []
        self.active_window: Optional[VirtualWindow] = None
        self.pointer = QPoint(-100, -100)
        self.eye_pointer = QPoint(-100, -100)
        self.gesture_text = "No hand"
        self.hand_detail = ""
        self.show_camera = settings.show_camera
        self.camera_frame: Optional[np.ndarray] = None
        self.camera_pixmap = QPixmap()
        self.phone_frame: Optional[QPixmap] = None

        # Independent rates: Qt UI ≈60 FPS, camera ≈30 FPS, MediaPipe 15–20 FPS.
        self.ui_fps = 0.0
        self.camera_fps = 0.0
        self.tracking_fps = 0.0
        self.frame_counter = 0
        self.fps_started = time.perf_counter()
        self.latest_camera_sequence = -1
        self.latest_tracking_sequence = -1
        self.pointer_target = QPoint(-100, -100)
        self.primary_pinching = False

        self.camera_ok = False
        self.eye_tracking_enabled = settings.eye_tracking
        self.eye_cursor_enabled = settings.eye_cursor
        self.camera_worker: Optional[CameraWorker] = None
        self.tracking_worker: Optional[TrackingWorker] = None

        self.grabbed_window: Optional[VirtualWindow] = None
        self.grab_offset = QPoint()
        self.was_pinching = False
        self.two_hand_resize = False
        self.resize_start_distance = 0.0
        self.resize_start_geometry = QRect()
        self.last_open_event = 0.0
        self.last_gesture_shortcut = 0.0

        self.windows_controller = WindowsController()
        self.ai_client = AIClient(settings)
        self.companion_state = CompanionState()
        self.companion_server = CompanionServer(self.companion_state)
        self.command_callbacks: dict[str, Callable[[], Any]] = {}

        self.particles = [
            {"x": random.random(), "y": random.random(), "vx": random.uniform(-0.0004, 0.0004), "vy": random.uniform(0.0001, 0.0007), "r": random.uniform(1.0, 2.7)}
            for _ in range(74)
        ]

        self._start_realtime_pipeline()

        # UI rendering never waits for camera capture, MediaPipe, AI or weather requests.
        self.render_timer = QTimer(self)
        self.render_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.render_timer.timeout.connect(self.render_tick)
        self.render_timer.start(16)
        self.remote_timer = QTimer(self)
        self.remote_timer.timeout.connect(self.poll_remote_events)
        self.remote_timer.start(30)
        self.particle_timer = QTimer(self)
        self.particle_timer.timeout.connect(self.animate_particles)
        self.particle_timer.start(90 if self.settings.performance_mode else 50)

        # Reactor-style home dashboard. Existing tools open above it as floating windows.
        self.dashboard = JarvisDashboard(self)
        self.dashboard.setGeometry(10, 76, max(900, self.width() - 20), max(540, self.height() - 86))
        self.dashboard.show()
        self.dashboard.lower()

    def _start_realtime_pipeline(self) -> None:
        # Hand/camera control intentionally disabled in 1.2.1.
        # The Reactor dashboard and all mouse/keyboard tools remain unchanged.
        self.camera_worker = None
        self.tracking_worker = None
        self.camera_ok = False
        self.camera_fps = 0.0
        self.tracking_fps = 0.0
        self.gesture_text = "Manual control"
        self.hand_detail = ""
        self.pointer = QPoint(-100, -100)
        self.pointer_target = QPoint(-100, -100)

    def set_eye_tracking(self, enabled: bool) -> None:
        self.eye_tracking_enabled = enabled
        self.settings.eye_tracking = enabled
        if not enabled:
            self.eye_pointer = QPoint(-100, -100)
        self.settings.save()

    def set_eye_cursor(self, enabled: bool) -> None:
        self.eye_cursor_enabled = enabled
        self.settings.eye_cursor = enabled
        self.settings.save()

    def set_performance_mode(self, enabled: bool) -> None:
        self.settings.performance_mode = enabled
        self.particle_timer.setInterval(90 if enabled else 50)
        self.settings.save()

    def animate_particles(self) -> None:
        for particle in self.particles:
            particle["x"] += particle["vx"]
            particle["y"] += particle["vy"]
            if particle["x"] < 0 or particle["x"] > 1:
                particle["vx"] *= -1
            if particle["y"] > 1:
                particle["y"] = 0
                particle["x"] = random.random()
        # render_tick() owns repaint scheduling at a stable 60 FPS.

    def unregister_window(self, window: VirtualWindow) -> None:
        if window in self.windows:
            self.windows.remove(window)
        if self.active_window is window:
            self.active_window = self.windows[-1] if self.windows else None

    def place_window(self, window: VirtualWindow, geometry: Optional[list[int]] = None) -> VirtualWindow:
        if geometry and len(geometry) == 4:
            window.setGeometry(*map(int, geometry))
        else:
            usable_w = max(1, self.width() - window.width() - 140)
            usable_h = max(1, self.height() - window.height() - 160)
            x = 72 + (len(self.windows) * 42) % usable_w
            y = 102 + (len(self.windows) * 34) % usable_h
            window.move_clamped(x, y)
        self.windows.append(window)
        self.active_window = window
        window.raise_()
        return window

    def add_text_window(self, title: str = "Notes", text: str = "Write something here…", geometry: Optional[list[int]] = None) -> VirtualWindow:
        editor = QTextEdit()
        editor.setPlainText(text)
        editor.setStyleSheet(input_style() + "QTextEdit{border:none;border-radius:0;padding:12px;font-size:14px;}")
        return self.place_window(VirtualWindow(self, title, editor, 420, 290, "text", {"text": text}), geometry)

    def add_image_window(self, path: str = "", geometry: Optional[list[int]] = None) -> Optional[VirtualWindow]:
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Choose an image", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return None
        view = ImageView(path)
        return self.place_window(VirtualWindow(self, Path(path).name, view, 480, 330, "image", {"path": path}), geometry)

    def add_browser_window(self, url: str = "https://www.google.com", geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "Browser", BrowserWidget(url), 720, 490, "browser", {"url": url}), geometry)

    def add_video_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "Video Player", MediaWidget("video"), 640, 420, "video"), geometry)

    def add_music_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "Music", MediaWidget("music"), 470, 340, "music"), geometry)

    def add_calculator_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "Calculator", CalculatorWidget(), 350, 430, "calculator"), geometry)

    def add_calendar_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        calendar = QCalendarWidget()
        calendar.setStyleSheet("QCalendarWidget{background:#08131D;color:#EAFBFF;}QToolButton{color:#EAFBFF;background:#15394A;}")
        return self.place_window(VirtualWindow(self, "Calendar", calendar, 470, 390, "calendar"), geometry)

    def add_weather_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "Weather", WeatherWidget(), 430, 320, "weather"), geometry)

    def add_clock_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "Clock", ClockWidget(), 410, 250, "clock"), geometry)

    def add_ai_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "JARVIS AI", AIChatWidget(self.ai_client, self), 620, 460, "ai"), geometry)

    def add_world_map_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "JARVIS World Map", WorldMapWidget(), 720, 520, "world_map"), geometry)

    def open_google_location(self) -> bool:
        for window in self.windows:
            if window.content_type == "google_location":
                window.show()
                window.maximize_window()
                return True
        window = self.place_window(VirtualWindow(self, "JARVIS / Google Maps", GoogleLocationWidget(), 1000, 700, "google_location"))
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        window.maximize_window()
        return True

    def add_location_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        for window in self.windows:
            if window.content_type == "location":
                window.show()
                window.maximize_window()
                window.raise_()
                self.active_window = window
                return window
        window = self.place_window(VirtualWindow(self, "JARVIS / My Location", LocationMapWidget(), 1000, 680, "location"), geometry)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        if not geometry:
            window.maximize_window()
        return window

    def add_future_self_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "Future Self Simulator", FutureSelfWidget(), 680, 500, "future_self"), geometry)

    def add_mission_builder_window(
        self,
        initial_request: str = "",
        geometry: Optional[list[int]] = None,
        auto_start: bool = False,
    ) -> VirtualWindow:
        data = {"request": initial_request} if initial_request else {}
        return self.place_window(
            VirtualWindow(
                self,
                "JARVIS Mission Builder",
                MissionBuilderWidget(self.ai_client, initial_request, auto_start),
                820,
                610,
                "mission_builder",
                data,
            ),
            geometry,
        )

    def add_agent_workspace_window(
        self,
        initial_request: str = "",
        geometry: Optional[list[int]] = None,
        auto_start: bool = False,
    ) -> VirtualWindow:
        data = {"request": initial_request} if initial_request else {}
        return self.place_window(
            VirtualWindow(
                self,
                "JARVIS Agent Workspace",
                AgentWorkspaceWidget(self.ai_client, initial_request, auto_start),
                860,
                640,
                "agent_workspace",
                data,
            ),
            geometry,
        )

    def add_zip_builder_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "JARVIS ZIP Builder", ZipBuilderWidget(), 720, 500, "zip_builder"), geometry)

    def add_self_edit_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "JARVIS Self Edit Center", SelfEditWidget(), 740, 540, "self_edit"), geometry)

    def add_windows_manager(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "Windows Manager", WindowsManagerWidget(self.windows_controller), 760, 500, "windows_manager"), geometry)

    def add_voice_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "Voice Commands", VoiceControlWidget(self), 520, 350, "voice"), geometry)

    def add_phone_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        return self.place_window(VirtualWindow(self, "Phone Companion", PhoneCompanionWidget(self), 530, 490, "phone"), geometry)

    def add_settings_window(self, geometry: Optional[list[int]] = None) -> VirtualWindow:
        widget = SettingsWidget(self.settings)
        widget.settings_changed.connect(self.reload_ai_client)
        return self.place_window(VirtualWindow(self, "Settings", widget, 540, 390, "settings"), geometry)

    def reload_ai_client(self) -> None:
        self.ai_client = AIClient(self.settings)

    def open_air_menu(self) -> None:
        now = time.monotonic()
        if now - self.last_open_event < 1.25:
            return
        self.last_open_event = now
        menu = QFrame(self)
        menu.setObjectName("airMenu")
        menu.setGeometry(24, 88, 270, 540)
        menu.setStyleSheet("""
            QFrame#airMenu{background:rgba(6,18,28,248);border:1px solid rgba(88,225,255,190);border-radius:20px;}
            QLabel{color:#8BE9FF;font-weight:800;} QPushButton{color:#EAFBFF;background:rgba(31,74,94,205);border:1px solid rgba(90,220,255,65);border-radius:9px;padding:8px;text-align:left;}
            QPushButton:hover{background:rgba(65,126,150,235);}
        """)
        layout = QVBoxLayout(menu)
        layout.setContentsMargins(12, 12, 12, 12)
        title = QLabel("JARVIS AIR MENU")
        layout.addWidget(title)
        items = [
            ("AGENT WORKSPACE", self.add_agent_workspace_window),
            ("MISSION BUILDER", self.add_mission_builder_window),
            ("🛠 Self Edit Center", self.add_self_edit_window),
            ("🧭 World Map", self.add_world_map_window),
            ("🔮 Future Self", self.add_future_self_window),
            ("📦 ZIP Builder", self.add_zip_builder_window),
            ("🪟 Windows Manager", self.add_windows_manager),
            ("🤖 AI Assistant", self.add_ai_window),
            ("🌐 Browser", self.add_browser_window),
            ("📝 Notes", self.add_text_window),
            ("🎬 Video", self.add_video_window),
            ("♫ Music", self.add_music_window),
            ("🧮 Calculator", self.add_calculator_window),
            ("📅 Calendar", self.add_calendar_window),
            ("🌦 Weather", self.add_weather_window),
            ("🕒 Clock", self.add_clock_window),
            ("🎙 Voice", self.add_voice_window),
            ("📱 Phone Companion", self.add_phone_window),
            ("⚙ Settings", self.add_settings_window),
        ]
        for text, callback in items:
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, cb=callback: (cb(), menu.deleteLater()))
            layout.addWidget(button)
        close = QPushButton("× Close Menu")
        close.clicked.connect(menu.deleteLater)
        layout.addWidget(close)
        menu.show()
        menu.raise_()

    def window_at(self, x: int, y: int) -> Optional[VirtualWindow]:
        for window in reversed(self.windows):
            if window.isVisible() and window.geometry().contains(x, y):
                return window
        return None

    def _point_from_hand(self, hand: dict[str, Any]) -> QPoint:
        ix, iy = hand["index"][0], hand["index"][1]
        return QPoint(
            int(clamp(ix * self.width(), 0, self.width() - 1)),
            int(clamp(iy * self.height(), 0, self.height() - 1)),
        )

    def update_hand_control(self, hands: list[dict[str, Any]]) -> None:
        if not hands:
            self.gesture_text = "No hand"
            self.hand_detail = ""
            self.pointer_target = QPoint(-100, -100)
            self.primary_pinching = False
            self.was_pinching = False
            self.grabbed_window = None
            self.two_hand_resize = False
            return

        primary = hands[0]
        self.pointer_target = self._point_from_hand(primary)
        self.gesture_text = primary["gesture"]
        finger_letters = "".join(name[0].upper() for name, state in primary["fingers"].items() if state)
        self.hand_detail = f"{primary['handedness']} • fingers:{finger_letters or 'none'} • pinch:{primary['pinch_strength']:.0%}"

        if primary["palm_open"] and time.monotonic() - self.last_open_event > 1.0:
            self.open_air_menu()

        pinching = bool(primary["pinching"])
        self.primary_pinching = pinching
        x, y = self.pointer_target.x(), self.pointer_target.y()

        if pinching and not self.was_pinching:
            target_widget = self.childAt(x, y)
            if isinstance(target_widget, QPushButton):
                target_widget.click()
                self.was_pinching = True
                return
            target = self.window_at(x, y)
            if target:
                self.grabbed_window = target
                self.active_window = target
                target.raise_()
                self.grab_offset = QPoint(x - target.x(), y - target.y())

        two_pinches = len(hands) >= 2 and hands[0]["pinching"] and hands[1]["pinching"]
        if two_pinches and self.grabbed_window:
            p1 = self._point_from_hand(hands[0])
            p2 = self._point_from_hand(hands[1])
            current_distance = math.hypot(p1.x() - p2.x(), p1.y() - p2.y())
            if not self.two_hand_resize:
                self.two_hand_resize = True
                self.resize_start_distance = max(20.0, current_distance)
                self.resize_start_geometry = self.grabbed_window.geometry()
            scale = clamp(current_distance / self.resize_start_distance, 0.55, 2.2)
            new_w = int(clamp(self.resize_start_geometry.width() * scale, 250, self.width() - 16))
            new_h = int(clamp(self.resize_start_geometry.height() * scale, 150, self.height() - 86))
            center_x = (p1.x() + p2.x()) // 2
            center_y = (p1.y() + p2.y()) // 2
            self.grabbed_window.resize(new_w, new_h)
            self.grabbed_window.move_clamped(center_x - new_w // 2, center_y - new_h // 2)
        elif pinching and self.grabbed_window:
            # Position is interpolated in render_tick() at 60 FPS.
            self.two_hand_resize = False
        else:
            self.two_hand_resize = False

        if not pinching:
            self.grabbed_window = None

        # Deliberate two-hand gesture shortcuts with cooldown.
        now = time.monotonic()
        if len(hands) >= 2 and now - self.last_gesture_shortcut > 1.5:
            gestures = {hands[0]["gesture"], hands[1]["gesture"]}
            if gestures == {"open", "fist"} and self.active_window:
                self.active_window.toggle_maximize()
                self.last_gesture_shortcut = now
            elif hands[0]["gesture"] == "victory" and hands[1]["gesture"] == "victory":
                self.save_workspace(show_message=False)
                self.last_gesture_shortcut = now

        self.was_pinching = pinching

    def update_eye_control(self, face: Optional[dict[str, Any]]) -> None:
        if not face:
            self.eye_pointer = QPoint(-100, -100)
            return
        gx, gy = face["gaze"]
        self.eye_pointer = QPoint(int(gx * self.width()), int(gy * self.height()))
        if self.eye_cursor_enabled and self.pointer_target.x() < 0:
            self.pointer_target = QPoint(self.eye_pointer.x(), self.eye_pointer.y())

    def _refresh_camera_pixmap(self, frame: np.ndarray) -> None:
        if not self.show_camera:
            return
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, _ = rgb.shape
            image = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
            source = QPixmap.fromImage(image)
            target_size = QSize(max(1, self.width()), max(1, self.height() - 70))
            transform = Qt.TransformationMode.FastTransformation if self.settings.performance_mode else Qt.TransformationMode.SmoothTransformation
            self.camera_pixmap = source.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                transform,
            )
        except Exception:
            self.camera_pixmap = QPixmap()

    def _interpolate_pointer(self) -> None:
        if self.pointer_target.x() < 0:
            self.pointer = QPoint(-100, -100)
            return
        if self.pointer.x() < 0:
            self.pointer = QPoint(self.pointer_target.x(), self.pointer_target.y())
            return

        alpha = 0.28
        nx = self.pointer.x() + (self.pointer_target.x() - self.pointer.x()) * alpha
        ny = self.pointer.y() + (self.pointer_target.y() - self.pointer.y()) * alpha
        if abs(self.pointer_target.x() - nx) < 0.8:
            nx = self.pointer_target.x()
        if abs(self.pointer_target.y() - ny) < 0.8:
            ny = self.pointer_target.y()
        self.pointer = QPoint(int(nx), int(ny))

    def render_tick(self) -> None:
        # Hand/camera control is disabled. Keep the Reactor UI responsive at 60 FPS.
        self.gesture_text = "Manual control"
        self.hand_detail = ""
        self.pointer = QPoint(-100, -100)
        self.pointer_target = QPoint(-100, -100)
        self.primary_pinching = False
        self.grabbed_window = None
        self.two_hand_resize = False
        self.update()

    def poll_remote_events(self) -> None:
        for _ in range(20):
            try:
                event = self.companion_state.events.get_nowait()
            except queue.Empty:
                break
            event_type = event.get("type")
            if event_type == "move":
                dx = safe_int(event.get("dx"))
                dy = safe_int(event.get("dy"))
                if self.windows_controller.available:
                    self.windows_controller.move_cursor(dx, dy)
                else:
                    base_x = self.pointer.x() if self.pointer.x() >= 0 else self.width() // 2
                    base_y = self.pointer.y() if self.pointer.y() >= 0 else self.height() // 2
                    self.pointer_target = QPoint(
                        int(clamp(base_x + dx, 0, self.width() - 1)),
                        int(clamp(base_y + dy, 0, self.height() - 1)),
                    )
            elif event_type == "command":
                command = str(event.get("command", ""))
                if command == "click":
                    if self.windows_controller.available:
                        self.windows_controller.click()
                    else:
                        target = self.childAt(self.pointer)
                        if isinstance(target, QPushButton):
                            target.click()
                else:
                    self.execute_command(command, silent=True)

    def start_companion(self) -> tuple[bool, str]:
        return self.companion_server.start(self.settings.phone_port)

    def stop_companion(self) -> None:
        self.companion_server.stop()

    def execute_command(self, raw_command: str, silent: bool = False) -> bool:
        if google_maps_intent(raw_command):
            self.open_google_location()
            return True
        if location_intent(raw_command):
            self.add_location_window()
            return True
        pc_command = parse_pc_command(raw_command)
        if pc_command:
            return self.windows_controller.voice_command(pc_command)
        command = raw_command.strip().lower()
        normalized = command.replace("-", " ").replace("_", " ")
        command_words = set(normalized.split())

        def has(*phrases: str) -> bool:
            return any(phrase in normalized for phrase in phrases)

        def log(source: str, message: str) -> None:
            reactor = getattr(self, "reactor_console", None)
            if reactor is not None and hasattr(reactor, "log"):
                reactor.log(source, message)

        aliased = self._custom_alias_command(normalized)
        if aliased and aliased != normalized:
            return self.execute_command(aliased, silent=silent)

        if has("clear memory", "forget conversation", "forget our conversation"):
            self.ai_client.clear_memory()
            log("JARVIS", "Conversation memory cleared.")
            return True

        if has("help", "commands", "what can you do"):
            log("JARVIS", "Commands: build project, edit last app, zip builder, open Chrome, open Notepad, open Calculator, time.")
            return True
        if has("what is your name", "who are you"):
            log("JARVIS", "I am JARVIS 2.0 Agent Core, your local Windows assistant.")
            return True
        if "time" in command_words or has("what time"):
            log("TIME", f"Current time: {datetime.now().strftime('%H:%M:%S')}")
            return True
        if has("open chrome"):
            return self.windows_controller.launch("chrome")
        if has("open notepad", "notepad"):
            return self.windows_controller.launch("notepad")
        if has("open calculator", "open calc", "calc.exe", "windows calculator", "calculator"):
            return self.windows_controller.launch("calc")
        if has("open windows browser", "windows browser", "open default browser", "default browser"):
            return QDesktopServices.openUrl(QUrl("https://www.google.com"))
        if has("open browser", "browser"):
            self.add_browser_window(); return True
        if has("open ai", "ai assistant"):
            self.add_ai_window(); return True
        agent_phrases = (
            "agent workspace", "edit project", "edit app", "update project",
            "update app", "change project", "change app", "fix project", "fix app",
        )
        if not project_generation_intent(normalized) and (
            has(*agent_phrases) or project_edit_intent(normalized) or project_followup_intent(normalized)
        ):
            request = raw_command.strip()
            if normalized.strip() in agent_phrases:
                request = ""
            self.add_agent_workspace_window(
                request,
                auto_start=bool(request and last_project_path()),
            )
            return True
        if has("world map", "digital twin", "my world"):
            self.add_world_map_window(); return True
        if has("future self", "future simulator", "simulate future"):
            self.add_future_self_window(); return True
        mission_phrases = (
            "mission builder", "build project", "create project", "make project",
            "generate a random app", "generate random app", "make a random app", "make random app",
            "create a random app", "create random app",
            "generate an app", "generate app", "build an app", "build app",
            "create an app", "create app",
        )
        if has(*mission_phrases) or project_generation_intent(normalized):
            lower_raw = raw_command.lower()
            request = ""
            for phrase in mission_phrases:
                position = lower_raw.find(phrase)
                if position >= 0:
                    request = raw_command[position + len(phrase):].strip(" :-,.")
                    break
            if not request and not any(phrase in lower_raw for phrase in mission_phrases):
                request = raw_command.strip()
            random_request = random_app_intent(normalized) or has(
                "generate a random app", "generate random app", "make a random app", "make random app",
                "create a random app", "create random app",
            )
            if random_request:
                request = (
                    "Create one small, original and useful random desktop app. Choose the idea yourself. "
                    "Make it complete, runnable on Windows, visually clear, and include a README with exact run instructions."
                )
            self.add_mission_builder_window(request, auto_start=bool(request)); return True
        if has("zip builder", "make zip", "build zip", "create zip", "package files"):
            self.add_zip_builder_window(); return True
        if has("self edit", "self editor", "edit yourself", "change yourself"):
            self.add_self_edit_window(); return True
        if has("windows manager", "window manager"):
            self.add_windows_manager(); return True
        if has("notes", "note"):
            self.add_text_window(); return True
        if has("calculator widget"):
            self.add_calculator_window(); return True
        if has("calendar"):
            self.add_calendar_window(); return True
        if has("weather"):
            self.add_weather_window(); return True
        if has("clock"):
            self.add_clock_window(); return True
        if has("video"):
            self.add_video_window(); return True
        if has("music"):
            self.add_music_window(); return True
        if has("phone"):
            self.add_phone_window(); return True
        if has("air menu", "air_menu"):
            self.open_air_menu(); return True
        if has("close window", "close_window"):
            if self.active_window:
                self.active_window.close(); return True
            return False
        if has("maximize"):
            if self.active_window:
                self.active_window.maximize_window(); return True
            return False
        if has("minimize"):
            if self.active_window:
                self.active_window.minimize_window(); return True
            return False
        if has("restore"):
            if self.active_window:
                self.active_window.restore_window(); return True
            return False
        if has("snap left"):
            if self.active_window:
                self.active_window.snap_left(); return True
            return False
        if has("snap right"):
            if self.active_window:
                self.active_window.snap_right(); return True
            return False
        if has("rotate"):
            if self.active_window:
                self.active_window.rotate_by(15); return True
            return False
        if has("camera off", "disable camera"):
            self.show_camera = False; self.settings.show_camera = False; self.settings.save(); return True
        if has("camera on", "enable camera"):
            self.show_camera = True; self.settings.show_camera = True; self.settings.save(); return True
        if has("save workspace", "save_workspace"):
            self.save_workspace(show_message=not silent); return True
        if has("load workspace"):
            self.load_workspace(); return True
        if has("next monitor", "next_monitor"):
            self.window().move_to_next_monitor(); return True
        return False

    def _custom_alias_command(self, normalized: str) -> str:
        aliases = load_self_edit_config().get("aliases", "")
        for line in aliases.splitlines():
            if "=>" not in line:
                continue
            phrase, target = [part.strip().lower() for part in line.split("=>", 1)]
            if phrase and target and phrase in normalized:
                return target
        return ""

    def screen_context(self) -> str:
        active = self.active_window.title() if self.active_window else "None"
        titles = ", ".join(window.title() for window in self.windows[-12:]) or "None"
        system_windows = self.windows_controller.list_windows()[:10]
        real_titles = ", ".join(row["title"] for row in system_windows) if system_windows else "Unavailable"
        return (
            f"HoloDesk active window: {active}\n"
            f"HoloDesk open widgets: {titles}\n"
            f"Real Windows applications: {real_titles}\n"
            f"Hand gesture: {self.gesture_text}\n"
            f"Camera: {'on' if self.camera_ok else 'unavailable'}\n"
            f"Eye tracking: {'on' if self.eye_tracking_enabled else 'off'}"
        )

    def save_workspace(self, show_message: bool = True) -> None:
        payload = {
            "version": APP_VERSION,
            "saved_at": datetime.now().isoformat(),
            "windows": [window.serialize() for window in self.windows if window.isVisible()],
        }
        WORKSPACE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if show_message:
            QMessageBox.information(self, APP_NAME, f"Workspace saved:\n{WORKSPACE_PATH}")

    def load_workspace(self) -> None:
        if not WORKSPACE_PATH.exists():
            QMessageBox.information(self, APP_NAME, "No saved workspace found.")
            return
        try:
            payload = json.loads(WORKSPACE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not read workspace: {exc}")
            return
        for window in list(self.windows):
            window.close()
        for item in payload.get("windows", []):
            self.restore_item(item)

    def restore_item(self, item: dict[str, Any]) -> None:
        kind = item.get("type", "text")
        data = item.get("data", {})
        geometry = item.get("geometry")
        window: Optional[VirtualWindow] = None
        if kind in {"text", "notes"}:
            window = self.add_text_window(item.get("title", "Notes"), data.get("text", ""), geometry)
        elif kind == "image" and Path(data.get("path", "")).exists():
            window = self.add_image_window(data.get("path", ""), geometry)
        elif kind == "browser":
            window = self.add_browser_window(data.get("url", "https://www.google.com"), geometry)
        elif kind == "video": window = self.add_video_window(geometry)
        elif kind == "music": window = self.add_music_window(geometry)
        elif kind == "calculator": window = self.add_calculator_window(geometry)
        elif kind == "calendar": window = self.add_calendar_window(geometry)
        elif kind == "weather": window = self.add_weather_window(geometry)
        elif kind == "clock": window = self.add_clock_window(geometry)
        elif kind == "ai": window = self.add_ai_window(geometry)
        elif kind == "world_map": window = self.add_world_map_window(geometry)
        elif kind == "location": window = self.add_location_window(geometry)
        elif kind == "google_location":
            self.open_google_location()
            window = self.active_window
        elif kind == "future_self": window = self.add_future_self_window(geometry)
        elif kind == "mission_builder": window = self.add_mission_builder_window(data.get("request", ""), geometry)
        elif kind == "agent_workspace": window = self.add_agent_workspace_window(data.get("request", ""), geometry)
        elif kind == "zip_builder": window = self.add_zip_builder_window(geometry)
        elif kind == "self_edit": window = self.add_self_edit_window(geometry)
        elif kind == "windows_manager": window = self.add_windows_manager(geometry)
        elif kind == "voice": window = self.add_voice_window(geometry)
        elif kind == "phone": window = self.add_phone_window(geometry)
        elif kind == "settings": window = self.add_settings_window(geometry)
        elif kind == "control_center":
            window = self.place_window(VirtualWindow(self, "JARVIS Control Center", ControlCenter(self), 650, 500, "control_center"), geometry)
        if window:
            rotation = safe_int(item.get("rotation"))
            if rotation:
                window.rotate_by(rotation)
            if item.get("maximized"):
                window.maximize_window()

    def paintEvent(self, event) -> None:
        self.frame_counter += 1
        elapsed = time.perf_counter() - self.fps_started
        if elapsed >= 1.0:
            self.ui_fps = self.frame_counter / elapsed
            self.frame_counter = 0
            self.fps_started = time.perf_counter()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient_top = QColor("#07141E")
        gradient_bottom = QColor("#02070C")
        painter.fillRect(self.rect(), gradient_bottom)

        if self.show_camera and not self.camera_pixmap.isNull():
            painter.setOpacity(0.20)
            x = (self.width() - self.camera_pixmap.width()) // 2
            y = 70 + (max(1, self.height() - 70) - self.camera_pixmap.height()) // 2
            painter.drawPixmap(x, y, self.camera_pixmap)
            painter.setOpacity(1.0)

        painter.fillRect(QRect(0, 70, self.width(), self.height() - 70), QColor(4, 12, 18, 120))
        painter.setPen(QPen(QColor(70, 204, 235, 30), 1))
        for x in range(0, self.width(), 54):
            painter.drawLine(x, 70, x, self.height())
        for y in range(70, self.height(), 54):
            painter.drawLine(0, y, self.width(), y)

        for particle in self.particles:
            x = int(particle["x"] * self.width())
            y = int(70 + particle["y"] * max(1, self.height() - 70))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(103, 220, 250, 85))
            painter.drawEllipse(QPoint(x, y), int(particle["r"]), int(particle["r"]))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(5, 16, 25, 248)))
        painter.drawRect(0, 0, self.width(), 70)
        painter.setPen(QColor("#8BE9FF"))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(13)
        painter.setFont(font)
        painter.drawText(22, 31, "J.A.R.V.I.S. / HOLODESK")
        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#6FB8C9"))
        painter.drawText(22, 52, f"REACTOR CONSOLE • {APP_VERSION}")
        painter.setPen(QColor("#C5E9F2"))
        painter.drawText(270, 31, f"Gesture: {self.gesture_text}")
        painter.setPen(QColor("#6FA6B3"))
        painter.drawText(270, 51, self.hand_detail[:70])
        painter.setPen(QColor("#72CFE8"))
        painter.drawText(
            max(500, self.width() - 650), 44,
            f"UI {self.ui_fps:.0f} FPS • CAM {self.camera_fps:.0f} • HAND {self.tracking_fps:.0f} • GPU/Qt {'ON' if WEBENGINE_AVAILABLE else 'BASE'}"
        )

        if self.pointer.x() >= 0:
            painter.setPen(QPen(QColor("#8BE9FF"), 2))
            painter.setBrush(QBrush(QColor(139, 233, 255, 40)))
            painter.drawEllipse(self.pointer, 18, 18)
            painter.setBrush(QBrush(QColor("#8BE9FF")))
            painter.drawEllipse(self.pointer, 4, 4)
        if self.eye_tracking_enabled and self.eye_pointer.x() >= 0:
            painter.setPen(QPen(QColor("#FFDD7A"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.eye_pointer, 12, 8)
            painter.drawLine(self.eye_pointer.x() - 17, self.eye_pointer.y(), self.eye_pointer.x() + 17, self.eye_pointer.y())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "dashboard"):
            self.dashboard.setGeometry(10, 76, max(900, self.width() - 20), max(540, self.height() - 86))
            self.dashboard.lower()

    def close_all_resources(self) -> None:
        self.stop_companion()
        if self.tracking_worker is not None:
            self.tracking_worker.stop()
        if self.camera_worker is not None:
            self.camera_worker.stop()
        if self.tracking_worker is not None:
            self.tracking_worker.join(timeout=2.0)
        if self.camera_worker is not None:
            self.camera_worker.join(timeout=2.0)


class ControlCenter(QWidget):
    def __init__(self, canvas: HoloCanvas):
        super().__init__()
        self.canvas = canvas
        layout = QVBoxLayout(self)
        title = QLabel("JARVIS CONTROL CENTER")
        title.setStyleSheet("color:#8BE9FF;font-size:18px;font-weight:800;padding:6px;")
        layout.addWidget(title)
        grid = QGridLayout()
        items = [
            ("Agent Workspace", canvas.add_agent_workspace_window),
            ("Mission Builder", canvas.add_mission_builder_window),
            ("Self Edit", canvas.add_self_edit_window),
            ("World Map", canvas.add_world_map_window), ("Future Self", canvas.add_future_self_window),
            ("ZIP Builder", canvas.add_zip_builder_window),
            ("Windows", canvas.add_windows_manager), ("AI", canvas.add_ai_window),
            ("Browser", canvas.add_browser_window), ("Notes", canvas.add_text_window),
            ("Video", canvas.add_video_window), ("Music", canvas.add_music_window),
            ("Calculator", canvas.add_calculator_window), ("Calendar", canvas.add_calendar_window),
            ("Weather", canvas.add_weather_window), ("Clock", canvas.add_clock_window),
            ("Voice", canvas.add_voice_window), ("Phone", canvas.add_phone_window),
        ]
        for index, (label, callback) in enumerate(items):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, cb=callback: cb())
            grid.addWidget(button, index // 3, index % 3)
        layout.addLayout(grid)
        options = QHBoxLayout()
        self.eye = QCheckBox("Eye tracking")
        self.eye.setChecked(canvas.eye_tracking_enabled)
        self.eye.toggled.connect(canvas.set_eye_tracking)
        self.eye_cursor = QCheckBox("Eye cursor")
        self.eye_cursor.setChecked(canvas.eye_cursor_enabled)
        self.eye_cursor.toggled.connect(canvas.set_eye_cursor)
        self.performance = QCheckBox("Performance mode")
        self.performance.setChecked(canvas.settings.performance_mode)
        self.performance.toggled.connect(canvas.set_performance_mode)
        options.addWidget(self.eye)
        options.addWidget(self.eye_cursor)
        options.addWidget(self.performance)
        layout.addLayout(options)
        workspace = QHBoxLayout()
        save = QPushButton("Save Workspace")
        load = QPushButton("Load Workspace")
        settings = QPushButton("Settings")
        save.clicked.connect(lambda: canvas.save_workspace())
        load.clicked.connect(lambda: canvas.load_workspace())
        settings.clicked.connect(lambda: canvas.add_settings_window())
        workspace.addWidget(save)
        workspace.addWidget(load)
        workspace.addWidget(settings)
        layout.addLayout(workspace)
        self.setStyleSheet(button_style() + "QCheckBox{color:#DDF7FF;padding:8px;}")


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle(f"{APP_NAME} — Reactor Console")
        self.resize(1380, 860)
        self.setMinimumSize(1040, 680)
        self.canvas = HoloCanvas(settings)
        self.setCentralWidget(self.canvas)
        self.setStyleSheet("QMainWindow{background:#03080D;}QToolTip{color:#EAFBFF;background:#10222D;border:1px solid #4EA7C1;}")
        self.create_top_controls()
        self.create_menu()
        self.auto_voice = AutoVoiceController(self.canvas, self, start_immediately=False)
        self.mini_voice = MiniJarvis()
        self._mini_was_maximized = False
        self.mini_voice.restore_requested.connect(self.restore_from_mini)
        self.mini_voice.listening_toggled.connect(self.auto_voice.set_listening_enabled)
        self.mini_voice.exit_requested.connect(self.close)
        self.screen_agent = ScreenAgent(self.canvas.ai_client, self)
        self.auto_voice.screen_agent = self.screen_agent
        self.screen_agent.status.connect(self.mini_voice.set_screen_status)
        self.screen_agent.reply.connect(self.auto_voice._speak)
        self.mini_voice.screen_toggled.connect(self.toggle_screen_access)
        self.mini_voice.listening_toggled.connect(lambda enabled: self.sync_screen_access())
        self.auto_voice.status_changed.connect(self._voice_status_changed)
        self.startup_sound_worker: Optional[AudioFileWorker] = None
        self.startup_speaker: Optional[SpeechWorker] = None
        QTimer.singleShot(300, self._start_startup_sequence)

    def _start_startup_sequence(self) -> None:
        if self.auto_voice._closing:
            return
        sound_path = resource_path("assets", "jarvis_startup.wav")
        self._voice_status_changed("JARVIS • INITIALIZING")
        if not sound_path.exists():
            self._speak_startup_greeting()
            return
        self.startup_sound_worker = AudioFileWorker(sound_path, self)
        self.startup_sound_worker.failed.connect(
            lambda message: self._voice_status_changed(f"STARTUP SOUND • {message[:90]}")
        )
        self.startup_sound_worker.completed.connect(self._speak_startup_greeting)
        self.startup_sound_worker.finished.connect(self._clear_startup_sound_worker)
        self.startup_sound_worker.start()

    def _clear_startup_sound_worker(self) -> None:
        self.startup_sound_worker = None

    def _speak_startup_greeting(self) -> None:
        if self.auto_voice._closing:
            return
        if self.startup_speaker is not None and self.startup_speaker.isRunning():
            return
        self._voice_status_changed("JARVIS • ONLINE")
        self.startup_speaker = SpeechWorker("Welcome home, sir. JARVIS is online.")
        self.startup_speaker.engine_used.connect(
            lambda engine: self._voice_status_changed(f"JARVIS • {engine.upper()}")
        )
        self.startup_speaker.failed.connect(
            lambda message: self._voice_status_changed(f"VOICE ERROR • {message[:90]}")
        )
        self.startup_speaker.finished_speaking.connect(self._finish_startup_sequence)
        self.startup_speaker.finished.connect(self._clear_startup_speaker)
        self.startup_speaker.start()

    def _clear_startup_speaker(self) -> None:
        self.startup_speaker = None

    def _finish_startup_sequence(self) -> None:
        self._voice_status_changed("VOICE • READY")
        QTimer.singleShot(350, self.auto_voice._start_listening)

    def _voice_status_changed(self, message: str) -> None:
        if hasattr(self, 'mini_voice'):
            self.mini_voice.set_voice_status(message, self.auto_voice.enabled)
        # Keep the current Reactor layout unchanged; surface voice state in the
        # title bar and, when available, in the Reactor activity panel.
        self.setWindowTitle(f"{APP_NAME} — Reactor Console — {message}")
        try:
            reactor = getattr(self.canvas, "reactor_console", None)
            if reactor is not None and hasattr(reactor, "log"):
                reactor.log("VOICE", message)
        except Exception:
            pass

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(self, 'mini_voice'):
            if self.isMinimized():
                self._mini_was_maximized = bool(event.oldState() & Qt.WindowState.WindowMaximized)
                self.mini_voice.show_near(self.screen())
                if hasattr(self, 'screen_agent'):
                    QTimer.singleShot(0, self.sync_screen_access)
            else:
                self.mini_voice.hide()
                if hasattr(self, 'screen_agent'):
                    self.screen_agent.disable()

    def sync_screen_access(self) -> None:
        if self.isMinimized() and self.auto_voice.enabled and not self.auto_voice._closing:
            self.screen_agent.enable()
        else:
            self.screen_agent.disable()

    def toggle_screen_access(self, enabled: bool) -> None:
        if enabled:
            self.screen_agent.granted = None
            self.sync_screen_access()
        else:
            self.screen_agent.granted = False
            self.screen_agent.disable()

    def restore_from_mini(self) -> None:
        self.mini_voice.hide()
        if self._mini_was_maximized:
            self.showMaximized()
        else:
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def create_top_controls(self) -> None:
        self.controls = QFrame(self.canvas)
        self.controls.setGeometry(self.width() - 440, 8, 420, 54)
        self.controls.setStyleSheet("QFrame{background:rgba(12,33,45,225);border:1px solid rgba(90,220,255,80);border-radius:14px;}" + button_style())
        layout = QHBoxLayout(self.controls)
        layout.setContentsMargins(7, 7, 7, 7)
        for label, callback in [
            ("JARVIS", self.open_control_center),
            ("Air Menu", self.canvas.open_air_menu),
            ("Camera", self.toggle_camera),
            ("Save", self.canvas.save_workspace),
            ("Monitor", self.move_to_next_monitor),
        ]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, cb=callback: cb())
            layout.addWidget(button)
        self.controls.raise_()

    def create_menu(self) -> None:
        app_menu = self.menuBar().addMenu("HoloDesk")
        actions = [
            ("Control Center", self.open_control_center),
            ("Save Workspace", self.canvas.save_workspace),
            ("Load Workspace", self.canvas.load_workspace),
            ("Settings", self.canvas.add_settings_window),
            ("Exit", self.close),
        ]
        for label, callback in actions:
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, cb=callback: cb())
            app_menu.addAction(action)
        window_menu = self.menuBar().addMenu("Active Window")
        for label, callback in [
            ("Maximize", lambda: self.canvas.active_window.maximize_window() if self.canvas.active_window else None),
            ("Restore", lambda: self.canvas.active_window.restore_window() if self.canvas.active_window else None),
            ("Snap Left", lambda: self.canvas.active_window.snap_left() if self.canvas.active_window else None),
            ("Snap Right", lambda: self.canvas.active_window.snap_right() if self.canvas.active_window else None),
            ("Rotate +15°", lambda: self.canvas.active_window.rotate_by(15) if self.canvas.active_window else None),
            ("Close", lambda: self.canvas.active_window.close() if self.canvas.active_window else None),
        ]:
            action = QAction(label, self)
            action.triggered.connect(lambda checked=False, cb=callback: cb())
            window_menu.addAction(action)
        self.menuBar().setStyleSheet("QMenuBar{background:#07141E;color:#DDF7FF;}QMenuBar::item:selected{background:#17495D;}QMenu{background:#0A1A25;color:#DDF7FF;border:1px solid #28758E;}QMenu::item:selected{background:#225C70;}")

    def open_control_center(self) -> None:
        self.canvas.place_window(VirtualWindow(self.canvas, "JARVIS Control Center", ControlCenter(self.canvas), 650, 500, "control_center"))

    def toggle_camera(self) -> None:
        self.canvas.show_camera = not self.canvas.show_camera
        self.settings.show_camera = self.canvas.show_camera
        self.settings.save()

    def move_to_next_monitor(self) -> None:
        screens = QGuiApplication.screens()
        if len(screens) <= 1:
            return
        current = self.screen()
        try:
            index = screens.index(current)
        except ValueError:
            index = 0
        target = screens[(index + 1) % len(screens)]
        geo = target.availableGeometry()
        self.move(geo.topLeft() + QPoint(40, 40))
        self.resize(min(self.width(), geo.width() - 80), min(self.height(), geo.height() - 80))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "controls"):
            self.controls.setGeometry(self.width() - 440, 8, 420, 54)
        for window in self.canvas.windows:
            if window.maximized:
                window.maximize_window()

    def closeEvent(self, event) -> None:
        if hasattr(self, 'mini_voice'):
            self.mini_voice.hide()
        if hasattr(self, 'screen_agent'):
            self.screen_agent.disable()
        try:
            if hasattr(self, "auto_voice"):
                self.auto_voice.stop()
        except Exception:
            pass
        screen_worker = getattr(getattr(self, 'screen_agent', None), 'worker', None)
        if screen_worker is not None and screen_worker.isRunning() and not screen_worker.wait(100):
            event.ignore()
            QTimer.singleShot(300, self.close)
            return
        for name in ('worker', 'ai_worker', 'speaker'):
            worker = getattr(self.auto_voice, name, None)
            if worker is not None and worker.isRunning() and not worker.wait(100):
                event.ignore()
                QTimer.singleShot(300, self.close)
                return
        for name in ("startup_sound_worker", "startup_speaker"):
            try:
                worker = getattr(self, name, None)
                if worker is not None and worker.isRunning():
                    worker.wait(15000)
            except Exception:
                pass
        try:
            self.canvas.save_workspace(show_message=False)
        except Exception:
            pass
        self.canvas.close_all_resources()
        super().closeEvent(event)


def enable_windows_dpi_awareness() -> None:
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main() -> None:
    enable_windows_dpi_awareness()
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setFont(QFont("Segoe UI", 10))
    settings = AppSettings.load()
    window = MainWindow(settings)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

