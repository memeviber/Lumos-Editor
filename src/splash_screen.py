import logging
from pathlib import Path

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication, QSplashScreen

from .theme_manager import theme

logger = logging.getLogger(__name__)


class StartupSplash(QSplashScreen):
    def __init__(self):
        logger.debug("Creating startup splash screen")
        super().__init__(self._create_pixmap(), Qt.WindowStaysOnTopHint)
        self.showMessage(
            "Starting Lumos Editor...",
            Qt.AlignHCenter | Qt.AlignBottom,
            QColor(theme.color22),
        )

    @staticmethod
    def _create_pixmap():
        screen = QApplication.primaryScreen()
        scale = 1.0
        if screen is not None:
            scale = max(
                screen.devicePixelRatio(),
                screen.logicalDotsPerInch() / 96.0,
            )

        width, height = 500, 240
        pixmap = QPixmap(round(width * scale), round(height * scale))
        pixmap.setDevicePixelRatio(scale)
        pixmap.fill(QColor(theme.color6))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.fillRect(0, 0, width, 4, QColor(theme.color38))

        logo_path = (
            Path(__file__).resolve().parent.parent / "resources" / "lumos-icon.png"
        )
        logo = QPixmap(str(logo_path))
        if not logo.isNull():
            painter.drawPixmap(
                QRectF(58, 76, 64, 64),
                logo,
                QRectF(0, 0, logo.width(), logo.height()),
            )

        painter.setPen(QColor(theme.color27))
        painter.setFont(QFont("Segoe UI", 25, QFont.DemiBold))
        painter.drawText(144, 111, "LUMOS EDITOR")

        painter.setPen(QColor(theme.color22))
        painter.setFont(QFont("Segoe UI", 11))
        painter.drawText(146, 139, "Your workspace is getting ready")

        painter.setPen(QColor(theme.color1))
        painter.drawLine(58, 181, 442, 181)
        painter.end()
        return pixmap

    def mousePressEvent(self, event):
        event.ignore()
