"""The preferences of the extension, kept in its own settings; what does not
fit is left out and the default is used."""

from typing import Any, Protocol

MINIMUM = 15  # seconds; a list of events every few seconds is too much load
MAXIMUM = 3600
DEFAULT = 60
WIDTH = 400  # the panel, in pixels
MIN_WIDTH = 300
MAX_WIDTH = 900


class Store(Protocol):
    """Where the preferences are kept (`ctx.settings`)."""

    def get(self, key: str, default: Any = None) -> Any: ...

    def set(self, key: str, value: Any) -> None: ...


class NotificationSettings:
    def __init__(self, store: Store) -> None:
        self._store = store

    @property
    def interval(self) -> int:
        """Seconds between two looks at the events of the cluster."""
        value = self._store.get("interval", DEFAULT)
        if isinstance(value, bool) or not isinstance(value, int):
            return DEFAULT
        return min(max(value, MINIMUM), MAXIMUM)

    @interval.setter
    def interval(self, value: int) -> None:
        self._store.set("interval", min(max(int(value), MINIMUM), MAXIMUM))

    @property
    def panel_width(self) -> int:
        """The width of the panel, as the person dragged it."""
        value = self._store.get("panel_width", WIDTH)
        if isinstance(value, bool) or not isinstance(value, int):
            return WIDTH
        return min(max(value, MIN_WIDTH), MAX_WIDTH)

    @panel_width.setter
    def panel_width(self, value: int) -> None:
        self._store.set("panel_width", min(max(int(value), MIN_WIDTH), MAX_WIDTH))

    @property
    def system_notifications(self) -> bool:
        """Whether a new notification is also told by the operating system; on
        unless the person turned it off."""
        return self._store.get("system_notifications", True) is not False

    @system_notifications.setter
    def system_notifications(self, value: bool) -> None:
        self._store.set("system_notifications", bool(value))
