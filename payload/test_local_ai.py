import unittest
from unittest.mock import MagicMock, PropertyMock, patch

from main import AIClient, AppSettings


class LocalAITests(unittest.TestCase):
    def test_ollama_uses_local_keyless_endpoint_and_selected_model(self):
        settings = AppSettings(
            local_ai_enabled=True,
            local_ai_model="qwen3:4b",
            persistent_memory=False,
        )
        client = AIClient(settings)

        self.assertEqual(client.effective_endpoint, "http://127.0.0.1:11434/v1")
        self.assertEqual(client.effective_model, "qwen3:4b")
        self.assertTrue(client.configured)

    def test_unavailable_ollama_falls_back_to_cloud(self):
        settings = AppSettings(local_ai_enabled=True, persistent_memory=False)
        client = AIClient(settings)
        client._chat_openai_compatible = MagicMock(
            return_value="AI connection error: connection refused"
        )
        client._chat_gemini_native = MagicMock(return_value="Cloud answer")

        with patch.object(AIClient, "effective_key", new_callable=PropertyMock, return_value="test-key"):
            result = client.chat("hello")

        self.assertEqual(result, "Cloud answer")
        client._chat_gemini_native.assert_called_once()
        self.assertGreater(client._local_unavailable_until, 0.0)

    def test_unavailable_ollama_uses_offline_reply_and_waits_before_retry(self):
        settings = AppSettings(local_ai_enabled=True, persistent_memory=False)
        client = AIClient(settings)
        client._chat_openai_compatible = MagicMock(
            return_value="AI connection error: connection refused"
        )

        with patch.object(AIClient, "effective_key", new_callable=PropertyMock, return_value=""):
            first = client.chat("hello")
            second = client.chat("hello again")

        self.assertNotIn("AI connection error", first)
        self.assertNotIn("AI connection error", second)
        self.assertEqual(client._chat_openai_compatible.call_count, 1)


if __name__ == "__main__":
    unittest.main()
