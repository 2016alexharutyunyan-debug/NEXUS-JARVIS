"""Google Maps inside the JARVIS desktop, with explicit location permission."""
from PySide6.QtCore import Qt, QTimer, QUrl, QRectF, Slot
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QDesktopServices
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QStyle, QApplication

MAP_URL = 'https://www.google.com/maps/@?api=1&map_action=map&hl=en'


def trusted_location_origin(origin):
    return origin.scheme() == 'https' and origin.host() == 'www.google.com' and origin.port(443) == 443


class ReactorBadge(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(124, 124)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(50)

    @Slot()
    def tick(self):
        if self.isVisible():
            self.angle = (self.angle + 1) % 360
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor('#287b9f'), 1))
        painter.drawEllipse(QRectF(5, 5, 114, 114))
        painter.setPen(QPen(QColor('#5edaff'), 2))
        for i in range(8):
            painter.drawArc(QRectF(12, 12, 100, 100), int((self.angle + i * 45) * 16), 27 * 16)
        painter.setPen(QPen(QColor('#2c9fda'), 2))
        painter.drawEllipse(QRectF(27, 27, 70, 70))
        painter.setPen(QColor('#b7f4ff'))
        painter.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'JARVIS')


class GoogleLocationWidget(QWidget):
    shared_profile = None
    def __init__(self):
        super().__init__()
        self.view = None
        self.setStyleSheet('QWidget{background:#050b10;color:#9ce7f6;} QLabel{padding:6px;} QPushButton{background:#10252d;border:1px solid #285c6c;border-radius:4px;}')
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.status = QLabel('GOOGLE MAPS / LOADING')
        self.status.setWordWrap(True)
        bar.addWidget(self.status, 1)
        self.reload_button = QPushButton()
        self.reload_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        self.reload_button.setToolTip('Reload Google Maps')
        self.reload_button.setFixedSize(34, 32)
        self.reload_button.clicked.connect(self.reload_map)
        bar.addWidget(self.reload_button)
        settings = QPushButton()
        settings.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        settings.setToolTip('Windows location settings')
        settings.setFixedSize(34, 32)
        settings.clicked.connect(lambda: QDesktopServices.openUrl(QUrl('ms-settings:privacy-location')))
        bar.addWidget(settings)
        root.addLayout(bar)
        try:
            from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings, QWebEngineScript
            from PySide6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            self.status.setText('Google Maps component missing. Run INSTALL_JARVIS.bat.')
            self.reload_button.setEnabled(False)
            return
        # Off-the-record: map cookies and grants do not outlive this app session.
        if type(self).shared_profile is None:
            type(self).shared_profile = QWebEngineProfile(QApplication.instance())
        self.profile = type(self).shared_profile
        self.view = QWebEngineView(self)
        page = QWebEnginePage(self.profile, self.view)
        page.setBackgroundColor(QColor('#050b10'))
        self.view.setPage(page)
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.ForceDarkMode, True)
        dark_map = QWebEngineScript()
        dark_map.setName('JarvisDarkMap')
        dark_map.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentReady)
        dark_map.setWorldId(QWebEngineScript.ScriptWorldId.ApplicationWorld)
        dark_map.setSourceCode("""
            if (location.hostname === 'www.google.com' && location.pathname.startsWith('/maps')) {
                const style = document.createElement('style');
                style.textContent = 'canvas { filter: invert(1) hue-rotate(180deg) saturate(.65) !important; }';
                document.head.appendChild(style);
            }
        """)
        page.scripts().insert(dark_map)
        if hasattr(page, 'permissionRequested'):
            page.permissionRequested.connect(self.permission_requested)
        else:
            page.featurePermissionRequested.connect(self.legacy_permission_requested)
        self.view.loadFinished.connect(self.loaded)
        root.addWidget(self.view, 1)
        # A separate footer keeps the animated core clear of Google's controls and attribution.
        footer = QHBoxLayout()
        label = QLabel('J.A.R.V.I.S. / LOCATION\nGOOGLE MAPS')
        footer.addWidget(label, 1)
        footer.addWidget(ReactorBadge(self))
        root.addLayout(footer)
        self.view.setUrl(QUrl(MAP_URL))

    def reload_map(self):
        if self.view:
            self.view.setUrl(QUrl(MAP_URL))

    def loaded(self, ok):
        self.status.setText('GOOGLE MAPS / READY' if ok else 'GOOGLE MAPS / LOAD FAILED - CHECK INTERNET')

    def consent(self, origin):
        if not trusted_location_origin(origin):
            return False
        result = QMessageBox.question(self, 'Google Maps location',
            'Allow Google Maps to access your device location in this window?\n\n'
            'Google receives the position supplied by Windows. Accuracy depends on '
            'your device and Windows location settings. JARVIS does not save it.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        allowed = result == QMessageBox.StandardButton.Yes
        self.status.setText('LOCATION / ACCESS ALLOWED' if allowed else 'LOCATION / ACCESS DENIED')
        return allowed

    def permission_requested(self, permission):
        from PySide6.QtWebEngineCore import QWebEnginePermission
        if permission.permissionType() == QWebEnginePermission.PermissionType.Geolocation and self.consent(permission.origin()):
            permission.grant()
        else:
            permission.deny()

    def legacy_permission_requested(self, origin, feature):
        from PySide6.QtWebEngineCore import QWebEnginePage
        allowed = feature == QWebEnginePage.Feature.Geolocation and self.consent(origin)
        policy = QWebEnginePage.PermissionPolicy.PermissionGrantedByUser if allowed else QWebEnginePage.PermissionPolicy.PermissionDeniedByUser
        self.view.page().setFeaturePermission(origin, feature, policy)
