"""Explicit English commands for Windows desktop control."""
import re
from urllib.parse import quote_plus


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
    "open google": ("url", "https://www.google.com", "Google opened."),
    "open telegram": ("url", "tg://", "Telegram opened."),
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


SIMPLE_APP_ALIASES = {
    "google": "open google",
    "gogle": "open google",
    "gugle": "open google",
    "go google": "open google",
    "go to google": "open google",
    "start google": "open google",
    "in google": "open google",
    "on google": "open google",
    "telegram": "open telegram",
    "tele gram": "open telegram",
    "telegramm": "open telegram",
    "start telegram": "open telegram",
    "go telegram": "open telegram",
    "go to telegram": "open telegram",
    "in telegram": "open telegram",
    "on telegram": "open telegram",
}


KNOWN_WEBSITES = {
    "youtube": "https://www.youtube.com",
    "you tube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "git hub": "https://github.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "tiktok": "https://www.tiktok.com",
    "tik tok": "https://www.tiktok.com",
    "twitter": "https://x.com",
    "x": "https://x.com",
}


def _browser_command(text):
    direct = re.fullmatch(r"(?:open|start|go to|in|on) (.+?)(?: (?:in|on) google)?", text)
    if direct:
        target = direct.group(1).strip()
        if target in KNOWN_WEBSITES:
            return "url", KNOWN_WEBSITES[target], f"{target.title()} opened."
        if text.endswith((" in google", " on google")):
            return "url", f"https://www.google.com/search?q={quote_plus(target)}", f"Searching Google for {target}."

    search = re.fullmatch(r"(?:search|find|google)(?: for)? (.+?)(?: (?:in|on) google)?", text)
    if search:
        query = search.group(1).strip()
        if query and not query.startswith(("and ", "or ")):
            return "url", f"https://www.google.com/search?q={quote_plus(query)}", f"Searching Google for {query}."
    return None


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
    text = re.sub(r"\b(?:gogle|gugle)\b", "google", text)
    text = re.sub(r"\btelegramm\b", "telegram", text)
    text = text.replace("tele gram", "telegram")
    text = SIMPLE_APP_ALIASES.get(text, text)
    return COMMANDS.get(text) or _browser_command(text)
