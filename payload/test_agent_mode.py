import unittest

from agent_mode import looks_like_agent_request, validate_agent_plan


class AgentModeTests(unittest.TestCase):
    def test_action_intent(self):
        for text in ('open my browser', 'Jarvis please create a note', 'can you search for weather', 'read the screen'):
            self.assertTrue(looks_like_agent_request(text), text)
        for text in ('how are you', 'how do I open Chrome', 'tell me about Python'):
            self.assertFalse(looks_like_agent_request(text), text)

    def test_valid_plan(self):
        plan = validate_agent_plan({'reply': 'I can do that.', 'actions': [
            {'type': 'search', 'query': 'weather in Yerevan'},
            {'type': 'note', 'title': 'Tasks', 'text': 'Call Sam'},
        ]})
        self.assertEqual(len(plan['actions']), 2)

    def test_rejects_unsafe_or_unknown_actions(self):
        for action in (
            {'type': 'command', 'command': 'delete all files'},
            {'type': 'shell', 'command': 'format disk'},
            {'type': 'website', 'name': 'unknown.example'},
        ):
            with self.assertRaises(ValueError):
                validate_agent_plan({'reply': '', 'actions': [action]})

    def test_action_count_is_bounded(self):
        actions = [{'type': 'command', 'command': 'open chrome'}] * 4
        with self.assertRaises(ValueError):
            validate_agent_plan({'reply': '', 'actions': actions})


if __name__ == '__main__':
    unittest.main()
