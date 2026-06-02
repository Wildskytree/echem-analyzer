"""Splash screen shown during GUI startup."""

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen


class SplashScreen(QSplashScreen):
    """QSplashScreen with app identity and a simple progress bar."""

    def __init__(self, app_name: str, version: str):
        pixmap = QPixmap(520, 300)
        pixmap.fill(QColor("#f7fafc"))
        super().__init__(pixmap)
        self._app_name = app_name
        self._version = version
        self._progress = 0
        self._message = "正在启动..."
        self.setWindowFlag(Qt.WindowStaysOnTopHint)

    def show_progress(self, progress: int, message: str):
        self._progress = max(0, min(100, int(progress)))
        self._message = message
        self.showMessage(
            f"{message}  {self._progress}%",
            Qt.AlignLeft | Qt.AlignBottom,
            QColor("#334155"),
        )
        self.repaint()

    def drawContents(self, painter: QPainter):
        painter.setRenderHint(QPainter.Antialiasing)

        painter.fillRect(self.rect(), QColor("#f7fafc"))
        painter.fillRect(QRect(0, 0, self.width(), 84), QColor("#1f4b63"))

        painter.setPen(QColor("#ffffff"))
        title_font = QFont()
        title_font.setPointSize(26)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(32, 56, self._app_name)

        painter.setPen(QColor("#dbeafe"))
        version_font = QFont()
        version_font.setPointSize(11)
        painter.setFont(version_font)
        painter.drawText(34, 104, self._version)

        painter.setPen(QColor("#334155"))
        body_font = QFont()
        body_font.setPointSize(11)
        painter.setFont(body_font)
        painter.drawText(34, 168, self._message)

        bar_rect = QRect(34, 206, self.width() - 68, 12)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#e2e8f0"))
        painter.drawRoundedRect(bar_rect, 6, 6)

        fill_width = int(bar_rect.width() * self._progress / 100)
        if fill_width > 0:
            painter.setBrush(QColor("#2f80ed"))
            painter.drawRoundedRect(
                QRect(bar_rect.left(), bar_rect.top(), fill_width, bar_rect.height()),
                6,
                6,
            )

        painter.setPen(QColor("#64748b"))
        painter.drawText(34, 248, "PySide6 + Matplotlib + NumPy/SciPy")
