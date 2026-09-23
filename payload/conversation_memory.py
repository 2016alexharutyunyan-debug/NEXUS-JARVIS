"""Small, local and bounded conversation memory for JARVIS."""
import json
import re
from pathlib import Path


SENSITIVE_LINE = re.compile(
    r"(?i)\b(password|passcode|api[ _-]?key|secret|access[ _-]?token|bearer[ _-]?token)\b\s*(?:is\b|[:=])"
)
KEY_LIKE_VALUE = re.compile(r"\b(?:AIza[0-9A-Za-z_-]{20,}|sk-[0-9A-Za-z_-]{16,})\b")


def memory_safe_text(text, limit=4000):
    lines = []
    for line in str(text or "").splitlines() or [str(text or "")]:
        if SENSITIVE_LINE.search(line):
            lines.append("[sensitive information not saved]")
        else:
            lines.append(KEY_LIKE_VALUE.sub("[secret not saved]", line))
    return "\n".join(lines).strip()[:limit]


class ConversationMemory:
    def __init__(self, path, limit_messages=40):
        self.path = Path(path)
        self.limit_messages = max(2, int(limit_messages))

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            raw = data.get("messages", []) if isinstance(data, dict) else []
        except Exception:
            return []
        messages = []
        for item in raw:
            if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
                continue
            content = memory_safe_text(item.get("content", ""))
            if content:
                messages.append({"role": item["role"], "content": content})
        return messages[-self.limit_messages:]

    def save(self, messages):
        clean = []
        for item in list(messages)[-self.limit_messages:]:
            if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
                continue
            content = memory_safe_text(item.get("content", ""))
            if content:
                clean.append({"role": item["role"], "content": content})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({"version": 1, "messages": clean}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def clear(self):
        self.path.unlink(missing_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.unlink(missing_ok=True)
