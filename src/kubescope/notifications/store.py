"""The notifications kept between runs.

No Qt. An event of the cluster becomes a notification, an `error` when its
reason says that something failed and a `warning` otherwise. They are kept by
the context and the uid of the event, so one that repeats is one notification
whose count and time move on. What is kept is the text of the events, which
can name objects of the cluster: the file is readable only by the person.
"""

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from kubescope.sdk.models import ClusterEvent

LIMIT = 500  # the notifications kept; the oldest go first
ERROR = "error"
WARNING = "warning"
INFO = "info"  # an update of the app
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


def level_of(event: ClusterEvent) -> str:
    """`error` when the reason of the event says something failed."""
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

    def __init__(self, path: Path, limit: int = LIMIT) -> None:
        self.path = path
        self.limit = limit
        self._items: dict[str, Notification] = {}
        self.read_until = 0.0
        self.load()

    def load(self) -> None:
        """Read the file; a missing or damaged one is an empty store."""
        self._items = {}
        self.read_until = 0.0
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
            self.read_until = float(document.get("read_until", 0.0))
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
                before = self._items.get(item.key)
                if before is None or item.last_seen >= before.last_seen:
                    self._items[item.key] = item
        except OSError, ValueError, TypeError, AttributeError:
            self._items = {}
            self.read_until = 0.0

    def save(self) -> None:
        """Write the file, readable only by the person."""
        document = {
            "read_until": self.read_until,
            "items": [asdict(item) for item in self._items.values()],
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
    ) -> bool:
        """Add a notice of the app itself: an error, a warning or an update.

        The same `key` again is the same notice, which counts once more when
        `repeat` is set and is left alone otherwise; `context` names the one
        it is about, when there is one. True when something changed.
        """
        identity = f"{APP}\n{key}"
        before = self._items.get(identity)
        if before is not None and not repeat:
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
        )
        self._trim()
        self.save()
        return True

    def find(self, key: str) -> Notification | None:
        """The notice of the app added with that key."""
        return self._items.get(f"{APP}\n{key}")

    def discard(self, key: str) -> bool:
        """Take a notice of the app away, the one added with that key; True
        when there was one."""
        if self._items.pop(f"{APP}\n{key}", None) is None:
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
        self, context: str, events: list[ClusterEvent]
    ) -> list[Notification]:
        """Add what the events of `context` bring; the notifications that are
        new or that happened again, whether or not the person looked."""
        changed: list[Notification] = []
        for event in events:
            item = notification_of(context, event)
            before = self._items.get(item.key)
            if before is None or item.last_seen > before.last_seen:
                changed.append(item)
                self._items[item.key] = item
        self._trim()
        self.save()
        return changed

    def merge(self, context: str, events: list[ClusterEvent]) -> int:
        """Add what the events of `context` bring; the number of notifications
        that are new or that happened again since the person looked."""
        changed = self.merge_changes(context, events)
        return sum(1 for item in changed if item.last_seen > self.read_until)

    def items(self) -> list[Notification]:
        """Every notification, the newest first."""
        return sorted(self._items.values(), key=lambda one: one.last_seen, reverse=True)

    def unread(self) -> int:
        return sum(
            1 for item in self._items.values() if item.last_seen > self.read_until
        )

    def mark_read(self, moment: float) -> None:
        """The person looked at everything up to `moment`."""
        self.read_until = moment
        self.save()

    def clear(self) -> None:
        self._items = {}
        self.save()
