import ast
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from location_map import LocationMapWidget, location_intent, google_maps_intent, device_location, validated_location, lookup_location, open_google_maps
from urllib.parse import urlparse, parse_qs
import queue


class LocationTests(unittest.TestCase):
    def test_intents(self):
        for command in ("my location", "My location!", "hey Jarvis, my location", "Jarvis please show my location", "Where am I?", "locate me please"):
            self.assertTrue(location_intent(command), command)
        for command in ("save my location history", "don't show my location", "build an app with my location", "world map", "open windows browser"):
            self.assertFalse(location_intent(command), command)

    def test_validation(self):
        data = validated_location({"success": True, "latitude": 0, "longitude": 0, "city": "Test", "ip": "secret"})
        self.assertEqual(data["latitude"], 0)
        self.assertNotIn("ip", data)
        self.assertIn("not GPS", data["source"])
        for lat, lon in ((91, 0), (0, 181), (True, 0), (float('nan'), 0), (0, float('inf')), (None, 2), ("40", 2)):
            with self.assertRaises(ValueError):
                validated_location({"success": True, "latitude": lat, "longitude": lon})
        for data in ({"success": False}, None, []):
            with self.assertRaises(ValueError):
                validated_location(data)

    @patch('location_map.urllib.request.urlopen')
    def test_request(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({"success": True, "latitude": 12, "longitude": 34}).encode()
        result = lookup_location()
        self.assertEqual(result["longitude"], 34)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://ipwho.is/")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 8)
        self.assertNotIn("Authorization", request.headers)

    def test_text_and_voice_routing(self):
        tree = ast.parse(Path(__file__).with_name('main.py').read_text(encoding='utf-8'))
        for name in ('_command_reply', 'execute_command'):
            method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)
            method.returns = None
            for arg in method.args.args:
                arg.annotation = None
            namespace = {'location_intent': location_intent, 'google_maps_intent': google_maps_intent}
            exec(compile(ast.Module(body=[method], type_ignores=[]), '<route>', 'exec'), namespace)
            owner = MagicMock()
            result = namespace[name](owner, 'Hey Jarvis, my location!')
            target = owner.canvas if name == '_command_reply' else owner
            target.add_location_window.assert_called_once()
            target.open_google_location.assert_not_called()
            self.assertTrue(result)

    @patch('location_map.QDesktopServices.openUrl', return_value=True)
    @patch('location_map.lookup_location')
    def test_google_maps_uses_browser_without_ip_lookup(self, lookup, open_url):
        self.assertTrue(open_google_maps())
        url = urlparse(open_url.call_args.args[0].toString())
        self.assertEqual(url.scheme, 'https')
        self.assertEqual(url.hostname, 'www.google.com')
        self.assertEqual(parse_qs(url.query), {'api': ['1'], 'map_action': ['map']})
        lookup.assert_not_called()

    @patch('location_map.QDesktopServices.openUrl', return_value=False)
    def test_browser_failure(self, open_url):
        self.assertFalse(open_google_maps())

    def test_declined_network_does_not_start_work(self):
        owner = MagicMock()
        owner.busy = False
        owner.ready = True
        owner.allow_network.return_value = False
        LocationMapWidget.locate(owner)
        owner.view.page.assert_not_called()
        owner.poll.start.assert_not_called()

    def test_duplicate_lookup_is_ignored(self):
        owner = MagicMock()
        owner.busy = True
        LocationMapWidget.locate(owner)
        owner.allow_network.assert_not_called()

    def test_device_position_has_reported_accuracy(self):
        from PySide6.QtCore import QDateTime
        from PySide6.QtPositioning import QGeoPositionInfo, QGeoCoordinate
        info = QGeoPositionInfo(QGeoCoordinate(10, 20), QDateTime.currentDateTimeUtc())
        info.setAttribute(QGeoPositionInfo.Attribute.HorizontalAccuracy, 50)
        result = device_location(info)
        self.assertEqual(result['kind'], 'device')
        self.assertEqual(result['accuracy'], 50)
        self.assertIn('not guaranteed GPS', result['source'])
        info.setTimestamp(QDateTime.currentDateTimeUtc().addSecs(-3600))
        with self.assertRaises(ValueError):
            device_location(info)

    def test_unknown_accuracy_is_not_invented(self):
        from PySide6.QtCore import QDateTime
        from PySide6.QtPositioning import QGeoPositionInfo, QGeoCoordinate
        info = QGeoPositionInfo(QGeoCoordinate(10, 20), QDateTime.currentDateTimeUtc())
        self.assertIsNone(device_location(info)['accuracy'])

    @patch('location_map.lookup_location')
    def test_device_failure_does_not_fall_back_to_ip(self, lookup):
        owner = MagicMock()
        LocationMapWidget.device_failed(owner)
        owner.stop_device.assert_called_once()
        lookup.assert_not_called()
        self.assertIn('unavailable', owner.status.setText.call_args.args[0])

    def test_google_command_is_separate_from_hud(self):
        self.assertTrue(google_maps_intent('Jarvis, open Google Maps'))
        self.assertFalse(location_intent('Jarvis, open Google Maps'))
        self.assertFalse(google_maps_intent('my location'))

    def test_failed_lookup_is_visible(self):
        owner = MagicMock()
        owner.results = queue.Queue()
        owner.results.put((False, 'Location unavailable.'))
        LocationMapWidget.collect_result(owner)
        owner.status.setText.assert_called_once_with('Location unavailable.')
        self.assertFalse(owner.busy)
        owner.show_location.assert_not_called()

    def test_successful_lookup_is_displayed(self):
        owner = MagicMock()
        owner.results = queue.Queue()
        data = validated_location({'success': True, 'latitude': 20, 'longitude': 30})
        owner.results.put((True, data))
        LocationMapWidget.collect_result(owner)
        owner.show_location.assert_called_once_with(data)
        owner.refresh_button.setEnabled.assert_called_once_with(True)

    def test_repeat_command_focuses_existing_map(self):
        tree = ast.parse(Path(__file__).with_name('main.py').read_text(encoding='utf-8'))
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'add_location_window')
        method.returns = None
        for arg in method.args.args:
            arg.annotation = None
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<window>', 'exec'), namespace)
        owner = MagicMock()
        existing = MagicMock(content_type='location')
        owner.windows = [existing]
        result = namespace['add_location_window'](owner)
        self.assertIs(result, existing)
        existing.maximize_window.assert_called_once()
        owner.place_window.assert_not_called()


if __name__ == '__main__':
    unittest.main()
