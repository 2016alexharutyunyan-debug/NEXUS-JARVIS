from __future__ import annotations

import json
import urllib.error
import urllib.request


def phone_agent_request(host: str, token: str, action: str, number: str, message: str = "") -> str:
    clean_host = host.strip().removeprefix("http://").removeprefix("https://").rstrip("/")
    clean_token = token.strip()
    if not clean_host:
        raise ValueError("Enter the phone IP shown by JARVIS Phone Agent.")
    if not clean_token:
        raise ValueError("Enter the pairing code shown by JARVIS Phone Agent.")
    if action not in {"call", "sms"}:
        raise ValueError("Unsupported phone action.")
    payload = json.dumps({"number": number, "message": message}).encode("utf-8")
    request = urllib.request.Request(
        f"http://{clean_host}/{action}",
        data=payload,
        headers={"Content-Type": "application/json", "X-JARVIS-TOKEN": clean_token},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Phone Agent rejected the request: {detail or exc.code}") from exc
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError("Could not reach JARVIS Phone Agent. Check Wi-Fi, IP and pairing code.") from exc
    if not data.get("ok"):
        raise RuntimeError(str(data.get("error", "Phone Agent could not complete the request.")))
    return str(data.get("message", "Done."))
