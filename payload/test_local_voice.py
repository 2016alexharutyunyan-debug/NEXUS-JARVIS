import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_voice import resolve_piper_executable, synthesize_piper


class LocalVoiceTests(unittest.TestCase):
    def test_resolve_piper_uses_configured_file(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder) / "piper.exe"
            executable.write_bytes(b"")
            self.assertEqual(resolve_piper_executable(str(executable)), str(executable))

    def test_piper_requires_voice_model(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder) / "piper.exe"
            executable.write_bytes(b"")
            with self.assertRaisesRegex(RuntimeError, "voice model"):
                synthesize_piper("hello", "", Path(folder) / "out.wav", str(executable))

    @patch("local_voice.shutil.which", return_value=None)
    def test_missing_piper_is_reported(self, _which):
        with patch("local_voice.sys.executable", str(Path("Z:/missing/python.exe"))):
            self.assertEqual(resolve_piper_executable(""), "")

    @patch("local_voice.shutil.which", return_value=None)
    def test_resolve_piper_finds_virtual_environment_executable(self, _which):
        with tempfile.TemporaryDirectory() as folder:
            python = Path(folder) / "python.exe"
            piper = Path(folder) / "piper.exe"
            piper.write_bytes(b"")
            with patch("local_voice.sys.executable", str(python)):
                self.assertEqual(resolve_piper_executable(""), str(piper))


if __name__ == "__main__":
    unittest.main()
