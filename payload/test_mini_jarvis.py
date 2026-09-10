import ast
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt, QEvent, QPoint
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtTest import QTest
from mini_jarvis import MiniJarvis, voice_label


def main_methods(class_name, names):
    tree = ast.parse(Path(__file__).with_name('main.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    return [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]


class MiniTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
        cls.app.setFont(QFont('Segoe UI', 10))
        methods = main_methods('MainWindow', {'changeEvent', 'restore_from_mini'})
        tree = ast.Module(body=[ast.ClassDef(name='Harness', bases=[ast.Name(id='QMainWindow', ctx=ast.Load())], keywords=[], body=methods, decorator_list=[])], type_ignores=[])
        namespace = {'QMainWindow': QMainWindow, 'QEvent': QEvent, 'Qt': Qt}
        exec(compile(ast.fix_missing_locations(tree), '<main-window>', 'exec'), namespace)
        cls.Harness = namespace['Harness']

    def setUp(self):
        self.window = self.Harness()
        self.window.mini_voice = MiniJarvis()
        self.window._mini_was_maximized = False
        self.window.auto_voice = MagicMock(enabled=True)
        self.window.mini_voice.restore_requested.connect(self.window.restore_from_mini)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.mini_voice.close()
        self.window.mini_voice.deleteLater()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_minimize_preserves_voice_and_restore_hides_badge(self):
        self.window.showMinimized()
        self.app.processEvents()
        self.assertTrue(self.window.mini_voice.isVisible())
        self.window.auto_voice.stop.assert_not_called()
        self.window.restore_from_mini()
        self.app.processEvents()
        self.assertFalse(self.window.isMinimized())
        self.assertFalse(self.window.mini_voice.isVisible())

    def test_maximized_state_survives_roundtrip(self):
        self.window.showMaximized()
        self.window.showMinimized()
        self.app.processEvents()
        self.window.restore_from_mini()
        self.assertTrue(self.window.isMaximized())

    def test_click_restores(self):
        self.window.showMinimized()
        self.app.processEvents()
        QTest.mouseClick(self.window.mini_voice, Qt.MouseButton.LeftButton, pos=QPoint(56, 55))
        self.assertFalse(self.window.isMinimized())

    def test_badge_does_not_accept_focus(self):
        mini = self.window.mini_voice
        self.assertTrue(mini.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus)
        self.assertTrue(mini.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
        self.assertEqual(mini.focusPolicy(), Qt.FocusPolicy.NoFocus)

    def test_drag_does_not_restore(self):
        mini = self.window.mini_voice
        self.window.showMinimized()
        self.app.processEvents()
        press = MagicMock()
        press.button.return_value = Qt.MouseButton.LeftButton
        press.globalPosition.return_value.toPoint.return_value = QPoint(100, 100)
        mini.mousePressEvent(press)
        move = MagicMock()
        move.buttons.return_value = Qt.MouseButton.LeftButton
        move.globalPosition.return_value.toPoint.return_value = QPoint(150, 150)
        mini.mouseMoveEvent(move)
        mini.mouseReleaseEvent(press)
        self.assertTrue(self.window.isMinimized())

    def test_status_priority_and_pause(self):
        self.assertEqual(voice_label('VOICE ERROR'), 'ERROR')
        self.assertEqual(voice_label('SPEAKING'), 'SPEAKING')
        self.assertEqual(voice_label('AI THINKING'), 'THINKING')
        self.assertEqual(voice_label('LISTENING', False), 'PAUSED')

    def test_paused_or_discarded_recording_cannot_execute(self):
        method = main_methods('AutoVoiceController', {'_heard'})[0]
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<voice>', 'exec'), namespace)
        for enabled, discard in ((False, False), (True, True)):
            owner = MagicMock(enabled=enabled, _closing=False, _discard_recording=discard)
            namespace['_heard'](owner, 'close window')
            owner._command_reply.assert_not_called()

    def test_resume_waits_for_previous_worker_cleanup(self):
        method = main_methods('AutoVoiceController', {'_start_listening'})[0]
        factory = MagicMock()
        namespace = {'VoiceWorker': factory}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<voice-start>', 'exec'), namespace)
        owner = MagicMock(enabled=True, _closing=False, _busy_reply=False)
        owner.worker.isRunning.return_value = False
        namespace['_start_listening'](owner)
        factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
