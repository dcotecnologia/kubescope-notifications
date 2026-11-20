"""What the app calls to run the notifications: a bell in the top bar, a look
at the events of the cluster from time to time, and the panel."""

import time
from collections.abc import Callable
from functools import partial

from kubescope.sdk import (
    CONTEXT_CHANGED,
    NOTIFICATION,
    SHUTDOWN,
    THEME_CHANGED,
    Context,
)
from PySide6.QtCore import QCoreApplication, QObject, QPoint, QTimer

from kubescope.notifications.bell import Bell
from kubescope.notifications.panel import NotificationPanel
from kubescope.notifications.reader import Backoff, read_all
from kubescope.notifications.settings import NotificationSettings
from kubescope.notifications.settings_panel import NotificationSettingsPanel
from kubescope.notifications.store import ERROR, INFO, Notification, NotificationStore

TITLE = "Notifications"
GAP = 6  # between the top bar and the panel
FIRST_LOOK_MS = 30_000  # before the first look at the clusters
SINCE = 60.0  # seconds before the start from which an event is still news
SHOWN_IN_A_NOTICE = 3  # notifications named in one notice of the system
MESSAGE_LIMIT = 220  # characters of a message in a notice of the system
REPEAT_WINDOW = 1800.0  # seconds in which the same notice of the app only counts
COOLDOWN = 1800.0  # seconds before the system is told again about the same alert
REASON_LIMIT = 300  # characters of why a context could not be read


def first_line(reason: str) -> str:
    """The first line of what a failure said, cut to what a card can hold."""
    lines = [line.strip() for line in reason.splitlines() if line.strip()]
    return (lines[0] if lines else reason.strip())[:REASON_LIMIT]


