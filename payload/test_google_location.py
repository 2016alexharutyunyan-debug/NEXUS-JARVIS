import ast
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEnginePermission
from google_location import GoogleLocationWidget, trusted_location_origin


class GoogleLocationTests(unittest.TestCase):
    def test_origin_is_exact_https(self):
        self.assertTrue(trusted_location_origin(QUrl('https://www.google.com')))
        for url in ('http://www.google.com', 'https://www.google.com.evil.test', 'https://evil.test', 'https://www.google.com:444'):
            self.assertFalse(trusted_location_origin(QUrl(url)))

    @patch('google_location.QMessageBox.question')
    def test_wrong_origin_never_prompts(self, question):
        self.assertFalse(GoogleLocationWidget.consent(MagicMock(), QUrl('https://evil.test')))
        question.assert_not_called()

    def test_permission_denied(self):
        owner, request = MagicMock(), MagicMock()
        owner.consent.return_value = False
        request.permissionType.return_value = QWebEnginePermission.PermissionType.Geolocation
        GoogleLocationWidget.permission_requested(owner, request)
        request.deny.assert_called_once()
        request.grant.assert_not_called()

    def test_permission_granted_only_after_consent(self):
        owner, request = MagicMock(), MagicMock()
        owner.consent.return_value = True
        request.permissionType.return_value = QWebEnginePermission.PermissionType.Geolocation
        GoogleLocationWidget.permission_requested(owner, request)
        owner.consent.assert_called_once()
        request.grant.assert_called_once()

    def test_other_permissions_denied(self):
        owner, request = MagicMock(), MagicMock()
        request.permissionType.return_value = QWebEnginePermission.PermissionType.Notifications
        GoogleLocationWidget.permission_requested(owner, request)
        request.deny.assert_called_once()
        owner.consent.assert_not_called()

    def test_command_reuses_embedded_map_not_browser(self):
        tree = ast.parse(Path(__file__).with_name('main.py').read_text(encoding='utf-8'))
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'open_google_location')
        method.returns = None
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<embedded>', 'exec'), namespace)
        owner = MagicMock()
        window = MagicMock(content_type='google_location')
        owner.windows = [window]
        self.assertTrue(namespace['open_google_location'](owner))
        window.maximize_window.assert_called_once()
        owner.place_window.assert_not_called()


if __name__ == '__main__':
    unittest.main()
