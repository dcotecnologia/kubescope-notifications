import json
import os
import stat

from kubescope.notifications.settings import (
    DEFAULT,
    MAXIMUM,
    MINIMUM,
    NotificationSettings,
)
from kubescope.notifications.store import (
    ERROR,
    WARNING,
    NotificationStore,
    level_of,
    notification_of,
)


def test_a_failure_reason_is_an_error_and_any_other_is_a_warning(make_event) -> None:
    assert level_of(make_event(reason="FailedScheduling")) == ERROR
    assert level_of(make_event(reason="Unhealthy")) == WARNING


def test_an_event_without_a_uid_is_told_by_what_it_is_about(make_event) -> None:
    one = notification_of("prod", make_event(uid=""))
    again = notification_of("prod", make_event(uid="", last_seen=2000.0))
    other = notification_of("prod", make_event(uid="", name="web"))

    assert one.key == again.key != other.key
    assert (
        notification_of("dev", make_event()).key
        != notification_of("prod", make_event()).key
    )


def test_a_repeated_event_is_one_notification_that_moves_on(
    tmp_path, make_event
) -> None:
    store = NotificationStore(tmp_path / "n.json")

    assert store.merge("prod", [make_event(last_seen=100.0)]) == 1
    assert store.merge("prod", [make_event(last_seen=100.0)]) == 0  # nothing new
    assert store.merge("prod", [make_event(last_seen=200.0, count=3)]) == 1

    (only,) = store.items()
    assert (only.count, only.last_seen) == (3, 200.0)


def test_the_newest_come_first_and_the_oldest_go_when_there_are_too_many(
    tmp_path, make_event
) -> None:
    store = NotificationStore(tmp_path / "n.json", limit=2)

    store.merge(
        "prod",
        [make_event("a", last_seen=1.0), make_event("b", last_seen=3.0)],
    )
    store.merge("prod", [make_event("c", last_seen=2.0)])

    assert [item.key.split("\n")[1] for item in store.items()] == ["b", "c"]


def test_what_was_read_is_not_unread_again(tmp_path, make_event) -> None:
    store = NotificationStore(tmp_path / "n.json")
    store.merge("prod", [make_event("a", last_seen=10.0)])
    assert store.unread() == 1

    store.mark_read(50.0)
    assert store.unread() == 0
    assert store.merge("prod", [make_event("a", last_seen=20.0)]) == 0  # seen before
    assert store.merge("prod", [make_event("a", last_seen=60.0)]) == 1


def test_it_is_kept_between_runs_and_only_the_person_reads_the_file(
    tmp_path, make_event
) -> None:
    path = tmp_path / "deep" / "n.json"
    store = NotificationStore(path)
    store.merge("prod", [make_event()])
    store.mark_read(5.0)

    again = NotificationStore(path)

    assert [item.reason for item in again.items()] == ["BackOff"]
    assert again.read_until == 5.0
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_a_damaged_file_is_an_empty_store(tmp_path, make_event) -> None:
    for content in ("not json", '{"items": [{"nope": 1}]}', "[]"):
        path = tmp_path / "n.json"
        path.write_text(content, encoding="utf-8")
        store = NotificationStore(path)
        assert store.items() == [] and store.read_until == 0.0
    assert json.loads('{"a": 1}')  # the file is plain JSON, nothing else


def test_clearing_empties_it_for_good(tmp_path, make_event) -> None:
    store = NotificationStore(tmp_path / "n.json")
    store.merge("prod", [make_event()])

    store.clear()

    assert NotificationStore(tmp_path / "n.json").items() == []


def test_the_interval_is_kept_between_what_is_reasonable() -> None:
    saved: dict = {}

    class Store:
        def get(self, key, default=None):
            return saved.get(key, default)

        def set(self, key, value):
            saved[key] = value

    settings = NotificationSettings(Store())
    assert settings.interval == DEFAULT
    settings.interval = 1
    assert settings.interval == MINIMUM
    settings.interval = 10**6
    assert settings.interval == MAXIMUM
    saved["interval"] = "often"
    assert settings.interval == DEFAULT
    saved["interval"] = True
    assert settings.interval == DEFAULT


def test_a_notice_of_the_app_is_one_notification_that_counts_when_it_repeats(
    tmp_path,
) -> None:
    store = NotificationStore(tmp_path / "n.json")

    assert store.add_notice("error", "Boom", "it broke", "e1", True, 10.0)
    assert store.add_notice("error", "Boom", "it broke", "e1", True, 20.0)

    (only,) = store.items()
    assert (only.source, only.level, only.reason, only.message) == (
        "app",
        "error",
        "Boom",
        "it broke",
    )
    assert (only.count, only.first_seen, only.last_seen) == (2, 10.0, 20.0)


def test_an_update_is_told_once_and_a_second_time_changes_nothing(tmp_path) -> None:
    store = NotificationStore(tmp_path / "n.json")

    assert store.add_notice("info", "Update", "9.9.9", "update:9.9.9", False, 5.0)
    assert not store.add_notice("info", "Update", "9.9.9", "update:9.9.9", False, 50.0)

    (only,) = store.items()
    assert (only.level, only.count, only.last_seen) == ("info", 1, 5.0)


def test_an_unknown_level_is_a_warning_and_the_notices_are_trimmed(tmp_path) -> None:
    store = NotificationStore(tmp_path / "n.json", limit=2)

    store.add_notice("loud", "A", "a", "a", False, 1.0)
    store.add_notice("error", "B", "b", "b", False, 2.0)
    store.add_notice("error", "C", "c", "c", False, 3.0)

    assert [item.reason for item in store.items()] == ["C", "B"]
    assert store.items()[-1].level == "error"
    store.add_notice("loud", "D", "d", "d", False, 4.0)
    assert store.items()[0].level == "warning"


def test_a_file_from_before_the_notices_of_the_app_still_loads(
    tmp_path, make_event
) -> None:
    path = tmp_path / "n.json"
    old = NotificationStore(path)
    old.merge("prod", [make_event()])
    document = json.loads(path.read_text(encoding="utf-8"))
    for item in document["items"]:
        del item["source"]  # what an older version wrote
    path.write_text(json.dumps(document), encoding="utf-8")

    (item,) = NotificationStore(path).items()

    assert item.source == "cluster"


def test_the_width_of_the_panel_is_kept_between_what_is_usable() -> None:
    saved: dict = {}

    class Store:
        def get(self, key, default=None):
            return saved.get(key, default)

        def set(self, key, value):
            saved[key] = value

    settings = NotificationSettings(Store())
    assert settings.panel_width == 400
    settings.panel_width = 10
    assert settings.panel_width == 300
    settings.panel_width = 10**6
    assert settings.panel_width == 900
    settings.panel_width = 520
    assert saved["panel_width"] == 520
    saved["panel_width"] = "wide"
    assert settings.panel_width == 400
    saved["panel_width"] = True
    assert settings.panel_width == 400


def test_the_changes_are_the_notifications_that_are_new_or_happened_again(
    tmp_path, make_event
) -> None:
    store = NotificationStore(tmp_path / "n.json")

    first = store.merge_changes("prod", [make_event("a", last_seen=5.0)])
    again = store.merge_changes("prod", [make_event("a", last_seen=5.0)])
    later = store.merge_changes("prod", [make_event("a", last_seen=9.0)])

    assert [len(first), len(again), len(later)] == [1, 0, 1]
    assert later[0].last_seen == 9.0
