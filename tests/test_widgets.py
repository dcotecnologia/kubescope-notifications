from kubescope.extensions import testing
from kubescope.extensions.components import UiComponents

from kubescope.notifications.panel import SHOWN, ago, card_of
from kubescope.notifications.store import NotificationStore, notification_of


def test_the_time_is_said_the_way_the_lists_say_it() -> None:
    assert ago(5) == "just now"
    assert ago(-5) == "just now"
    assert ago(120) == "2m ago"
    assert ago(7200) == "2h ago"
    assert ago(3 * 86400) == "3d ago"


def make(item, now=1180.0, unread=True, opened=None, visit=None):
    return card_of(
        UiComponents(),
        item,
        now,
        opened or (lambda _item: None),
        unread,
        visit or (lambda _item: None),
    )


def test_the_cards_say_what_happened_and_how_long_ago(make_event) -> None:
    mine = notification_of("prod", make_event(count=4, last_seen=1000.0))
    bare = notification_of(
        "prod", make_event("b", reason="", name="", namespace="", last_seen=1000.0)
    )

    shown = testing.texts(make(mine)) + testing.texts(make(bare))

    assert "BackOff" in shown and "Event" in shown
    assert "Back-off restarting failed container" in shown
    assert "prod · Pod/api-u1 · ns" in shown  # the context is named
    assert "4× · 3m ago" in shown
    assert "1× · 3m ago" not in shown and "3m ago" in shown


def test_only_the_newest_cards_are_drawn() -> None:
    assert SHOWN == 200


def test_a_notice_of_the_app_shows_its_title_and_how_serious_it_is(tmp_path) -> None:
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

    shown = [
        text for item in store.items() for text in testing.texts(make(item, 160.0))
    ]

    assert "KubeScope update available" in shown and "Info" in shown
    assert "Boom" in shown and "Error" in shown
    assert "Version 9 is available" in shown


def test_a_card_without_a_context_is_clicked_to_be_read(tmp_path) -> None:
    heard: list[str] = []
    store = NotificationStore(tmp_path / "n.json")
    store.add_notice("error", "Boom", "it broke", "e", False, 100.0)
    (item,) = store.items()

    card = make(item, 160.0, opened=lambda one: heard.append(one.reason))
    assert card.toolTip() == "Mark as read" and card.item is item
    assert [one.text() for one in card.buttons] == ["Mark as read"]

    testing.click(card, 5, 5, "release")
    assert heard == ["Boom"]


def test_a_read_card_has_only_the_way_to_its_context(make_event) -> None:
    item = notification_of("prod", make_event("a", last_seen=100.0))
    visited: list[str] = []
    card = make(item, 160.0, unread=False, visit=lambda one: visited.append(one.name))
    assert [one.text() for one in card.buttons] == ["Go to context"]
    card.buttons[0].click()
    assert visited == ["api-a"]
