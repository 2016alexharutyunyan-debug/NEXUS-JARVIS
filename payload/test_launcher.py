"""Windows batch launcher regression tests; never starts the real assistant."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == 'nt', 'Windows launcher')
class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='JARVIS launcher space ')
        self.root = Path(self.temp.name)
        self.payload = self.root / 'payload'
        self.payload.mkdir()
        source = Path(__file__).resolve().parent
        root_source = source if (source / 'START_JARVIS.bat').exists() else source.parent
        shutil.copy2(root_source / 'START_JARVIS.bat', self.root)
        shutil.copy2(source / 'run_1_2_8_tts_fix.bat', self.payload)
        for name in ('main.py', 'pc_voice.py', 'location_map.py', 'google_location.py', 'mini_jarvis.py', 'screen_agent.py', 'assets/location/index.html',
                     'assets/location/location.js', 'assets/location/leaflet.js', 'assets/location/leaflet.css'):
            target = self.payload / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def run_launcher(self, *args):
        return subprocess.run(
            ['cmd.exe', '/d', '/c', 'call', str(self.root / 'START_JARVIS.bat'), *args],
            cwd=os.environ.get('SystemRoot', 'C:\\Windows'), input='\n',
            text=True, capture_output=True, timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def test_package_check_does_not_require_old_version(self):
        (self.payload / 'main.py').write_text('APP_VERSION = "9.9-future"\n', encoding='utf-8')
        result = self.run_launcher('--check')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('package check OK', result.stdout)

    def test_missing_payload(self):
        (self.payload / 'run_1_2_8_tts_fix.bat').unlink()
        result = self.run_launcher('--check')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('payload is missing', result.stdout)

    def test_missing_map_file(self):
        (self.payload / 'assets/location/location.js').unlink()
        result = self.run_launcher('--check')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('location.js', result.stdout)

    def test_launch_from_unrelated_directory_with_spaces(self):
        (self.payload / 'main.py').write_text('print("LAUNCH_STUB_OK")\n', encoding='utf-8')
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('LAUNCH_STUB_OK', result.stdout)

    def test_python_error_is_preserved(self):
        (self.payload / 'main.py').write_text('raise SystemExit(7)\n', encoding='utf-8')
        result = self.run_launcher()
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
