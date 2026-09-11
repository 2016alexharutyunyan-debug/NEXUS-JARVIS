import ast
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile

from pc_voice import parse_pc_command


class ZipTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(Path(__file__).with_name('main.py').read_text(encoding='utf-8'))
        widget = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'ZipBuilderWidget')
        method = next(node for node in widget.body if isinstance(node, ast.FunctionDef) and node.name == 'build_zip')
        self.messages = MagicMock()
        self.messages.StandardButton.Yes = 1
        self.messages.StandardButton.No = 2
        self.messages.question.return_value = 1
        namespace = dict(Path=Path, tempfile=tempfile, os=os, zipfile=zipfile,
                         QMessageBox=self.messages, APP_NAME='JARVIS')
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<zip-builder>', 'exec'), namespace)
        self.build = namespace['build_zip']
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'hello.txt').write_text('hello', encoding='utf-8')
        self.output = self.source / 'archive.zip'
        self.ui = MagicMock()
        self.ui.source.text.return_value = str(self.source)
        self.ui.output.text.return_value = str(self.output)
        self.ui._should_skip.return_value = False

    def test_archive_inside_source_excludes_itself_and_temporary_file(self):
        self.build(self.ui)
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.namelist(), ['hello.txt'])
            self.assertEqual(archive.read('hello.txt'), b'hello')

    def test_existing_archive_survives_write_failure(self):
        self.output.write_bytes(b'previous archive')
        with patch.object(zipfile.ZipFile, 'write', side_effect=OSError('disk failure')):
            self.build(self.ui)
        self.assertEqual(self.output.read_bytes(), b'previous archive')
        self.assertEqual(list(self.source.glob('.jarvis-*')), [])
        self.messages.warning.assert_called_once()

    def test_declined_replace_preserves_file(self):
        self.output.write_bytes(b'previous archive')
        self.messages.question.return_value = 2
        self.build(self.ui)
        self.assertEqual(self.output.read_bytes(), b'previous archive')

    def test_directory_output_is_reported_without_crashing(self):
        for target in ('.', str(self.source), self.root.anchor):
            with self.subTest(target=target):
                self.messages.reset_mock()
                self.ui.output.text.return_value = target
                self.build(self.ui)
                self.messages.warning.assert_called_once()

    def test_empty_output_is_reported(self):
        self.ui.output.text.return_value = ' '
        self.build(self.ui)
        self.messages.warning.assert_called_once()


class CommandTests(unittest.TestCase):
    def test_polite_prefix_order(self):
        expected = parse_pc_command('open chrome')
        self.assertIsNotNone(expected)
        for phrase in ('Please Jarvis, can you open Chrome?',
                       'Can you please hey Jarvis open Chrome please',
                       'Jarvis please open Chrome'):
            self.assertEqual(parse_pc_command(phrase), expected)

    def test_conversation_is_not_a_command(self):
        self.assertIsNone(parse_pc_command('Do not open chrome'))
        self.assertIsNone(parse_pc_command('Tell me about open chrome'))


if __name__ == '__main__':
    unittest.main()