class Notifications(QObject):
    """Looks at the events of every context of the kubeconfig every few
    seconds, keeps the Warning ones, shows them, and tells the operating
    system about the new ones."""

    def __init__(
        self,
        ctx: Context,
        settings: NotificationSettings,
        store: NotificationStore,
        now: Callable[[], float] = time.time,
    ) -> None:
        ui = ctx.ui
        assert ui is not None
        super().__init__(ui.window)
        self.ctx = ctx
        self.settings = settings
        self.store = store
        self._now = now
        self._busy = False
        self._since = now() - SINCE  # what happened before is not news
        self.backoff = Backoff()
        self._announced: dict[str, float] = {}  # when the system was told of each
        self.bell = Bell(
            QCoreApplication.translate("NotificationsExtension", "Notifications")
        )
        self.bell.clicked.connect(self.toggle)
        self.panel = NotificationPanel(ui.central, ui.themed, self._panel_top)
        self.panel.on_closed = lambda: self.bell.setChecked(False)
        self.panel.on_mark_read = self.mark_read
        self.panel.on_clear = self.clear
        self.panel.on_open = self.open_context
        self.panel.is_unread = self.store.is_unread
        self.panel.on_resized = lambda width: setattr(
            self.settings, "panel_width", width
        )
        self.panel.set_panel_width(self.settings.panel_width)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        # the first look comes a while after the start, so that an extension
        # reloaded again and again while it is written does not read every
        # cluster each time
        self.first_look = QTimer(self)
        self.first_look.setSingleShot(True)
        self.first_look.timeout.connect(self.poll)
        self.first_look.start(FIRST_LOOK_MS)
        ui.add_top_bar_button(ctx.id, self.bell)
        self.apply_settings()
        self.refresh()

    def _panel_top(self) -> int:
        """Where the panel starts: under the top bar."""
        central = self.panel.host
        return self.bell.mapTo(central, QPoint(0, self.bell.height())).y() + GAP

    def apply_settings(self) -> None:
        """Start (or restart) the look at the cluster at the interval chosen."""
        self.timer.start(self.settings.interval * 1000)

    def poll(self) -> None:
        """Read the events of every context, off the UI thread. Nothing
        happens while the last read is not over; a context that cannot be read
        (it is not signed in) keeps what is kept and is left alone for a
        while."""
        ui = self.ctx.ui
        if ui is None or self._busy:
            return
        self._busy = True
        skip = self.backoff.round()
        ui.run_action(
            read_all,
            self._arrived,
            self.ctx.cluster,
            skip,
            on_error=lambda _reason: self._failed(),
            quiet=True,
        )

    def _failed(self) -> None:
        self._busy = False

    def _arrived(self, result: tuple[list[str], dict]) -> None:
        self._busy = False
        contexts, found = result
        self.backoff.forget(contexts)
        news: list[Notification] = []
        for context, events in found.items():
            key = f"unreadable:{context}"
            if isinstance(events, str):
                self.backoff.failed(context)
                added = self.store.add_notice(
                    "warning",
                    QCoreApplication.translate(
                        "NotificationsExtension", "Could not read {context}"
                    ).format(context=context),
                    first_line(events),
                    key,
                    False,
                    self._now(),
                    context,
                )
                if added:
                    # the errors the app showed for this context say the same
                    self.store.discard_where(
                        lambda one, name=context: (
                            one.context == name
                            and one.level == ERROR
                            and one.key.split("\n", 1)[1].startswith("error:")
                        )
                    )
                if added and (item := self.store.find(key)) is not None:
                    news.append(item)  # told once, when it first cannot be read
                continue
            self.backoff.worked(context)
            self.store.discard(key)  # it can be read again
            news += self.store.merge_changes(context, events)
        self.refresh()
        self.announce([item for item in news if item.last_seen >= self._since])

    def announce(self, items: list[Notification]) -> None:
        """Tell the operating system about what is new, in one notice, unless
        the person turned it off."""
        ui = self.ctx.ui
        if not items or ui is None or not self.settings.system_notifications:
            return
        now = self._now()
        items = [
            one
            for one in items
            if now - self._announced.get(one.key, -COOLDOWN) >= COOLDOWN
        ]
        if not items:
            return  # the same alerts, told a moment ago
        for one in items:
            self._announced[one.key] = now
        items = sorted(items, key=lambda one: one.last_seen, reverse=True)
        if len(items) == 1:
            one = items[0]
            title = one.reason or QCoreApplication.translate(
                "NotificationsExtension", "Notification"
            )
            about = f"{one.kind}/{one.name}" if one.name else ""
            where = " · ".join(part for part in (about, one.context) if part)
            message = f"{where}: {one.message}" if where else one.message
        else:
            title = QCoreApplication.translate(
                "NotificationsExtension", "{count} new notifications"
            ).format(count=len(items))
            message = "\n".join(
                f"{one.reason or one.message} · {one.context}".strip(" ·")
                for one in items[:SHOWN_IN_A_NOTICE]
            )
        click: Callable[[], None] = self.open_panel
        if len(items) == 1 and items[0].context:  # the one notice goes to its context
            click = partial(self.open_context, items[0])
        ui.show_system_notification(title, message[:MESSAGE_LIMIT], click)

    def open_context(self, item: Notification) -> None:
        """Read a notification and go to the context it belongs to, if it is
        about one, leaving the panel."""
        self.store.mark_item_read(item.key, self._now())  # clicking reads it
        self.refresh()
        ui = self.ctx.ui
        if ui is None or not item.context:
            return
        self.ctx.invoke(
            "switch_context",
            context=item.context,
            report=lambda text: ui.show_message("warning", TITLE, text),
        )
        self.panel.close_panel()

    def open_panel(self) -> None:
        """Show the panel, as the bell does; a notice of the system leads here."""
        if not self.panel.opened:
            self.toggle()

    def refresh(self) -> None:
        self.bell.set_unread(self.store.unread())
        self.panel.show_items(self.store.items(), self._now())

    def toggle(self) -> None:
        if self.panel.opened:
            self.panel.close_panel()
            return
        self.panel.show_items(self.store.items(), self._now())
        self.panel.open_panel()
        self.bell.setChecked(True)

    def notice(
        self,
        level: str,
        title: str,
        message: str,
        key: str,
        repeat: bool = False,
        context: str = "",
    ) -> None:
        """The app tells about an error, a warning or an update, and the
        context it is about when it is about one."""
        now = self._now()
        if (
            level == ERROR
            and context
            and self.store.find(f"unreadable:{context}") is not None
        ):
            return  # the context that cannot be read says it already
        if self.store.add_notice(
            level, title, message, key, repeat, now, context, REPEAT_WINDOW
        ):
            self.refresh()
            item = self.store.find(key)
            if level != INFO and item is not None:  # the app tells of an update
                self.announce([item])

    def mark_read(self) -> None:
        self.store.mark_read(self._now())
        self.refresh()

    def clear(self) -> None:
        self.store.clear()
        self.refresh()

    def restyle(self) -> None:
        self.panel.restyle()
        self.refresh()

    def context_changed(self) -> None:
        """Another context was chosen: what is kept is shown as it is; the next
        look comes with the timer, not at every switch."""
        self.refresh()

    def close(self) -> None:
        """The extension is unloaded: stop looking and take the panel away."""
        self.timer.stop()
        self.first_look.stop()
        self.panel.close()
        self.panel.deleteLater()
        self.bell.hide()
        self.bell.deleteLater()  # the top bar must not keep a bell nobody answers
        self.deleteLater()


def activate(ctx: Context) -> None:
    ui = ctx.ui
    if ui is None:  # the terminal has no top bar to put a bell in
        return
    settings = NotificationSettings(ctx.settings)
    store = NotificationStore(ctx.data_directory / "notifications.json")
    notifications = Notifications(ctx, settings, store)
    ctx.events.on(CONTEXT_CHANGED, lambda context: notifications.context_changed())
    ctx.events.on(THEME_CHANGED, notifications.restyle)
    ctx.events.on(NOTIFICATION, notifications.notice)
    ctx.events.on(SHUTDOWN, notifications.close)
    ctx.add_settings_section(
        TITLE,
        lambda: NotificationSettingsPanel(settings, notifications.apply_settings),
    )
    ctx.on_unload(notifications.close)
