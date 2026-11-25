"""The cards of the panel that slides in from the right with the notifications,
the newest first.

The panel itself, its cards and the bell are the ones of the app
(`ctx.ui.components`).
"""

from collections.abc import Callable
from typing import Any

from kubescope.sdk import translate

from kubescope.notifications.store import ERROR, INFO, NORMAL, Notification

SHOWN = 200  # the cards drawn; the store keeps more


def ago(seconds: float) -> str:
    """How long ago, the way the lists of the app say it."""
    seconds = max(int(seconds), 0)
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return translate("NotificationPanel", "{amount}{unit} ago").format(
                amount=seconds // size, unit=unit
            )
    return translate("NotificationPanel", "just now")


def card_of(
    components: Any,
    item: Notification,
    now: float,
    opened: Callable[[Notification], None],
    unread: bool,
    visit: Callable[[Notification], None],
) -> Any:
    """The card of one notification: what happened, where, how long ago, and
    the links to read it and to go to its context."""
    level = {
        ERROR: translate("NotificationPanel", "Error"),
        INFO: translate("NotificationPanel", "Info"),
        NORMAL: translate("NotificationPanel", "Info"),
    }.get(item.level, translate("NotificationPanel", "Warning"))
    about = " · ".join(
        part
        for part in (
            item.context,
            f"{item.kind}/{item.name}" if item.name else "",
            item.namespace,
        )
        if part
    )
    times = f"{item.count}× · " if item.count > 1 else ""
    actions: list[tuple[str, Callable[[], None]]] = []
    if unread:
        actions.append(
            (translate("NotificationPanel", "Mark as read"), lambda: opened(item))
        )
    if item.context:
        actions.append(
            (translate("NotificationPanel", "Go to context"), lambda: visit(item))
        )
    card = components.notice_card(
        item.reason or translate("NotificationPanel", "Event"),
        level,
        about,
        item.message,
        times + ago(now - item.first_seen),  # how long ago it began
        item.level,
        unread,
        translate("NotificationPanel", "Mark as read"),
        lambda: opened(item),
        actions,
    )
    card.item = item  # what the card shows
    return card
