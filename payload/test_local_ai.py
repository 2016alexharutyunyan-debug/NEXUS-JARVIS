import unittest

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


if __name__ == "__main__":
    unittest.main()
