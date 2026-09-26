import unittest

from phone_link import call_uri, normalize_phone_number, parse_phone_action, sms_uri


class PhoneLinkTests(unittest.TestCase):
    def test_parses_call_command(self):
        action = parse_phone_action("call +374 94 881 201")
        self.assertEqual((action.kind, action.number), ("call", "+37494881201"))

    def test_parses_short_text_command(self):
        action = parse_phone_action("text 094881201 I will arrive at six")
        self.assertEqual(action.kind, "text")
        self.assertEqual(action.number, "094881201")
        self.assertEqual(action.message, "I will arrive at six")

    def test_parses_send_sms_command(self):
        action = parse_phone_action("send an SMS to +374 94 881 201 saying hello Alex")
        self.assertEqual(action.message, "hello Alex")

    def test_rejects_emergency_numbers(self):
        with self.assertRaisesRegex(ValueError, "Emergency calls"):
            normalize_phone_number("112")

    def test_rejects_invalid_number(self):
        with self.assertRaises(ValueError):
            normalize_phone_number("Alex")

    def test_builds_phone_link_uris(self):
        self.assertEqual(call_uri("+374 (94) 881-201"), "tel:+37494881201")
        self.assertEqual(
            sms_uri("094881201", "Hello from JARVIS!"),
            "sms:094881201?body=Hello%20from%20JARVIS%21",
        )


if __name__ == "__main__":
    unittest.main()
