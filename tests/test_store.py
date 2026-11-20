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
