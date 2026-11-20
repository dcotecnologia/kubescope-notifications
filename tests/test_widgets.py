from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QLabel, QWidget

from kubescope.notifications.bell import Bell, bell_icon
from kubescope.notifications.panel import (
    MAX_WIDTH,
    MIN_WIDTH,
    SHOWN,
    WIDTH,
    NotificationPanel,
    ago,
    style,
)
from kubescope.notifications.store import notification_of


def test_the_badge_counts_and_stops_at_99() -> None:
    bell = Bell("Notifications")
    bell.resize(32, 32)
    assert bell.badge_text() == "0"

    bell.set_unread(7)
    assert bell.badge_text() == "7"
    bell.grab()  # paints the badge
    bell.set_unread(250)
    assert bell.badge_text() == "99+"
    bell.grab()
    bell.set_unread(-3)
    assert bell.unread == 0
    bell.grab()  # nothing to paint over the icon
    assert not bell_icon().isNull()


def test_the_time_is_said_the_way_the_lists_say_it() -> None:
    assert ago(5) == "just now"
    assert ago(-5) == "just now"
    assert ago(120) == "2m ago"
    assert ago(7200) == "2h ago"
    assert ago(3 * 86400) == "3d ago"


def test_the_style_has_the_colors_of_the_theme() -> None:
    assert "#ffffff" in style(lambda color, text: color)


def make_panel(host: QWidget | None = None) -> NotificationPanel:
    host = host or QWidget()
    host.resize(900, 600)
    return NotificationPanel(host, lambda color, text: color, lambda: 50)


def texts(panel: NotificationPanel) -> list[str]:
    return [label.text() for label in panel.list.findChildren(QLabel)]


def test_the_cards_say_what_happened_and_how_long_ago(make_event) -> None:
    panel = make_panel()
    mine = notification_of("prod", make_event(count=4, last_seen=1000.0))
    bare = notification_of(
        "prod", make_event("b", reason="", name="", namespace="", last_seen=1000.0)
    )

    panel.show_items([mine, bare], now=1180.0)

    shown = texts(panel)
    assert "BackOff" in shown and "Event" in shown
    assert "Back-off restarting failed container" in shown
    assert "prod · Pod/api · ns" in shown  # the context is named
    assert "4× · 3m ago" in shown
    assert "1× · 3m ago" not in shown and "3m ago" in shown
    assert panel.mark_read.isEnabled()


def test_an_empty_panel_says_there_is_nothing_and_has_nothing_to_clear() -> None:
    panel = make_panel()

    panel.show_items([], now=0.0)

    assert any("Nothing to report" in text for text in texts(panel))
    assert not panel.mark_read.isEnabled() and not panel.clear_all.isEnabled()


def test_only_the_newest_cards_are_drawn(make_event) -> None:
    panel = make_panel()
    items = [
        notification_of("p", make_event(str(n), last_seen=float(n)))
        for n in range(SHOWN + 5)
    ]

    panel.show_items(items, now=1e6)

    assert len(panel.list.findChildren(QLabel, "notificationReason")) == SHOWN
    panel.show_items([], now=0.0)  # the cards are replaced, not piled up


def test_it_slides_in_from_the_right_and_out_again() -> None:
    host = QWidget()
    panel = make_panel(host)
    host.show()  # a hidden widget is told of its new size only when it is shown
    closed: list[bool] = []
    panel.on_closed = lambda: closed.append(True)

    panel.close_panel()  # closed already: nothing happens
    assert closed == []

    panel.open_panel()
    assert panel.opened
    panel.animation.setCurrentTime(panel.animation.duration())
    panel.animation.finished.emit()
    assert panel.pos() == QPoint(900 - WIDTH, 50)
    assert panel.height() == 550

    host.resize(1000, 700)  # the window is resized with the panel open
    assert panel.pos() == QPoint(1000 - WIDTH, 50)

    panel.close_panel()
    assert closed == [True] and not panel.opened
    panel.animation.setCurrentTime(panel.animation.duration())
    panel.animation.finished.emit()
    assert panel.isHidden()
    assert panel.pos().x() == 1000

    host.resize(1100, 700)  # closed: it stays where it is
    assert panel.pos().x() == 1000


def test_the_buttons_of_the_header_call_what_they_were_given() -> None:
    panel = make_panel()
    calls: list[str] = []
    panel.on_mark_read = lambda: calls.append("read")
    panel.on_clear = lambda: calls.append("clear")
    panel.show_items([], now=0.0)
    panel.mark_read.setEnabled(True)
    panel.clear_all.setEnabled(True)

    panel.mark_read.click()
    panel.clear_all.click()
    panel.restyle()

    assert calls == ["read", "clear"]


def test_esc_closes_it_only_while_it_is_open() -> None:
    host = QWidget()
    panel = make_panel(host)
    closed: list[bool] = []
    panel.on_closed = lambda: closed.append(True)
    assert not panel._escape.isEnabled()  # closed: the key is the window's

    panel.open_panel()
    assert panel._escape.isEnabled()
    panel._escape.activated.emit()

    assert closed == [True] and not panel.opened
    assert not panel._escape.isEnabled()


def test_a_notice_of_the_app_shows_its_title_and_how_serious_it_is(tmp_path) -> None:
    from kubescope.notifications.store import NotificationStore

    store = NotificationStore(tmp_path / "n.json")
    store.add_notice(
        "info",
        "KubeScope update available",
        "Version 9 is available",
        "u",
        False,
        100.0,
    )
    store.add_notice("error", "Boom", "it broke", "e", False, 100.0)
    panel = make_panel()

    panel.show_items(store.items(), now=160.0)

    shown = texts(panel)
    assert "KubeScope update available" in shown and "Info" in shown
    assert "Boom" in shown and "Error" in shown
    assert "Version 9 is available" in shown


def test_it_is_dragged_by_its_left_edge_and_the_width_is_handed_on() -> None:
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    host = QWidget()
    panel = make_panel(host)
    host.show()
    kept: list[int] = []
    panel.on_resized = kept.append
    panel.open_panel()
    panel.animation.setCurrentTime(panel.animation.duration())
    panel.animation.finished.emit()

    def mouse(kind: QEvent.Type, x: float) -> None:
        event = QMouseEvent(
            kind,
            QPointF(2, 20),
            QPointF(x, 20),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(panel.grip, event)

    mouse(QEvent.Type.MouseMove, 500.0)  # no press yet: nothing moves
    assert panel.width() == WIDTH
    mouse(QEvent.Type.MouseButtonPress, 600.0)
    mouse(QEvent.Type.MouseMove, 520.0)  # 80 px to the left: 80 px wider
    assert panel.width() == WIDTH + 80
    assert panel.pos().x() == 900 - (WIDTH + 80)  # it stays at the right edge
    mouse(QEvent.Type.MouseButtonRelease, 520.0)
    assert kept == [WIDTH + 80]
    mouse(QEvent.Type.MouseButtonRelease, 520.0)  # one release only
    assert kept == [WIDTH + 80]


def test_the_width_stays_within_what_is_usable_and_what_the_window_allows() -> None:
    host = QWidget()
    panel = make_panel(host)

    panel.set_panel_width(10)
    assert panel.width() == MIN_WIDTH
    panel.set_panel_width(10**6)
    assert panel.width() == 900 - 40  # the window has room for 40 px of its own
    host.resize(380, 600)  # a window narrower than the panel
    panel.open_panel()
    assert panel.width() == 340
    assert panel.width() < MAX_WIDTH
