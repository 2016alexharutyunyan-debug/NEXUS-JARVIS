import ast
from pathlib import Path
import unittest
from unittest.mock import MagicMock


class WindowsVoiceTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path(__file__).with_name('main.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SpeechWorker')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        namespace = {'IS_WINDOWS': True, 'EDGE_TTS_TIMEOUT_SECONDS': 10}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<speech>', 'exec'), namespace)
        self.run_voice = namespace['run']
        self.worker = MagicMock(original_text='Hello.')

    def check_no_network(self):
        self.worker._run_gemini_tts.assert_not_called()
        self.worker._run_elevenlabs_tts.assert_not_called()
        self.worker._run_edge_tts.assert_not_called()
        self.worker.finished_speaking.emit.assert_called_once()

    def test_windows_first(self):
        self.worker._run_ps.return_value = (True, '')
        self.run_voice(self.worker)
        self.worker.engine_used.emit.assert_called_once_with('Windows SAPI voice')
        script = self.worker._run_ps.call_args.args[0]
        self.assertIn("GetAttribute('Gender') -ne 'Male'", script)
        self.assertIn('-band 0x3ff) -eq 9', script)
        self.assertIn('$voice.Voice = $selected', script)
        self.assertIn('$voice.Rate = 1', script)
        self.check_no_network()

    def test_fallback_is_local(self):
        self.worker._run_ps.side_effect = [(False, 'unavailable'), (True, '')]
        self.run_voice(self.worker)
        self.worker.engine_used.emit.assert_called_once_with('Windows fallback voice')
        script = self.worker._run_ps.call_args.args[0]
        self.assertIn("VoiceInfo.Gender -eq 'Male'", script)
        self.assertIn("Culture.Name -like 'en-*'", script)
        self.assertIn('$synth.Rate = 1', script)
        self.check_no_network()

    def test_failure_does_not_use_cloud(self):
        self.worker._run_ps.return_value = (False, 'unavailable')
        self.run_voice(self.worker)
        self.worker.failed.emit.assert_called_once()
        self.check_no_network()


if __name__ == '__main__':
    unittest.main()
