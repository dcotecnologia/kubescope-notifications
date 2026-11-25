"""The preferences of the extension, kept in its own settings; what does not
fit is left out and the default is used."""

import re
from fnmatch import fnmatchcase
from typing import Any, Protocol

MINIMUM = 15  # seconds; a list of events every few seconds is too much load
MAXIMUM = 3600
DEFAULT = 60
WIDTH = 400  # the panel, in pixels
MIN_WIDTH = 300
MAX_WIDTH = 900
DEFAULT_START = "08:00"  # the window in which the system is told, when it is on
DEFAULT_END = "20:00"
MAX_IGNORED = 200
# the kinds of notification there are: the levels of the cluster and the app, the
# informative events, and what the app tells of something done
OLD_KINDS = ("error", "warning", "info", "normal")  # when `shown` was kept
KINDS = ("error", "warning", "info", "normal", "action", "pod", "task")
# what is off unless the person turns it on: only the errors of the cluster, the
# state of a Pod after an action and the updates of the app are on
HIDDEN = ("warning", "normal", "action", "task")
SILENT = ("warning", "normal", "action", "task")
_CLOCK = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")


def clock_of(value: object, default: str) -> str:
    """`HH:MM` when `value` is one, else `default`."""
    return value if isinstance(value, str) and _CLOCK.fullmatch(value) else default


def minutes_of(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def ignored_by(patterns: list[str], context: str, kind: str, name: str) -> bool:
    """Whether an object is on the ignore list.

    A pattern is `Kind/name`, or `context/Kind/name` to ignore it in one
    context only; `*` and `?` stand for any text, and case does not
    matter.
    """
    if not name:
        return False
    plain = f"{kind}/{name}".lower()
    full = f"{context}/{kind}/{name}".lower()
    return any(
        fnmatchcase(plain, pattern.lower()) or fnmatchcase(full, pattern.lower())
        for pattern in patterns
    )


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

    @property
    def window_enabled(self) -> bool:
        """Whether the system is told only inside the window; off unless the
        person turned it on."""
        return self._store.get("window_enabled", False) is True

    @window_enabled.setter
    def window_enabled(self, value: bool) -> None:
        self._store.set("window_enabled", bool(value))

    @property
    def window_start(self) -> str:
        return clock_of(self._store.get("window_start"), DEFAULT_START)

    @window_start.setter
    def window_start(self, value: str) -> None:
        self._store.set("window_start", clock_of(value, DEFAULT_START))

    @property
    def window_end(self) -> str:
        return clock_of(self._store.get("window_end"), DEFAULT_END)

    @window_end.setter
    def window_end(self, value: str) -> None:
        self._store.set("window_end", clock_of(value, DEFAULT_END))

    def in_window(self, minute_of_day: int) -> bool:
        """Whether the system may be told at this minute of the day.

        A window that ends before it starts runs over midnight.
        """
        if not self.window_enabled:
            return True
        start, end = minutes_of(self.window_start), minutes_of(self.window_end)
        if start == end:
            return True
        if start < end:
            return start <= minute_of_day < end
        return minute_of_day >= start or minute_of_day < end

    @property
    def ignored(self) -> list[str]:
        """The objects that are never kept nor told, one pattern each."""
        value = self._store.get("ignored", [])
        if not isinstance(value, list):
            return []
        kept = [line.strip() for line in value if isinstance(line, str)]
        return [line for line in kept if line][:MAX_IGNORED]

    @ignored.setter
    def ignored(self, value: list[str]) -> None:
        kept = [line.strip() for line in value if line.strip()]
        self._store.set("ignored", kept[:MAX_IGNORED])

    def _kinds(self, off: str, default: tuple[str, ...]) -> list[str]:
        """Every kind but the ones stored under `off`; a kind added by a later
        version is on, as the person has not been asked about it."""
        value = self._store.get(off, list(default))
        if not isinstance(value, list):
            value = list(default)
        return [kind for kind in KINDS if kind not in value]

    @property
    def shown(self) -> list[str]:
        """The kinds of notification that are listed and counted."""
        old = self._store.get("shown")
        if self._store.get("hidden") is None and isinstance(old, list):
            # kept by an earlier version as the ones that were on
            return [kind for kind in KINDS if kind in old or kind not in OLD_KINDS]
        return self._kinds("hidden", HIDDEN)

    @shown.setter
    def shown(self, value: list[str]) -> None:
        self._store.set("hidden", [kind for kind in KINDS if kind not in value])

    @property
    def told(self) -> list[str]:
        """The kinds the operating system is told about."""
        return self._kinds("silent", SILENT)

    @told.setter
    def told(self, value: list[str]) -> None:
        self._store.set("silent", [kind for kind in KINDS if kind not in value])
