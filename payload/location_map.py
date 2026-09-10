"""On-demand location HUD. No coordinates or lookup responses are persisted."""
import json
import math
import queue
import re
import threading
import urllib.request
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, QDateTime
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QInputDialog, QStyle, QMenu

GOOGLE_MAPS_LOCATION_URL = "https://www.google.com/maps/@?api=1&map_action=map"


def open_google_maps():
    # No IP estimate or coordinates: the browser handles Google's location permission.
    return QDesktopServices.openUrl(QUrl(GOOGLE_MAPS_LOCATION_URL))


def normalized_location_command(text):
    text = " ".join(re.sub(r"[^a-z\s]", " ", text.lower()).split())
    for prefix in ("hey jarvis ", "jarvis ", "can you ", "please "):
        if text.startswith(prefix):
            text = text[len(prefix):]
    text = text.removesuffix(" please")
    return text


def location_intent(text):
    return normalized_location_command(text) in {"my location", "show my location", "where am i", "locate me", "open my location", "location hud", "open location hud"}


def google_maps_intent(text):
    return normalized_location_command(text) in {"open google maps", "google maps"}


def device_location(info):
    from PySide6.QtPositioning import QGeoPositionInfo
    if not info.isValid() or not -60 <= info.timestamp().secsTo(QDateTime.currentDateTimeUtc()) <= 120:
        raise ValueError('No recent device position available.')
    coordinate = info.coordinate()
    result = validated_location({'success': True, 'latitude': coordinate.latitude(), 'longitude': coordinate.longitude()})
    accuracy = info.attribute(QGeoPositionInfo.Attribute.HorizontalAccuracy) if info.hasAttribute(QGeoPositionInfo.Attribute.HorizontalAccuracy) else None
    if accuracy is not None and (not math.isfinite(accuracy) or accuracy < 0):
        accuracy = None
    result.update(label='Device location', source='Windows location / not guaranteed GPS', kind='device', accuracy=accuracy)
    return result


def validated_location(data):
    if not isinstance(data, dict) or data.get("success") is not True:
        raise ValueError("Location service could not locate this connection.")
    lat, lon = data.get("latitude"), data.get("longitude")
    if (isinstance(lat, bool) or isinstance(lon, bool)
            or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float))
            or not math.isfinite(lat) or not math.isfinite(lon)
            or not -90 <= lat <= 90 or not -180 <= lon <= 180):
        raise ValueError("Location service returned invalid coordinates.")
    label = ", ".join(str(data[k])[:100] for k in ("city", "country") if data.get(k))
    return {"latitude": lat, "longitude": lon, "label": label or "Approximate region", "source": "IP estimate / not GPS"}


def lookup_location():
    request = urllib.request.Request("https://ipwho.is/", headers={"User-Agent": "JARVIS-HoloDesk/2.4 Location"})
    with urllib.request.urlopen(request, timeout=8) as response:
        return validated_location(json.loads(response.read(65536)))


