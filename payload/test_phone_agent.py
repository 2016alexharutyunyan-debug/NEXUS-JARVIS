import io
import json
import unittest
from unittest.mock import patch

from phone_agent import phone_agent_request


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({"ok": True, "message": "SMS sent."}).encode()


class PhoneAgentTests(unittest.TestCase):
    def test_requires_host(self):
        with self.assertRaisesRegex(ValueError, "phone IP"):
            phone_agent_request("", "CODE", "sms", "094881201", "hello")

    def test_requires_pairing_code(self):
        with self.assertRaisesRegex(ValueError, "pairing code"):
            phone_agent_request("192.168.1.25:8766", "", "call", "094881201")

    @patch("urllib.request.urlopen", return_value=FakeResponse())
    def test_sends_authenticated_local_request(self, mocked_open):
        reply = phone_agent_request("http://192.168.1.25:8766/", "ABC123", "sms", "094881201", "hello")
        self.assertEqual(reply, "SMS sent.")
        request = mocked_open.call_args.args[0]
        self.assertEqual(request.full_url, "http://192.168.1.25:8766/sms")
        self.assertEqual(request.get_header("X-jarvis-token"), "ABC123")


if __name__ == "__main__":
    unittest.main()
