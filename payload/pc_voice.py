"""Explicit English commands for Windows desktop control."""
import re


COMMANDS = {
    "volume up": ("keys", (0xAF,), "Volume increased."),
    "turn up the volume": ("keys", (0xAF,), "Volume increased."),
    "volume down": ("keys", (0xAE,), "Volume decreased."),
    "turn down the volume": ("keys", (0xAE,), "Volume decreased."),
    "toggle mute": ("keys", (0xAD,), "Mute toggled."),
    "play pause": ("keys", (0xB3,), "Playback toggled."),
    "pause music": ("keys", (0xB3,), "Playback toggled."),
    "next track": ("keys", (0xB0,), "Next track."),
    "previous track": ("keys", (0xB1,), "Previous track."),
    "show desktop": ("keys", (0x5B, 0x44), "Desktop toggled."),
    "switch window": ("keys", (0x12, 0x09), "Window switched."),
    "next window": ("keys", (0x12, 0x09), "Window switched."),
    "new tab": ("keys", (0x11, 0x54), "New tab requested."),
    "close tab": ("keys", (0x11, 0x57), "Close tab requested."),
    "next tab": ("keys", (0x11, 0x09), "Next tab."),
    "refresh page": ("keys", (0x74,), "Refresh requested."),
    "scroll down": ("keys", (0x22,), "Scrolled down."),
    "scroll up": ("keys", (0x21,), "Scrolled up."),
    "open file explorer": ("launch", "explorer.exe", "File Explorer opened."),
    "open explorer": ("launch", "explorer.exe", "File Explorer opened."),
    "open chrome": ("launch", "chrome", "Chrome opened."),
    "open notepad": ("launch", "notepad.exe", "Notepad opened."),
    "open calculator": ("launch", "calc.exe", "Calculator opened."),
    "open downloads": ("folder", "Downloads", "Downloads opened."),
    "open documents": ("folder", "Documents", "Documents opened."),
    "close window": ("window", "close", "Close requested."),
    "minimize window": ("window", "minimize", "Window minimized."),
    "maximize window": ("window", "maximize", "Window maximized."),
    "restore window": ("window", "restore", "Window restored."),
    "snap left": ("window", "snap_left", "Window moved left."),
    "snap right": ("window", "snap_right", "Window moved right."),
}


def parse_pc_command(text):
    text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    text = " ".join(text.split())
    prefixes = ("hey jarvis ", "jarvis ", "can you ", "please ")
    while True:
        prefix = next((prefix for prefix in prefixes if text.startswith(prefix)), None)
        if prefix is None:
            break
        text = text[len(prefix):]
    if text.endswith(" please"):
        text = text[:-7]
    return COMMANDS.get(text)
