"""The notifications kept between runs.

No Qt. An event of the cluster becomes a notification, an `error` when
its reason says that something failed and a `warning` otherwise. They
are kept by the context and the uid of the event, so one that repeats is
one notification whose count and time move on. What is kept is the text
of the events, which can name objects of the cluster: the file is
readable only by the person.
"""

import json
import os
import time
from collections.abc import Callable, Collection
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from kubescope.sdk.models import ClusterEvent

from kubescope.notifications.auth import is_auth_error

LIMIT = 500  # the notifications kept; the oldest go first
DISMISSED_LIMIT = 2000  # alerts remembered as cleared; the oldest are forgotten
# an alert that keeps happening is one notification; it is a new one only when
# it comes back after being quiet for this long (seconds)
QUIET = 3600.0
ERROR = "error"
WARNING = "warning"
INFO = "info"  # an update of the app
NORMAL = "normal"  # an informative event of the cluster
APP = "app"  # where a notice of the app came from, as the cluster is "cluster"
CLUSTER = "cluster"
LEVELS = (ERROR, WARNING, INFO)

# The reasons a Warning event gives when something failed, not only when it
# could happen: Kubernetes has no level above Warning.
ERROR_REASONS = frozenset(
    {
        "BackOff",
        "CrashLoopBackOff",
        "Failed",
        "FailedCreate",
        "FailedMount",
        "FailedScheduling",
        "FailedAttachVolume",
        "ErrImagePull",
        "ImagePullBackOff",
        "InspectFailed",
        "OOMKilling",
        "Evicted",
        "NodeNotReady",
        "SystemOOM",
    }
)


@dataclass(frozen=True)
class Notification:
    key: str  # the context and the uid of the event
    context: str
    level: str  # ERROR or WARNING
    reason: str
    namespace: str
    kind: str
    name: str
    message: str
    count: int
    first_seen: float
    last_seen: float
    source: str = CLUSTER
    read_at: float = 0.0  # when the person read this one, by clicking it
    category: str = ""  # of a notice of something done: action, pod or task
    noticed: float = 0.0  # when it was first told here, which says if it is new


def kind_of(item: Notification) -> str:
    """What kind of notification it is, the one the person turns on and off:

    the category of a notice of something done, else its level.
    """
    return item.category or item.level


def level_of(event: ClusterEvent) -> str:
    """`error` when the reason of the event says something failed."""
    if event.type == "Normal":
        return NORMAL
    return ERROR if event.reason in ERROR_REASONS else WARNING


def identity_of(
    context: str, namespace: str, kind: str, name: str, reason: str, fallback: str
) -> str:
    """What makes two events the same alert: the object, the reason and the
    context, so an event that Kubernetes creates again for the same thing is
    one alert whose count and time move on; `fallback` stands in when the event
    is not about a named object."""
    about = f"{namespace}/{kind}/{name}/{reason}" if name else fallback
    return f"{context}\n{about}"


def notification_of(context: str, event: ClusterEvent) -> Notification:
    return Notification(
        key=identity_of(
            context,
            event.namespace,
            event.kind,
            event.name,
            event.reason,
            event.uid or event.message,
        ),
        context=context,
        level=level_of(event),
        reason=event.reason,
        namespace=event.namespace,
        kind=event.kind,
        name=event.name,
        message=event.message,
        count=event.count,
        first_seen=event.first_seen,
        last_seen=event.last_seen,
    )


