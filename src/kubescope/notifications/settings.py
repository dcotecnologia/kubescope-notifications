"""The preferences of the extension, kept in its own settings; what does not
fit is left out and the default is used."""

from typing import Any, Protocol

MINIMUM = 15  # seconds; a list of events every few seconds is too much load
MAXIMUM = 3600
DEFAULT = 60


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
