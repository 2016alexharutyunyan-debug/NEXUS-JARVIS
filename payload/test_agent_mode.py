import unittest

from agent_mode import local_agent_plan, looks_like_agent_request, validate_agent_plan


class AgentModeTests(unittest.TestCase):
    def test_action_intent(self):
        for text in ('open my browser', 'Jarvis please create a note', 'can you search for weather', 'read the screen'):
            self.assertTrue(looks_like_agent_request(text), text)
        for text in ('how are you', 'how do I open Chrome', 'tell me about Python'):
            self.assertFalse(looks_like_agent_request(text), text)
        self.assertFalse(looks_like_agent_request('change the world'))
        self.assertFalse(looks_like_agent_request('revolutionize the world'))

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
        actions = [{'type': 'command', 'command': 'open chrome'}] * 6
        with self.assertRaises(ValueError):
            validate_agent_plan({'reply': '', 'actions': actions})

    def test_local_plan_handles_everyday_actions(self):
        cases = {
            'open YouTube': {'type': 'website', 'name': 'youtube'},
            'search Google for weather in Yerevan': {'type': 'search', 'query': 'weather in yerevan'},
            'create a note called Shopping with milk and bread': {
                'type': 'note', 'title': 'Shopping', 'text': 'milk and bread'},
            'open my browser': {'type': 'command', 'command': 'open browser'},
            'then open YouTube': {'type': 'website', 'name': 'youtube'},
        }
        for request, action in cases.items():
            with self.subTest(request=request):
                self.assertEqual(local_agent_plan(request)['actions'][0], action)

    def test_local_plan_handles_multiple_actions(self):
        plan = local_agent_plan('search for weather and open YouTube')
        self.assertEqual([action['type'] for action in plan['actions']], ['search', 'website'])

    def test_local_plan_defers_unknown_requests(self):
        self.assertIsNone(local_agent_plan('write a poem about the moon'))


if __name__ == '__main__':
    unittest.main()
