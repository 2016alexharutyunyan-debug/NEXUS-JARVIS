from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional


EMERGENCY_NUMBERS = {"101", "102", "103", "104", "112", "911"}


@dataclass(frozen=True)
class PhoneAction:
    kind: str
    number: str
    message: str = ""


def normalize_phone_number(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValueError("Enter a phone number first.")
    if not re.fullmatch(r"\+?[\d\s().-]+", raw):
        raise ValueError("Use a phone number made of digits, with an optional leading plus sign.")
    digits = re.sub(r"\D", "", raw)
    if not 3 <= len(digits) <= 16:
        raise ValueError("The phone number must contain 3 to 16 digits.")
    if digits in EMERGENCY_NUMBERS:
        raise ValueError("Emergency calls are blocked in JARVIS. Use your phone directly in an emergency.")
    return f"+{digits}" if raw.startswith("+") else digits


def parse_phone_action(text: str) -> Optional[PhoneAction]:
    command = " ".join(text.strip().split())
    if not command:
        return None

    call_match = re.fullmatch(
        r"(?:please\s+)?(?:call|dial|phone)\s+(?:number\s+)?(?P<number>\+?[\d\s().-]{3,30})",
        command,
        flags=re.IGNORECASE,
    )
    if call_match:
        return PhoneAction("call", normalize_phone_number(call_match.group("number")))

    text_match = re.fullmatch(
        r"(?:please\s+)?(?:text|message)\s+(?:number\s+)?"
        r"(?P<number>\+?[\d\s().-]{3,30})\s+(?:saying\s+)?(?P<message>[^\d\s().+\-].*)",
        command,
        flags=re.IGNORECASE,
    )
    if not text_match:
        text_match = re.fullmatch(
            r"(?:please\s+)?send\s+(?:an?\s+)?(?:sms|text|message)\s+to\s+(?:number\s+)?"
            r"(?P<number>\+?[\d\s().-]{3,30})\s+(?:saying\s+)?(?P<message>[^\d\s().+\-].*)",
            command,
            flags=re.IGNORECASE,
        )
    if text_match:
        message = text_match.group("message").strip()
        if not message:
            raise ValueError("Say or type the message after the phone number.")
        return PhoneAction("text", normalize_phone_number(text_match.group("number")), message)
    return None


def call_uri(number: str) -> str:
    return f"tel:{normalize_phone_number(number)}"


def sms_uri(number: str, message: str) -> str:
    clean_message = message.strip()
    if not clean_message:
        raise ValueError("Enter a message first.")
    query = urllib.parse.urlencode({"body": clean_message}, quote_via=urllib.parse.quote)
    return f"sms:{normalize_phone_number(number)}?{query}"
