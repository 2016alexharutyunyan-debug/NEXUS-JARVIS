"""Validated natural-language plans for JARVIS Agent Mode."""
import re


ALLOWED_COMMANDS = {
    "open chrome", "open notepad", "open calculator", "open file explorer",
    "open downloads", "open documents", "open google", "open telegram",
    "open browser", "open ai", "world map", "my location", "google maps",
    "notes", "calendar", "weather", "clock", "video", "music", "phone",
    "volume up", "volume down", "toggle mute", "play pause", "next track",
    "previous track", "show desktop", "switch window", "new tab", "close tab",
    "next tab", "refresh page", "scroll down", "scroll up", "close window",
    "minimize window", "maximize window", "restore window", "snap left",
    "snap right", "save workspace", "load workspace",
}

KNOWN_WEBSITES = {
    "google", "youtube", "gmail", "github", "facebook", "instagram",
    "tiktok", "twitter", "x",
}

ACTION_STARTS = (
    "open ", "start ", "launch ", "go to ", "search ", "find ", "show ",
    "create ", "make ", "build ", "edit ", "change ", "fix ", "write ",
    "add ", "save ", "load ", "close ", "minimize ", "maximize ", "restore ",
    "click ", "double click ", "type ", "scroll ", "press ", "read the screen",
)


AGENT_SYSTEM_PROMPT = '''You are the safe planning layer for JARVIS on Windows.
Return only one JSON object with this schema:
{"reply":"short English response","actions":[{"type":"..."}]}
Use at most 3 actions. Allowed actions are:
- {"type":"command","command":"one exact allowed command"}
- {"type":"search","query":"Google search words"}
- {"type":"website","name":"google|youtube|gmail|github|facebook|instagram|tiktok|twitter|x"}
- {"type":"note","title":"short title","text":"note text"}
- {"type":"screen","request":"one visible UI action"}
- {"type":"build","request":"small project description"}
- {"type":"edit","request":"change requested for the last project"}
Exact allowed command values:
''' + ", ".join(sorted(ALLOWED_COMMANDS)) + '''.
Questions and conversation are not action plans: return an empty actions list and a helpful reply.
Never plan shell commands, arbitrary programs, deletion, purchases, messages, account changes,
credentials, security changes, or background persistence. Use screen only for a user-requested
visible action; every screen action is separately reviewed. Do not claim an action already ran.'''


def normalize_agent_text(text):
    return " ".join(re.sub(r"[^a-z0-9\s]", " ", (text or "").lower()).split())


def _strip_agent_prefix(text):
    prefixes = ("hey jarvis ", "jarvis ", "please ", "can you ", "could you ", "would you ")
    while True:
        prefix = next((item for item in prefixes if text.startswith(item)), None)
        if prefix is None:
            return text
        text = text[len(prefix):].strip()


def looks_like_agent_request(text):
    text = _strip_agent_prefix(normalize_agent_text(text))
    return text.startswith(ACTION_STARTS)


def local_agent_plan(text):
    """Plan common actions locally so everyday commands do not wait for an API."""
    clean = _strip_agent_prefix(normalize_agent_text(text))
    if not clean:
        return None
    clauses = re.split(
        r"\s+and\s+(?=(?:open|start|launch|go to|search|find|show|create|make|write|add|build|edit|change|fix|click|double click|type|scroll|press)\b)",
        clean,
    )
    if len(clauses) > 3:
        return None

    actions = []
    for clause in clauses:
        clause = clause.strip()
        direct = clause
        aliases = {
            "open my browser": "open browser",
            "open the browser": "open browser",
            "show my location": "my location",
            "open my location": "my location",
            "open google maps": "google maps",
            "show google maps": "google maps",
        }
        direct = aliases.get(direct, direct)
        if direct in ALLOWED_COMMANDS:
            actions.append({"type": "command", "command": direct})
            continue

        website = re.fullmatch(r"(?:open|start|launch|go to|show) (?:the )?(.+)", clause)
        if website and website.group(1) in KNOWN_WEBSITES:
            actions.append({"type": "website", "name": website.group(1)})
            continue

        search = re.fullmatch(r"(?:search|find|google)(?: google)?(?: for)? (.+?)(?: (?:in|on) google)?", clause)
        if search and search.group(1).strip():
            actions.append({"type": "search", "query": search.group(1).strip()})
            continue

        note = re.fullmatch(r"(?:create|make|write|add) (?:a )?note(?: called| titled)?\s*(.*)", clause)
        if note:
            value = note.group(1).strip(" :")
            if not value:
                return None
            title, body = "Note", value
            titled = re.fullmatch(r"(.+?)\s+with\s+(.+)", value)
            if titled:
                title, body = titled.group(1).strip().title(), titled.group(2).strip()
            actions.append({"type": "note", "title": title, "text": body})
            continue

        build = re.fullmatch(r"(?:create|make|build) (?:a |an )?(?:project|app)\s*(.*)", clause)
        if build:
            request = build.group(1).strip(" :") or "Create a small useful desktop app."
            actions.append({"type": "build", "request": request})
            continue

        edit = re.fullmatch(r"(?:edit|change|fix|update) (?:my |the )?(?:last )?(?:project|app)\s*(.*)", clause)
        if edit:
            request = edit.group(1).strip(" :")
            if not request:
                return None
            actions.append({"type": "edit", "request": request})
            continue

        if clause.startswith(("click ", "double click ", "type ", "scroll ", "press ", "read the screen")):
            actions.append({"type": "screen", "request": clause})
            continue
        return None

    if not actions:
        return None
    return validate_agent_plan({"reply": "Done.", "actions": actions})


def validate_agent_plan(data):
    if not isinstance(data, dict):
        raise ValueError("Agent response is not an object.")
    reply = data.get("reply", "")
    actions = data.get("actions", [])
    if not isinstance(reply, str) or not isinstance(actions, list) or len(actions) > 3:
        raise ValueError("Agent response has an invalid shape.")
    clean_actions = []
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError("Agent action is invalid.")
        kind = action.get("type")
        clean = {"type": kind}
        if kind == "command":
            command = normalize_agent_text(action.get("command", ""))
            if command not in ALLOWED_COMMANDS:
                raise ValueError("Agent command is not allowed.")
            clean["command"] = command
        elif kind == "website":
            name = normalize_agent_text(action.get("name", ""))
            if name not in KNOWN_WEBSITES:
                raise ValueError("Agent website is not allowed.")
            clean["name"] = name
        elif kind in {"search", "screen", "build", "edit"}:
            field = "query" if kind == "search" else "request"
            value = str(action.get(field, "")).strip()
            limit = 240 if kind in {"search", "screen"} else 1000
            if not value or len(value) > limit:
                raise ValueError("Agent action text is invalid.")
            clean[field] = value
        elif kind == "note":
            title = str(action.get("title", "Note")).strip()[:80] or "Note"
            value = str(action.get("text", "")).strip()
            if not value or len(value) > 2000:
                raise ValueError("Agent note is invalid.")
            clean.update(title=title, text=value)
        else:
            raise ValueError("Agent action type is not allowed.")
        clean_actions.append(clean)
    return {"reply": reply.strip()[:500], "actions": clean_actions}
