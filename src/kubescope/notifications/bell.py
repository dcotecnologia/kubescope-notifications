"""The bell of the top bar, with the number of notifications not read."""

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QPushButton, QWidget

BADGE = QColor("#e5484d")


def bell_icon(color: str = "#ffffff") -> QIcon:
    """A bell drawn three times larger, so its edges stay smooth."""
    scale = 3
    pixmap = QPixmap(18 * scale, 18 * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(scale, scale)
    body = QPainterPath()
    body.moveTo(9, 2.2)
    body.cubicTo(5.6, 2.2, 4.4, 4.8, 4.4, 7.4)
    body.lineTo(4.4, 10.6)
    body.lineTo(2.8, 12.6)
    body.lineTo(2.8, 13.4)
    body.lineTo(15.2, 13.4)
    body.lineTo(15.2, 12.6)
    body.lineTo(13.6, 10.6)
    body.lineTo(13.6, 7.4)
    body.cubicTo(13.6, 4.8, 12.4, 2.2, 9, 2.2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawPath(body)
    painter.drawEllipse(QPointF(9, 15.1), 1.9, 1.5)  # the clapper
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    icon = QIcon()
    icon.addPixmap(pixmap, QIcon.Mode.Normal)
    icon.addPixmap(pixmap, QIcon.Mode.Disabled)
    return icon


class Bell(QPushButton):
    """A flat 32 px button like the one of the Settings, which shows a red
    badge when something was not read."""

    def __init__(
        self,
        tooltip: str,
        themed: Callable[[str, bool], str] = lambda color, text: color,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.unread = 0
        self.setObjectName("notificationsBell")
        self.setFixedSize(32, 32)
        self.setIcon(bell_icon())
        self.setIconSize(QSize(18, 18))
        self.setToolTip(tooltip)
        self.setCheckable(True)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.restyle(themed)

    def restyle(self, themed: Callable[[str, bool], str]) -> None:
        """Dress it as the Settings button beside it is, in the colors of the
        theme in use: the top bar has colors of its own in each theme, and the
        light ones written here would show through in the others."""
        hover = themed("#0d315d", False)
        selected = themed("#1f4f87", False)
        self.setStyleSheet(
            "QPushButton#notificationsBell { background: transparent;"
            " border: 1px solid transparent; border-radius: 4px; padding: 0; }"
            f"QPushButton#notificationsBell:hover {{ background: {hover}; }}"
            f"QPushButton#notificationsBell:checked {{ background: {selected}; }}"
        )

    def set_unread(self, count: int) -> None:
        self.unread = max(count, 0)
        self.update()

    def badge_text(self) -> str:
        return "99+" if self.unread > 99 else str(self.unread)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self.unread:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        text = self.badge_text()
        font = QFont(self.font())
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        width = max(14, painter.fontMetrics().horizontalAdvance(text) + 8)
        rect = QRectF(self.width() - width - 1, 1, width, 14)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(BADGE)
        painter.drawRoundedRect(rect, 7, 7)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
