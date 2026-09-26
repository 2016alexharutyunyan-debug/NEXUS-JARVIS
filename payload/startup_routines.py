"""Persistent startup routines and public market-data helpers."""

from __future__ import annotations

import concurrent.futures
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path


CRYPTO_SYMBOLS = (
    ("BTC", "BTCUSDT"),
    ("ETH", "ETHUSDT"),
    ("SOL", "SOLUSDT"),
)
MARKET_BASE_URLS = (
    "https://data-api.binance.vision",
    "https://api.binance.com",
)


class StartupRoutineStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> dict[str, bool]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {"crypto_market": bool(data.get("crypto_market", False))}
        except (OSError, ValueError, TypeError):
            pass
        return {"crypto_market": False}

    def crypto_enabled(self) -> bool:
        return self.load()["crypto_market"]

    def set_crypto_enabled(self, enabled: bool) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({"crypto_market": bool(enabled)}, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)


def startup_routine_intent(text: str) -> str | None:
    normalized = " ".join(str(text or "").lower().replace("-", " ").split())
    if not any(term in normalized for term in ("crypto", "cryptocurrency", "bitcoin")):
        return None
    disable_patterns = (
        r"\bstop (showing|opening).*(startup|start up)",
        r"\b(remove|disable|delete|forget).*(routine|startup|crypto)",
        r"\bdo not (show|open).*(crypto|bitcoin)",
        r"\bdon't (show|open).*(crypto|bitcoin)",
    )
    if any(re.search(pattern, normalized) for pattern in disable_patterns):
        return "disable_crypto"
    enable_patterns = (
        r"\bi (work|trade|invest).*(crypto|cryptocurrency|bitcoin)",
        r"\bi am .*crypto (trader|investor)",
        r"\bremember.*(crypto|cryptocurrency|bitcoin)",
        r"\b(show|open).*(crypto|bitcoin).*(startup|start up|every time)",
    )
    if any(re.search(pattern, normalized) for pattern in enable_patterns):
        return "enable_crypto"
    return None


def crypto_google_url() -> str:
    query = urllib.parse.urlencode({"q": "crypto market today BTC ETH SOL prices"})
    return "https://www.google.com/search?" + query


def _read_json(url: str, opener) -> object:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "NEXUS-JARVIS/3.3"},
    )
    with opener(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_crypto_market(opener=urllib.request.urlopen) -> list[dict[str, float | str]]:
    last_error: Exception | None = None
    for base_url in MARKET_BASE_URLS:
        try:
            def fetch_symbol(item):
                name, pair = item
                query = urllib.parse.urlencode({"symbol": pair})
                data = _read_json(f"{base_url}/api/v3/ticker/24hr?{query}", opener)
                if not isinstance(data, dict):
                    raise RuntimeError("Unexpected crypto market response.")
                return {
                    "symbol": name,
                    "price": float(data["lastPrice"]),
                    "change_percent": float(data["priceChangePercent"]),
                }

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                return list(executor.map(fetch_symbol, CRYPTO_SYMBOLS))
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Crypto market data is unavailable: {last_error}")


def format_crypto_summary(market: list[dict[str, float | str]]) -> str:
    parts = []
    for item in market:
        change = float(item["change_percent"])
        direction = "up" if change >= 0 else "down"
        parts.append(
            f"{item['symbol']} ${float(item['price']):,.2f}, {direction} {abs(change):.2f} percent"
        )
    return ". ".join(parts) + "."
