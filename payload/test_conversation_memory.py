import json
import tempfile
import unittest
from pathlib import Path

from conversation_memory import ConversationMemory, memory_safe_text


class ConversationMemoryTests(unittest.TestCase):
    def test_round_trip_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "memory.json"
            memory = ConversationMemory(path, limit_messages=4)
            messages = [{"role": "user" if index % 2 == 0 else "assistant", "content": str(index)} for index in range(8)]
            memory.save(messages)
            self.assertEqual([item["content"] for item in memory.load()], ["4", "5", "6", "7"])

    def test_secrets_are_not_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "memory.json"
            memory = ConversationMemory(path)
            memory.save([{"role": "user", "content": "API key: AIzaExampleSecretValue123456789"}])
            stored = path.read_text(encoding="utf-8")
            self.assertNotIn("AIzaExample", stored)
            self.assertIn("sensitive information not saved", stored)

    def test_invalid_file_is_ignored_and_clear_removes_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "memory.json"
            path.write_text("not json", encoding="utf-8")
            memory = ConversationMemory(path)
            self.assertEqual(memory.load(), [])
            memory.clear()
            self.assertFalse(path.exists())

    def test_key_like_values_are_redacted(self):
        text = memory_safe_text("Use sk-abcdefghijklmnopqrstuvwxyz1234 now")
        self.assertNotIn("sk-abc", text)


if __name__ == "__main__":
    unittest.main()