class LocationMapWidget(QWidget):
    session_allowed = False
    shared_profile = None

    def __init__(self):
        super().__init__()
        self.ready = False
        self.busy = False
        self.location_source = None
        self.device_timeout = QTimer(self)
        self.device_timeout.setSingleShot(True)
        self.device_timeout.timeout.connect(self.device_failed)
        self.results = queue.Queue()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.status = QLabel("LOCATION / READY")
        self.status.setWordWrap(True)
        bar.addWidget(self.status, 1)
        self.refresh_button = QPushButton()
        self.refresh_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.refresh_button.setToolTip("Locate again")
        self.refresh_button.setFixedSize(36, 32)
        self.refresh_button.clicked.connect(self.locate)
        bar.addWidget(self.refresh_button)
        manual = QPushButton()
        manual.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        manual.setToolTip("Location options")
        manual.setFixedSize(36, 32)
        menu = QMenu(manual)
        menu.addAction('Enter coordinates', self.manual_location)
        menu.addAction('Approximate IP location', self.locate_ip)
        menu.addAction('Windows location settings', lambda: QDesktopServices.openUrl(QUrl('ms-settings:privacy-location')))
        manual.setMenu(menu)
        bar.addWidget(manual)
        layout.addLayout(bar)
        self.setStyleSheet("QWidget{background:#050b10;color:#95e6f4;} QLabel{padding:6px;} QPushButton{border:1px solid #286573;border-radius:4px;background:#10232b;}")
        self.view = None
        try:
            from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings
            from PySide6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            self.status.setText("Map component unavailable. Run INSTALL_JARVIS.bat.")
            return
        # A named profile keeps the map tile HTTP cache separate from browsing.
        if type(self).shared_profile is None:
            type(self).shared_profile = QWebEngineProfile("JarvisLocationMap", QApplication.instance())
            type(self).shared_profile.setHttpUserAgent("JARVIS-HoloDesk/2.4 (+https://jarvis-voice-desktop.chirpy-rook-7076.chatgpt.site)")
        self.profile = type(self).shared_profile
        page_url = QUrl.fromLocalFile(str(Path(__file__).resolve().parent / "assets" / "location" / "index.html"))

        class MapPage(QWebEnginePage):
            def acceptNavigationRequest(self, url, navigation_type, main_frame):
                if main_frame and url != page_url:
                    if navigation_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked and url.scheme() == "https":
                        QDesktopServices.openUrl(url)
                    return False
                return True

        self.view = QWebEngineView(self)
        self.view.setPage(MapPage(self.profile, self.view))
        self.view.page().setBackgroundColor(QColor("#050b10"))
        self.view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        layout.addWidget(self.view, 1)
        self.view.loadFinished.connect(self.loaded)
        self.view.setUrl(page_url)
        self.poll = QTimer(self)
        self.poll.setInterval(100)
        self.poll.timeout.connect(self.collect_result)

    def loaded(self, ok):
        self.ready = ok
        if not ok:
            self.status.setText("Map files could not load. Extract the complete ZIP first.")
            return
        self.locate()

    def allow_network(self):
        if not self.session_allowed:
            answer = QMessageBox.question(
                self, "Location privacy",
                "Use online location and maps for this session?\n\n"
                "Windows supplies a device position if available. OpenStreetMap receives "
                "your IP and viewed map tiles. Accuracy depends on Windows and your hardware. "
                "JARVIS does not save coordinates or continuously track you. "
                "IP estimation is used only if you select that option separately.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.status.setText("LOCATION / PERMISSION DECLINED")
                return False
            type(self).session_allowed = True
        return True

    def locate(self):
        if self.busy or not self.ready or self.view is None or not self.allow_network():
            return
        self.busy = True
        self.refresh_button.setEnabled(False)
        self.status.setText('LOCATION / WAITING FOR WINDOWS')
        self.view.page().runJavaScript("window.startMap(); window.locationStatus('LOCATING DEVICE', true);")
        try:
            from PySide6.QtPositioning import QGeoPositionInfoSource
            self.location_source = QGeoPositionInfoSource.createDefaultSource(self)
        except ImportError:
            self.location_source = None
        if self.location_source is None:
            self.device_failed()
            return
        self.location_source.positionUpdated.connect(self.device_updated)
        self.location_source.errorOccurred.connect(self.device_error)
        self.device_timeout.start(13000)
        self.location_source.requestUpdate(12000)

    def stop_device(self):
        self.device_timeout.stop()
        if self.location_source is not None:
            source = self.location_source
            self.location_source = None
            source.stopUpdates()
            source.deleteLater()
        self.busy = False
        self.refresh_button.setEnabled(True)

    def device_updated(self, info):
        if self.location_source is None:
            return
        try:
            result = device_location(info)
        except ValueError:
            self.device_failed()
            return
        self.stop_device()
        self.show_location(result)

    def device_error(self, error):
        from PySide6.QtPositioning import QGeoPositionInfoSource
        if error != QGeoPositionInfoSource.Error.NoError and self.location_source is not None:
            self.device_failed()

    def device_failed(self):
        self.stop_device()
        self.status.setText('Device location unavailable. Enable Windows location services or choose Location options.')
        self.view.page().runJavaScript("window.locationStatus('DEVICE LOCATION UNAVAILABLE', true);")

    def locate_ip(self):
        if self.busy or not self.ready or self.view is None or not self.allow_network():
            return
        answer = QMessageBox.question(self, 'Approximate location',
            'Use ipwho.is to estimate a city from your public IP? This can show another city, especially with a VPN.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.busy = True
        self.refresh_button.setEnabled(False)
        self.status.setText("LOCATION / LOCATING")
        self.view.page().runJavaScript("window.startMap(); window.locationStatus('LOCATING', true);")
        results = self.results

        def work():
            try:
                results.put((True, lookup_location()))
            except Exception:
                results.put((False, "Location unavailable. Check internet, retry, or enter coordinates."))

        threading.Thread(target=work, daemon=True).start()
        self.poll.start()

    def collect_result(self):
        try:
            ok, result = self.results.get_nowait()
        except queue.Empty:
            return
        self.poll.stop()
        self.busy = False
        self.refresh_button.setEnabled(True)
        if ok:
            self.show_location(result)
        else:
            self.status.setText(result)
            self.view.page().runJavaScript("window.locationStatus('LOCATION UNAVAILABLE', false);")

    def show_location(self, result):
        self.status.setText("LOCATION / " + result["source"].upper())
        self.view.page().runJavaScript("window.showLocation(" + json.dumps(result) + ");")

    def manual_location(self):
        if self.busy or not self.ready or self.view is None:
            return
        text, ok = QInputDialog.getText(self, "Coordinates", "Latitude, longitude:")
        if not ok:
            return
        try:
            lat, lon = (float(value.strip()) for value in text.split(","))
            result = validated_location({"success": True, "latitude": lat, "longitude": lon})
        except (ValueError, TypeError):
            QMessageBox.warning(self, "Coordinates", "Enter latitude (-90 to 90), longitude (-180 to 180).")
            return
        if not self.allow_network():
            return
        result.update(label="Selected location", source="Manual coordinates / not detected")
        self.view.page().runJavaScript("window.startMap();")
        self.show_location(result)
