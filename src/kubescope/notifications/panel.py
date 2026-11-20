"""The panel that slides in from the right with the notifications, the newest
first."""

from collections.abc import Callable

from PySide6.QtCore import (
    QCoreApplication,
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from kubescope.notifications.store import ERROR, INFO, Notification

WIDTH = 400  # the usual width, which can be dragged
MIN_WIDTH = 300
MAX_WIDTH = 900
GRIP = 6  # the strip at the left edge that is dragged
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
QFrame#notificationCard[level="info"] {{
    border-left: 3px solid {themed("#3220a0", False)};
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


class _Grip(QWidget):
    """The strip at the left edge of the panel, which is dragged to make it
    wider or narrower."""

    dragged = Signal(int)  # the width the panel should have
    released = Signal()

    def __init__(self, panel: QWidget) -> None:
        super().__init__(panel)
        self._panel = panel
        self._origin: QPointF | None = None
        self._start = 0
        self.setCursor(Qt.CursorShape.SizeHorCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._origin = event.globalPosition()
        self._start = self._panel.width()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._origin is not None:
            moved = event.globalPosition() - self._origin
            self.dragged.emit(self._start - int(moved.x()))  # leftward is wider

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._origin is not None:
            self._origin = None
            self.released.emit()


class Card(QFrame):
    """One notification."""

    def __init__(
        self,
        item: Notification,
        now: float,
        opened: Callable[[Notification], None] = lambda _item: None,
    ) -> None:
        super().__init__()
        self.item = item
        self._opened = opened
        self.setObjectName("notificationCard")
        if item.context:  # one of a cluster: a click goes to its context
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip(
                QCoreApplication.translate(
                    "NotificationPanel", "Open the context {context}"
                ).format(context=item.context)
            )
        self.setProperty("level", item.level)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(3)
        head = QHBoxLayout()
        reason = QLabel(
            item.reason or QCoreApplication.translate("NotificationPanel", "Event")
        )
        reason.setObjectName("notificationReason")
        reason.setWordWrap(True)
        level = {
            ERROR: QCoreApplication.translate("NotificationPanel", "Error"),
            INFO: QCoreApplication.translate("NotificationPanel", "Info"),
        }.get(item.level, QCoreApplication.translate("NotificationPanel", "Warning"))
        kind = QLabel(level)
        kind.setObjectName("notificationMeta")
        head.addWidget(reason)
        head.addStretch(1)
        head.addWidget(kind)
        layout.addLayout(head)
        about = " · ".join(
            part
            for part in (
                item.context,
                f"{item.kind}/{item.name}" if item.name else "",
                item.namespace,
            )
            if part
        )
        if about:
            where = QLabel(about)
            where.setObjectName("notificationMeta")
            where.setWordWrap(True)
            layout.addWidget(where)
        message = QLabel(item.message)
        message.setObjectName("notificationMessage")
        message.setWordWrap(True)
        layout.addWidget(message)
        times = f"{item.count}× · " if item.count > 1 else ""
        when = QLabel(times + ago(now - item.last_seen))
        when.setObjectName("notificationMeta")
        layout.addWidget(when)
        for label in self.findChildren(QLabel):  # the click is the card's
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            self.item.context
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self._opened(self.item)
        super().mouseReleaseEvent(event)


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
        self._width = WIDTH
        self.setFixedWidth(WIDTH)
        self.hide()
        self.opened = False
        self.on_closed: Callable[[], None] = lambda: None
        self.on_clear: Callable[[], None] = lambda: None
        self.on_mark_read: Callable[[], None] = lambda: None
        self.on_resized: Callable[[int], None] = lambda width: None
        self.on_open: Callable[[Notification], None] = lambda item: None

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
        self.grip = _Grip(self)
        self.grip.dragged.connect(self.set_panel_width)
        self.grip.released.connect(lambda: self.on_resized(self._width))
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
            self.rows.addWidget(Card(item, now, lambda one: self.on_open(one)))
        self.rows.addStretch(1)
        self.mark_read.setEnabled(bool(items))
        self.clear_all.setEnabled(bool(items))

    def set_panel_width(self, width: int) -> None:
        """Give the panel a width, within what keeps it usable; while it is
        open it stays at the right edge."""
        self._width = min(max(width, MIN_WIDTH), MAX_WIDTH)
        if self.opened and self.animation.state() != QPropertyAnimation.State.Running:
            shown, _hidden = self._geometry()
            self.move(shown)
        else:
            self.setFixedWidth(self._fitted())
        self._place_grip()

    def _fitted(self) -> int:
        """The width it has now: the one chosen, as far as the window lets."""
        room = max(self.host.width() - 40, 200)
        return min(self._width, MAX_WIDTH, room)

    def _place_grip(self) -> None:
        self.grip.setGeometry(0, 0, GRIP, self.height())
        self.grip.raise_()

    def _geometry(self) -> tuple[QPoint, QPoint]:
        top = self._top()
        width = self._fitted()
        self.setFixedSize(width, max(self.host.height() - top, 0))
        self._place_grip()
        shown = QPoint(self.host.width() - width, top)
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