class NotificationStore:
    """The notifications of every context, in a JSON file, and when the person
    last looked at them."""

    def __init__(self, path: Path, limit: int = LIMIT, quiet: float = QUIET) -> None:
        self.path = path
        self.limit = limit
        self.quiet = quiet
        self._items: dict[str, Notification] = {}
        # the alerts the person cleared, and the time of the last one cleared:
        # they come back only when they happen again after that
        self._dismissed: dict[str, float] = {}
        self.read_until = 0.0
        self.load()

    def load(self) -> None:
        """Read the file; a missing or damaged one is an empty store."""
        self._items = {}
        self._dismissed = {}
        self.read_until = 0.0
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            self.read_until = float(document.get("read_until", 0.0))
            for key, moment in dict(document.get("dismissed", {})).items():
                self._dismissed[str(key)] = float(moment)
            for raw in document.get("items", []):
                item = Notification(**raw)
                if item.source == CLUSTER and item.name:  # kept by an older rule
                    item = replace(
                        item,
                        key=identity_of(
                            item.context,
                            item.namespace,
                            item.kind,
                            item.name,
                            item.reason,
                            item.key,
                        ),
                    )
                if item.key.startswith(f"{APP}\nunreadable:") and is_auth_error(
                    item.message
                ):
                    continue  # a sign-in an older version listed: the banner says it
                before = self._items.get(item.key)
                if before is None or item.last_seen >= before.last_seen:
                    self._items[item.key] = item
        except OSError, ValueError, TypeError, AttributeError:
            self._items = {}
            self._dismissed = {}
            self.read_until = 0.0

    def save(self) -> None:
        """Write the file, readable only by the person."""
        document = {
            "read_until": self.read_until,
            "items": [asdict(item) for item in self._items.values()],
            "dismissed": self._dismissed,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(document, handle, ensure_ascii=False)
        temporary.replace(self.path)

    def add_notice(
        self,
        level: str,
        title: str,
        message: str,
        key: str,
        repeat: bool,
        moment: float,
        context: str = "",
        window: float = 0.0,
        category: str = "",
    ) -> bool:
        """Add a notice of the app itself: an error, a warning or an update.

        The same `key` again is the same notice, which counts once more
        when `repeat` is set and is left alone otherwise; `context`
        names the one it is about, when there is one. Inside `window`
        seconds of the last time, a repeat only counts: it is not new
        and does not become unread again. True when it is new, or news
        again.
        """
        identity = f"{APP}\n{key}"
        cleared = self._dismissed.get(identity)
        if cleared is not None:
            # cleared by the person: gone for good unless it is the kind that
            # repeats, and then only once the window since it was cleared is over
            if not repeat or moment - cleared < window:
                return False
            del self._dismissed[identity]
        before = self._items.get(identity)
        if before is not None and not repeat:
            return False
        if before is not None and moment - before.last_seen < window:
            self._items[identity] = replace(before, count=before.count + 1)
            self.save()
            return False
        self._items[identity] = Notification(
            key=identity,
            context=context,
            level=level if level in LEVELS else WARNING,
            reason=title,
            namespace="",
            kind="",
            name="",
            message=message,
            count=before.count + 1 if before else 1,
            first_seen=before.first_seen if before else moment,
            last_seen=moment,
            source=APP,
            category=category,
            noticed=moment,
        )
        self._trim()
        self.save()
        return True

    def discard_where(self, test: Callable[[Notification], bool]) -> int:
        """Take away the notices of the app that the test says yes to."""
        gone = [
            key
            for key, item in self._items.items()
            if item.source == APP and test(item)
        ]
        for key in gone:
            del self._items[key]
        if gone:
            self.save()
        return len(gone)

    def find(self, key: str) -> Notification | None:
        """The notice of the app added with that key."""
        return self._items.get(f"{APP}\n{key}")

    def discard(self, key: str) -> bool:
        """Take a notice of the app away, the one added with that key; True
        when there was one."""
        identity = f"{APP}\n{key}"
        forgotten = self._dismissed.pop(identity, None) is not None
        if self._items.pop(identity, None) is None:
            if forgotten:
                self.save()
            return False
        self.save()
        return True

    def _trim(self) -> None:
        """Keep the newest `limit`; the oldest go first."""
        if len(self._items) > self.limit:
            newest = sorted(self._items.values(), key=lambda one: one.last_seen)[
                -self.limit :
            ]
            self._items = {one.key: one for one in newest}

    def merge_changes(
        self,
        context: str,
        events: list[ClusterEvent],
        moment: float | None = None,
    ) -> list[Notification]:
        """Add what the events of `context` bring; the notifications that are
        new, or that came back after being quiet for a while.

        An alert that keeps happening (an autoscaler that fails every
        few seconds) is one notification: its count and last time move
        on, and it is neither unread again nor told again. One the
        person cleared stays away while it goes on.
        """
        changed: list[Notification] = []
        moment = time.time() if moment is None else moment
        for event in events:
            item = notification_of(context, event)
            cleared = self._dismissed.get(item.key)
            if cleared is not None:
                if item.last_seen - cleared < self.quiet:
                    # the one the person cleared, still going on: it stays away
                    # until it has been quiet for a while
                    self._dismissed[item.key] = max(cleared, item.last_seen)
                    continue
                del self._dismissed[item.key]  # it happened again
            before = self._items.get(item.key)
            if before is None:
                item = replace(item, noticed=moment)
                changed.append(item)
                self._items[item.key] = item
            elif item.last_seen - before.last_seen >= self.quiet:
                # back after a quiet time: a new occurrence, which began now
                again = replace(item, first_seen=item.last_seen, noticed=moment)
                changed.append(again)
                self._items[item.key] = again
            elif item.last_seen > before.last_seen:  # still going on
                self._items[item.key] = replace(
                    before,
                    count=item.count,
                    last_seen=item.last_seen,
                    message=item.message,
                )
        self._trim()
        self.save()
        return changed

    def prune(
        self,
        context: str,
        events: list[ClusterEvent],
        levels: Collection[str] = (ERROR, WARNING, NORMAL),
    ) -> int:
        """Take away the notifications of `context` whose event is not in the
        cluster any more, given every event it has now of the `levels` that
        were read; how many went."""
        present = {notification_of(context, event).key for event in events}
        gone = [
            key
            for key, one in self._items.items()
            if one.source == CLUSTER
            and one.context == context
            and one.level in levels
            and key not in present
        ]
        for key in gone:
            del self._items[key]
        if gone:
            self.save()
        return len(gone)

    def merge(
        self,
        context: str,
        events: list[ClusterEvent],
        moment: float | None = None,
    ) -> int:
        """Add what the events of `context` bring; the number of notifications
        that are new or that happened again since the person looked."""
        changed = self.merge_changes(context, events, moment)
        return sum(1 for item in changed if item.noticed > self.read_until)

    def items(self) -> list[Notification]:
        """Every notification, the one that began last first."""
        return sorted(
            self._items.values(), key=lambda one: one.first_seen, reverse=True
        )

    def is_unread(self, item: Notification) -> bool:
        """Whether it came after it was read: going on is not news.

        What counts is when it was first told here, not when the event
        began, so a new notification of an old event is new.
        """
        return (item.noticed or item.first_seen) > max(self.read_until, item.read_at)

    def mark_item_read(self, key: str, moment: float) -> None:
        """The person read one notification."""
        item = self._items.get(key)
        if item is not None:
            self._items[key] = replace(item, read_at=moment)
            self.save()

    def unread(self) -> int:
        return sum(1 for item in self._items.values() if self.is_unread(item))

    def mark_read(self, moment: float) -> None:
        """The person looked at everything up to `moment`."""
        self.read_until = moment
        self.save()

    def clear(self) -> None:
        """Forget every notification.

        What was cleared does not come back with
        the next look at the cluster: only when it happens again.
        """
        for key, item in self._items.items():
            self._dismissed[key] = item.last_seen
        newest = sorted(self._dismissed.items(), key=lambda pair: pair[1])
        self._dismissed = dict(newest[-DISMISSED_LIMIT:])
        self._items = {}
        self.save()
