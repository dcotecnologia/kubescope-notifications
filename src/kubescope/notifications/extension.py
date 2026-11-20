"""What the app calls to run the notifications: a bell in the top bar, a look
at the events of the cluster from time to time, and the panel."""

import time
from collections.abc import Callable

from kubescope.sdk import (
    CONTEXT_CHANGED,
    SHUTDOWN,
    THEME_CHANGED,
    Context,
)
from kubescope.sdk.models import ClusterEvent
from PySide6.QtCore import QCoreApplication, QObject, QPoint, QTimer

from kubescope.notifications.bell import Bell
from kubescope.notifications.panel import NotificationPanel
from kubescope.notifications.settings import NotificationSettings
from kubescope.notifications.settings_panel import NotificationSettingsPanel
from kubescope.notifications.store import NotificationStore

TITLE = "Notifications"
GAP = 6  # between the top bar and the panel


class Notifications(QObject):
    """Looks at the events of the context in use every few seconds, keeps the
    Warning ones and shows them."""

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
        self.bell = Bell(
            QCoreApplication.translate("NotificationsExtension", "Notifications")
        )
        self.bell.clicked.connect(self.toggle)
        self.panel = NotificationPanel(ui.central, ui.themed, self._panel_top)
        self.panel.on_closed = lambda: self.bell.setChecked(False)
        self.panel.on_mark_read = self.mark_read
        self.panel.on_clear = self.clear
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
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
        """Read the events of the context in use, off the UI thread. Nothing
        happens without a context or while the last read is not over; a read
        that fails (the context is not signed in) leaves what is kept as it
        is."""
        ui = self.ctx.ui
        context = self.ctx.current_context
        if ui is None or not context or self._busy:
            return
        self._busy = True
        ui.run_action(
            self.ctx.cluster.get_events,
            lambda events: self._arrived(context, events),
            context,
            ("Warning",),
            on_error=lambda _reason: self._failed(),
            quiet=True,
        )

    def _failed(self) -> None:
        self._busy = False

    def _arrived(self, context: str, events: list[ClusterEvent]) -> None:
        self._busy = False
        self.store.merge(context, events)
        self.refresh()

    def refresh(self) -> None:
        self.bell.set_unread(0 if self.panel.opened else self.store.unread())
        self.panel.show_items(self.store.items(), self._now())

    def toggle(self) -> None:
        if self.panel.opened:
            self.panel.close_panel()
            return
        self.panel.show_items(self.store.items(), self._now())
        self.panel.open_panel()
        self.bell.setChecked(True)
        self.bell.set_unread(0)
        self.store.mark_read(self._now())

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
        self.poll()

    def close(self) -> None:
        """The extension is unloaded: stop looking and take the panel away."""
        self.timer.stop()
        self.panel.close()
        self.panel.deleteLater()
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
    ctx.events.on(SHUTDOWN, notifications.close)
    ctx.add_settings_section(
        TITLE,
        lambda: NotificationSettingsPanel(settings, notifications.apply_settings),
    )
    ctx.on_unload(notifications.close)
    QTimer.singleShot(0, notifications.poll)  # look once the window is up
