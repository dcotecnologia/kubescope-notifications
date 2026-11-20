"""The panel that slides in from the right with the notifications, the newest
first."""

from collections.abc import Callable

from PySide6.QtCore import (
    QCoreApplication,
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from kubescope.notifications.store import ERROR, Notification

WIDTH = 400
SHOWN = 200  # the cards drawn; the store keeps more
SLIDE_MS = 220


def ago(seconds: float) -> str:
    """How long ago, the way the lists of the app say it."""
    seconds = max(int(seconds), 0)
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return QCoreApplication.translate(
                "NotificationPanel", "{amount}{unit} ago"
            ).format(amount=seconds // size, unit=unit)
    return QCoreApplication.translate("NotificationPanel", "just now")


def style(themed: Callable[[str, bool], str]) -> str:
    """The style sheet of the panel, in the colors of the theme in use."""
    return f"""
QFrame#notificationPanel {{
    background: {themed("#ffffff", False)};
    border-left: 1px solid {themed("#e1e3e9", False)};
}}
QLabel#notificationTitle {{
    color: {themed("#17191e", True)}; font-size: 15px; font-weight: 700;
}}
QLabel#notificationEmpty {{ color: {themed("#6b7380", True)}; }}
QScrollArea#notificationScroll, QWidget#notificationList {{
    background: transparent; border: 0;
}}
QFrame#notificationCard {{
    background: {themed("#f3f4f7", False)};
    border: 1px solid {themed("#e1e3e9", False)}; border-radius: 8px;
}}
QFrame#notificationCard[level="error"] {{
    border-left: 3px solid {themed("#a33d45", False)};
}}
QFrame#notificationCard[level="warning"] {{
    border-left: 3px solid {themed("#985415", False)};
}}
QLabel#notificationReason {{
    color: {themed("#20232a", True)}; font-weight: 700;
}}
QLabel#notificationMessage {{ color: {themed("#20232a", True)}; }}
QLabel#notificationMeta {{ color: {themed("#6b7380", True)}; font-size: 10px; }}
"""


class Card(QFrame):
    """One notification."""

    def __init__(self, item: Notification, now: float) -> None:
        super().__init__()
        self.setObjectName("notificationCard")
        self.setProperty("level", item.level)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(3)
        head = QHBoxLayout()
        reason = QLabel(
            item.reason or QCoreApplication.translate("NotificationPanel", "Event")
        )
        reason.setObjectName("notificationReason")
        level = (
            QCoreApplication.translate("NotificationPanel", "Error")
            if item.level == ERROR
            else QCoreApplication.translate("NotificationPanel", "Warning")
        )
        kind = QLabel(level)
        kind.setObjectName("notificationMeta")
        head.addWidget(reason)
        head.addStretch(1)
        head.addWidget(kind)
        layout.addLayout(head)
        about = " · ".join(
            part
            for part in (
                f"{item.kind}/{item.name}" if item.name else "",
                item.namespace,
            )
            if part
        )
        if about:
            where = QLabel(about)
            where.setObjectName("notificationMeta")
            layout.addWidget(where)
        message = QLabel(item.message)
        message.setObjectName("notificationMessage")
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(message)
        times = f"{item.count}× · " if item.count > 1 else ""
        when = QLabel(times + ago(now - item.last_seen))
        when.setObjectName("notificationMeta")
        layout.addWidget(when)


class NotificationPanel(QFrame):
    """Sits on `host`, under the top bar, and slides in and out at its right
    edge."""

    def __init__(
        self,
        host: QWidget,
        themed: Callable[[str, bool], str],
        top: Callable[[], int],
    ) -> None:
        super().__init__(host)
        self.host = host
        self._themed = themed
        self._top = top
        self.setObjectName("notificationPanel")
        self.setFixedWidth(WIDTH)
        self.hide()
        self.opened = False
        self.on_closed: Callable[[], None] = lambda: None
        self.on_clear: Callable[[], None] = lambda: None
        self.on_mark_read: Callable[[], None] = lambda: None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel(QCoreApplication.translate("NotificationPanel", "Notifications"))
        title.setObjectName("notificationTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.mark_read = QPushButton(
            QCoreApplication.translate("NotificationPanel", "Mark all as read")
        )
        self.clear_all = QPushButton(
            QCoreApplication.translate("NotificationPanel", "Clear")
        )
        self.close_button = QPushButton("✕")
        for button in (self.mark_read, self.clear_all):
            button.setProperty("variant", "secondary")  # the buttons of the app
            header.addWidget(button)
        self.close_button.setProperty("variant", "link")
        header.addWidget(self.close_button)
        self.mark_read.clicked.connect(lambda: self.on_mark_read())
        self.clear_all.clicked.connect(lambda: self.on_clear())
        self.close_button.clicked.connect(self.close_panel)
        layout.addLayout(header)

        self.scroller = QScrollArea()
        self.scroller.setObjectName("notificationScroll")
        self.scroller.setWidgetResizable(True)
        self.scroller.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.list = QWidget()
        self.list.setObjectName("notificationList")
        self.rows = QVBoxLayout(self.list)
        self.rows.setContentsMargins(0, 0, 4, 0)
        self.rows.setSpacing(8)
        self.scroller.setWidget(self.list)
        layout.addWidget(self.scroller, 1)

        self.animation = QPropertyAnimation(self, b"pos", self)
        self.animation.setDuration(SLIDE_MS)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.finished.connect(self._slid)
        # Esc closes it, but only while it is open, so the key stays free for
        # the rest of the window the rest of the time
        self._escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), host)
        self._escape.setContext(Qt.ShortcutContext.WindowShortcut)
        self._escape.setEnabled(False)
        self._escape.activated.connect(self.close_panel)
        host.installEventFilter(self)
        self.restyle()

    def restyle(self) -> None:
        self.setStyleSheet(style(self._themed))

    def show_items(self, items: list[Notification], now: float) -> None:
        """Draw the notifications, the newest first."""
        while (child := self.rows.takeAt(0)) is not None:
            if (widget := child.widget()) is not None:
                widget.deleteLater()
        if not items:
            empty = QLabel(
                QCoreApplication.translate(
                    "NotificationPanel",
                    "Nothing to report. Warnings and errors will show here.",
                )
            )
            empty.setObjectName("notificationEmpty")
            empty.setWordWrap(True)
            self.rows.addWidget(empty)
        for item in items[:SHOWN]:
            self.rows.addWidget(Card(item, now))
        self.rows.addStretch(1)
        self.mark_read.setEnabled(bool(items))
        self.clear_all.setEnabled(bool(items))

    def _geometry(self) -> tuple[QPoint, QPoint]:
        top = self._top()
        self.setFixedHeight(max(self.host.height() - top, 0))
        shown = QPoint(self.host.width() - WIDTH, top)
        return shown, QPoint(self.host.width(), top)

    def open_panel(self) -> None:
        shown, hidden = self._geometry()
        self.opened = True
        self._escape.setEnabled(True)
        self.move(hidden)
        self.show()
        self.raise_()
        self.animation.stop()
        self.animation.setStartValue(hidden)
        self.animation.setEndValue(shown)
        self.animation.start()

    def close_panel(self) -> None:
        if not self.opened:
            return
        shown, hidden = self._geometry()
        self.opened = False
        self._escape.setEnabled(False)
        self.animation.stop()
        self.animation.setStartValue(self.pos())
        self.animation.setEndValue(hidden)
        self.animation.start()
        self.on_closed()

    def _slid(self) -> None:
        if not self.opened:
            self.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Follow the window as it is resized."""
        if (
            watched is self.host
            and event.type() == QEvent.Type.Resize
            and self.opened
            and self.animation.state() != QPropertyAnimation.State.Running
        ):
            shown, _hidden = self._geometry()
            self.move(shown)
        return False
