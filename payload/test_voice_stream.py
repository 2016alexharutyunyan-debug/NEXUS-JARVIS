import ast
import json
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
import urllib.request
import urllib.error
import urllib.parse


class StreamingVoiceTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path(__file__).with_name('main.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SpeechWorker')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_run_elevenlabs_tts')
        namespace = dict(os=os, json=json, urllib=urllib,
                         elevenlabs_api_key=lambda: 'test-key',
                         elevenlabs_voice_id=lambda: 'test-voice',
                         voice_config_from_file=lambda: {}, ELEVENLABS_TTS_TIMEOUT_SECONDS=12)
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<speech>', 'exec'), namespace)
        self.run_voice = namespace['_run_elevenlabs_tts']
        self.worker = MagicMock(original_text='Hello there.')
        self.sd = MagicMock()
        self.output = self.sd.RawOutputStream.return_value.__enter__.return_value
        self.response = MagicMock()

    def run_stream(self):
        with patch.dict('sys.modules', {'sounddevice': self.sd}), patch.object(
            urllib.request, 'urlopen') as open_url:
            open_url.return_value.__enter__.return_value = self.response
            result = self.run_voice(self.worker)
            self.assertIn('/stream?output_format=pcm_24000', open_url.call_args.args[0].full_url)
            return result

    def test_audio_plays_before_response_finishes_and_preserves_sample_boundaries(self):
        chunks = iter([b'abc', b'def', b''])
        calls = 0
        def read(size):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.output.write.assert_called_once_with(b'ab')
            return next(chunks)
        self.response.read1.side_effect = read
        self.assertEqual(self.run_stream(), (True, ''))
        self.assertEqual(b''.join(c.args[0] for c in self.output.write.call_args_list), b'abcdef')
        self.response.read.assert_not_called()
        self.worker._play_audio_file.assert_not_called()

    def test_empty_stream_allows_fallback(self):
        self.response.read1.return_value = b''
        self.assertFalse(self.run_stream()[0])

    def test_failure_before_audio_allows_fallback(self):
        self.response.read1.side_effect = TimeoutError('timeout')
        self.assertFalse(self.run_stream()[0])

    def test_partial_audio_failure_does_not_repeat_answer(self):
        self.response.read1.side_effect = [b'abcd', TimeoutError('timeout')]
        self.assertTrue(self.run_stream()[0])
        self.worker.failed.emit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
