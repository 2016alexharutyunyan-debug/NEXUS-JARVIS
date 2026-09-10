"""Non-activating desktop voice indicator shown when JARVIS is minimized."""
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF, Signal, Slot
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QGuiApplication
from PySide6.QtWidgets import QWidget, QMenu, QApplication


def voice_label(message, enabled=True):
    if not enabled:
        return 'PAUSED'
    text = message.upper()
    if 'ERROR' in text or 'FAILED' in text:
        return 'ERROR'
    if 'SPEAKING' in text or 'VOICE ENGINE' in text:
        return 'SPEAKING'
    if 'THINKING' in text or 'BUSY' in text:
        return 'THINKING'
    if 'LISTENING' in text or 'HEARD' in text or 'READY' in text:
        return 'LISTENING'
    return 'STARTING'


class MiniJarvis(QWidget):
    restore_requested = Signal()
    listening_toggled = Signal(bool)
    exit_requested = Signal()
    screen_toggled = Signal(bool)

    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFixedSize(112, 154)
        self.setWindowTitle('JARVIS Mini Voice')
        self.setToolTip('Restore JARVIS. Drag to move. Right-click for voice controls.')
        self.enabled = True
        self.state = 'STARTING'
        self.screen_state = 'SCREEN OFF'
        self.screen_active = False
        self.angle = 0
        self.press_position = None
        self.start_position = QPoint()
        self.dragging = False
        self.placed = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(50)
        self.setAccessibleName('JARVIS floating voice control')

    @Slot()
    def animate(self):
        if self.isVisible() and self.enabled:
            self.angle = (self.angle + 2) % 360
            self.update()

    def set_voice_status(self, message, enabled=True):
        self.enabled = enabled
        self.state = voice_label(message, enabled)
        self.setAccessibleDescription(self.state)
        self.update()

    def set_screen_status(self, message):
        self.screen_state = message
        self.screen_active = message != 'SCREEN OFF'
        self.update()

    def show_near(self, screen=None):
        screen = screen or QGuiApplication.primaryScreen()
        if not self.placed and screen:
            area = screen.availableGeometry()
            self.move(area.right() - self.width() - 24, area.bottom() - self.height() - 24)
            self.placed = True
        self.clamp_to_screen()
        self.show()
        self.raise_()

    def clamp_to_screen(self):
        screen = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(max(area.left(), min(self.x(), area.right() - self.width() + 1)),
                      max(area.top(), min(self.y(), area.bottom() - self.height() + 1)))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        accent = QColor('#f0ae6c' if self.state == 'ERROR' else '#6c8190' if not self.enabled else '#59dfff')
        p.setBrush(QColor('#06141e'))
        p.setPen(QPen(QColor('#205573'), 1))
        p.drawEllipse(QRectF(4, 4, 104, 104))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(accent, 2))
        for i in range(8):
            p.drawArc(QRectF(10, 10, 92, 92), int((i * 45 + self.angle) * 16), 28 * 16)
        p.setPen(QPen(QColor('#198ac6'), 2))
        p.drawEllipse(QRectF(23, 23, 66, 66))
        p.setPen(QPen(accent, 1))
        p.drawArc(QRectF(29, 29, 54, 54), -self.angle * 16, 250 * 16)
        p.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        p.setPen(QColor('#c7f6ff'))
        p.drawText(QRectF(10, 40, 92, 29), Qt.AlignmentFlag.AlignCenter, 'JARVIS')
        p.setBrush(accent)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(52, 77, 8, 8))
        p.setBrush(QColor('#07131c'))
        p.drawRoundedRect(QRectF(1, 113, 110, 20), 4, 4)
        p.setPen(accent)
        p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
        p.drawText(QRectF(1, 113, 110, 20), Qt.AlignmentFlag.AlignCenter, self.state)
        p.setBrush(QColor('#07131c'))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(1, 134, 110, 20), 4, 4)
        p.setPen(QColor('#efc675') if self.screen_active else QColor('#84949c'))
        p.setFont(QFont('Segoe UI', 7, QFont.Weight.Bold))
        p.drawText(QRectF(1, 134, 110, 20), Qt.AlignmentFlag.AlignCenter, self.screen_state)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_position = event.globalPosition().toPoint()
            self.start_position = self.pos()
            self.dragging = False
            event.accept()

    def mouseMoveEvent(self, event):
        if self.press_position is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.press_position
            if delta.manhattanLength() >= QApplication.startDragDistance():
                self.dragging = True
            if self.dragging:
                self.move(self.start_position + delta)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.press_position is not None:
            self.press_position = None
            if self.dragging:
                self.clamp_to_screen()
            else:
                self.restore_requested.emit()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet('QMenu{background:#081822;color:#c7f6ff;border:1px solid #27718c;}QMenu::item{padding:8px 16px;}QMenu::item:selected{background:#16445b;}')
        menu.addAction('Restore JARVIS', self.restore_requested.emit)
        pause = menu.addAction('Pause listening')
        pause.setCheckable(True)
        pause.setChecked(not self.enabled)
        pause.triggered.connect(lambda checked: self.listening_toggled.emit(not checked))
        screen = menu.addAction('Screen access')
        screen.setCheckable(True)
        screen.setChecked(self.screen_active)
        screen.triggered.connect(self.screen_toggled.emit)
        menu.addSeparator()
        menu.addAction('Exit JARVIS', self.exit_requested.emit)
        menu.exec(event.globalPos())
