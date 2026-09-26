import json
import tempfile
import unittest
from pathlib import Path

from startup_routines import (
    StartupRoutineStore,
    fetch_crypto_market,
    format_crypto_summary,
    startup_routine_intent,
)


class _Response:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.data).encode("utf-8")


class StartupRoutineTests(unittest.TestCase):
    def test_crypto_work_statement_enables_routine(self):
        self.assertEqual(startup_routine_intent("I work with crypto"), "enable_crypto")

    def test_crypto_stop_statement_disables_routine(self):
        self.assertEqual(
            startup_routine_intent("Stop showing crypto on startup"),
            "disable_crypto",
        )

    def test_routine_is_persistent(self):
        with tempfile.TemporaryDirectory() as folder:
            store = StartupRoutineStore(Path(folder) / "routines.json")
            self.assertFalse(store.crypto_enabled())
            store.set_crypto_enabled(True)
            self.assertTrue(StartupRoutineStore(store.path).crypto_enabled())

    def test_market_response_and_summary(self):
        responses = {
            "BTCUSDT": {"lastPrice": "65000.25", "priceChangePercent": "2.50"},
            "ETHUSDT": {"lastPrice": "3200.50", "priceChangePercent": "-1.25"},
            "SOLUSDT": {"lastPrice": "150.00", "priceChangePercent": "0.10"},
        }

        def opener(request, timeout=0):
            pair = request.full_url.split("symbol=", 1)[1]
            return _Response(responses[pair])

        market = fetch_crypto_market(opener)
        self.assertEqual([item["symbol"] for item in market], ["BTC", "ETH", "SOL"])
        summary = format_crypto_summary(market)
        self.assertIn("BTC $65,000.25, up 2.50 percent", summary)
        self.assertIn("ETH $3,200.50, down 1.25 percent", summary)


if __name__ == "__main__":
    unittest.main()
