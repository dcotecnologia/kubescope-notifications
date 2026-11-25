from kubescope.extensions import testing
from kubescope.extensions.components import UiComponents

import kubescope.notifications as package
from kubescope.notifications import extension
from kubescope.notifications.extension import Notifications, activate
from kubescope.notifications.settings import NotificationSettings
from kubescope.notifications.settings_panel import NotificationSettingsPanel
from kubescope.notifications.store import NotificationStore


def build(ctx, now=2000.0) -> Notifications:
    # the tests of what is told start from everything on, but the informative
    # events and the updates of the app
    ctx.settings.setdefault("hidden", ["normal"])
    ctx.settings.setdefault("silent", ["info", "normal"])
    settings = NotificationSettings(ctx.settings)
    store = NotificationStore(ctx.data_directory / "n.json")
    return Notifications(ctx, settings, store, now=lambda: now)  # type: ignore[arg-type]


def test_the_bell_goes_to_the_top_bar_and_every_context_is_read(
    ctx, make_event
) -> None:
    ctx.cluster.contexts = ["prod", "staging"]
    ctx.cluster.events = [make_event("a"), make_event("b", reason="Unhealthy")]
    notifications = build(ctx)
    assert ctx.ui.buttons == [("kubescope.notifications", notifications.bell)]

    notifications.poll()

    assert sorted(ctx.cluster.asked) == [
        ("prod", ("Warning",)),
        ("staging", ("Warning",)),
    ]
    assert notifications.bell.unread == 4  # the same events in each context
    assert {item.context for item in notifications.store.items()} == {
        "prod",
        "staging",
    }


def test_nothing_is_read_while_the_last_read_is_not_over(ctx) -> None:
    notifications = build(ctx)
    notifications._busy = True

    notifications.poll()

    assert ctx.cluster.asked == []


def test_a_context_that_fails_is_left_alone_for_a_while_and_the_others_go_on(
    ctx, make_event
) -> None:
    ctx.cluster.contexts = ["prod", "dead"]
    ctx.cluster.events = [make_event()]
    ctx.cluster.failures["dead"] = RuntimeError("not signed in")
    notifications = build(ctx)

    notifications.poll()  # dead fails
    notifications.poll()  # and is skipped this round
    notifications.poll()  # asked again

    asked = [name for name, _types in ctx.cluster.asked]
    assert asked.count("prod") == 3 and asked.count("dead") == 2
    assert len(notifications.store.items()) == 2 and not notifications._busy
    ctx.cluster.failures.clear()
    for _ in range(3):
        notifications.poll()
    assert {item.context for item in notifications.store.items()} == {"prod", "dead"}


def test_a_read_that_cannot_even_list_the_contexts_changes_nothing(
    ctx, make_event, monkeypatch
) -> None:
    ctx.cluster.events = [make_event()]
    notifications = build(ctx)
    notifications.poll()

    def broken():
        raise RuntimeError("no kubeconfig")

    monkeypatch.setattr(ctx.cluster, "list_contexts", broken)
    notifications.poll()

    assert len(notifications.store.items()) == 1 and not notifications._busy


def test_the_bell_opens_the_panel_and_what_is_in_it_stays_unread_until_clicked(
    ctx, make_event
) -> None:
    ctx.cluster.events = [make_event()]
    notifications = build(ctx)
    notifications.poll()
    assert notifications.bell.unread == 1

    notifications.bell.click()

    assert notifications.panel.opened and notifications.bell.isChecked()
    assert notifications.bell.unread == 1  # opening it reads nothing
    (card,) = cards_of(notifications)
    assert card.unread

    click_on(card)  # clicking one only reads it: the panel and the context stay
    assert notifications.bell.unread == 0 and notifications.store.unread() == 0
    assert notifications.panel.opened and ctx.invoked == []
    (card,) = cards_of(notifications)
    assert not card.unread

    notifications.bell.click()  # again: it closes
    assert not notifications.panel.opened and not notifications.bell.isChecked()


def test_an_event_that_comes_while_the_panel_is_open_counts_as_unread(
    ctx, make_event
) -> None:
    notifications = build(ctx, now=500.0)
    notifications.toggle()
    ctx.cluster.events = [make_event(last_seen=900.0)]

    notifications.poll()

    assert notifications.bell.unread == 1 and len(notifications.store.items()) == 1


def test_an_alert_that_goes_on_stays_read_and_one_that_comes_back_is_unread_again(
    ctx, make_event
) -> None:
    clock = [2000.0]
    settings = NotificationSettings(ctx.settings)
    store = NotificationStore(ctx.data_directory / "n.json")
    notifications = Notifications(ctx, settings, store, now=lambda: clock[0])  # type: ignore[arg-type]
    ctx.cluster.events = [make_event("a", name="api", last_seen=1990.0)]
    notifications.poll()
    notifications.open_context(notifications.store.items()[0])
    assert notifications.store.unread() == 0

    clock[0] = 3000.0  # it goes on: a count that moves is not news
    ctx.cluster.events = [make_event("b", name="api", last_seen=2900.0, count=3)]
    notifications.poll()
    assert notifications.store.unread() == 0
    assert notifications.store.items()[0].count == 3

    clock[0] = 9000.0  # it comes back after more than an hour of quiet
    ctx.cluster.events = [make_event("c", name="api", last_seen=8900.0, count=4)]
    notifications.poll()

    assert notifications.store.unread() == 1


def test_mark_all_as_read_and_clear(ctx, make_event) -> None:
    ctx.cluster.events = [make_event()]
    notifications = build(ctx)
    notifications.poll()

    notifications.mark_read()
    assert notifications.bell.unread == 0 and len(notifications.store.items()) == 1
    notifications.clear()
    assert notifications.store.items() == []


def test_the_interval_of_the_settings_sets_the_timer(ctx) -> None:
    ctx.settings["interval"] = 30
    notifications = build(ctx)
    assert notifications.timer.interval() == 30000

    panel = NotificationSettingsPanel(
        UiComponents(), notifications.settings, notifications.apply_settings
    )
    panel.load()
    assert panel.interval.value() == 30
    assert panel.system.isChecked()  # on unless turned off
    panel.interval.setValue(120)
    panel.system.setChecked(False)
    assert panel.save() is True
    assert notifications.timer.interval() == 120000
    assert ctx.settings["system_notifications"] is False
    panel.load()
    assert not panel.system.isChecked()


def test_the_seconds_are_any_whole_number_within_what_is_allowed(ctx) -> None:
    ctx.settings["interval"] = 45
    notifications = build(ctx)
    panel = NotificationSettingsPanel(
        UiComponents(), notifications.settings, notifications.apply_settings
    )

    panel.load()
    assert panel.interval.value() == 45  # not one of a fixed list
    assert panel.interval.suffix() == " seconds"

    panel.interval.lineEdit().setText("97")  # typed, not yet confirmed
    panel.save()
    assert ctx.settings["interval"] == 97
    assert notifications.timer.interval() == 97000

    panel.interval.setValue(1)  # too often is brought to the least
    assert panel.interval.value() == 15
    panel.interval.setValue(99999)
    assert panel.interval.value() == 3600
    panel.interval.lineEdit().setText("abc")  # not a number: the last one stays
    panel.save()
    assert ctx.settings["interval"] == 3600


def test_activating_it_wires_the_events_the_settings_and_the_cleanup(
    ctx, make_event
) -> None:
    ctx.cluster.events = [make_event()]

    activate(ctx)  # type: ignore[arg-type]

    assert [title for title, _ in ctx.sections] == ["Notifications"]
    ctx.events.fire("context_changed", context="prod")
    assert ctx.cluster.asked == []  # switching does not read every cluster
    ctx.events.fire("theme_changed")
    (_title, factory) = ctx.sections[0]
    assert factory() is not None  # the widget of the section
    ctx.events.fire("shutdown")
    for cleanup in ctx.cleanups:
        cleanup()


def test_the_terminal_has_no_top_bar_so_it_does_nothing(ctx) -> None:
    ctx.ui = None

    activate(ctx)  # type: ignore[arg-type]

    assert ctx.sections == [] and ctx.cleanups == []


def test_the_entry_point_of_the_manifest_runs_it(ctx, monkeypatch) -> None:
    called: list = []
    monkeypatch.setattr(extension, "activate", called.append)

    package.activate(ctx)  # type: ignore[arg-type]

    assert called == [ctx]


def test_closing_it_stops_the_timer(ctx) -> None:
    notifications = build(ctx)

    notifications.close()

    assert not notifications.timer.isActive()


def test_the_app_tells_an_error_and_an_update_and_the_bell_counts_them(ctx) -> None:
    activate(ctx)  # type: ignore[arg-type]

    ctx.events.fire(
        "notification",
        level="error",
        title="Boom",
        message="it broke",
        key="e",
        repeat=True,
    )
    ctx.events.fire(
        "notification",
        level="info",
        title="Update",
        message="9.9.9",
        key="u",
        repeat=False,
    )
    ctx.events.fire(
        "notification",
        level="info",
        title="Update",
        message="9.9.9",
        key="u",
        repeat=False,
    )  # the same update again: nothing changes

    bell = ctx.ui.buttons[0][1]
    assert bell.unread == 2


def test_notice_is_for_what_the_app_tells(ctx) -> None:
    notifications = build(ctx)

    notifications.notice("warning", "Careful", "m", "k")
    notifications.notice("warning", "Careful", "m", "k")  # not repeated by default

    assert [item.count for item in notifications.store.items()] == [1]


def test_the_width_the_person_dragged_is_kept_and_used_next_time(ctx) -> None:
    notifications = build(ctx)

    notifications.panel.on_resized(520)
    assert ctx.settings["panel_width"] == 520

    again = build(ctx)
    again.panel.open_panel()
    assert again.panel.width() == 520


def test_new_events_are_told_to_the_system_in_one_notice_that_opens_the_panel(
    ctx, make_event
) -> None:
    ctx.cluster.events = [make_event("new", last_seen=2000.0)]
    notifications = build(ctx)

    notifications.poll()

    ((title, message, click),) = ctx.ui.system
    assert title == "BackOff"
    assert "Pod/api" in message and "prod" in message
    click()  # the one notice goes to the context it is about
    assert [name for name, _ in ctx.invoked] == ["switch_context"]
    assert ctx.invoked[0][1]["context"] == "prod"


def test_several_new_events_make_one_notice_with_the_first_ones_named(
    ctx, make_event
) -> None:
    ctx.cluster.events = [
        make_event(str(n), last_seen=2000.0 + n, reason=f"Reason{n}") for n in range(5)
    ]
    notifications = build(ctx)

    notifications.poll()

    ((title, message, _click),) = ctx.ui.system
    assert title == "5 new notifications"
    assert (
        message.splitlines()[0] == "Reason4 · prod" and len(message.splitlines()) == 3
    )


def test_what_happened_before_the_start_or_is_not_new_is_not_told(
    ctx, make_event
) -> None:
    ctx.cluster.events = [make_event(last_seen=100.0)]  # long before the start
    notifications = build(ctx)

    notifications.poll()
    notifications.poll()

    assert ctx.ui.system == [] and notifications.bell.unread == 1


def test_the_system_is_not_told_when_it_is_turned_off(ctx, make_event) -> None:
    ctx.cluster.events = [make_event("a", last_seen=2000.0)]
    notifications = build(ctx)
    ctx.settings["system_notifications"] = False

    notifications.poll()

    assert ctx.ui.system == []


def test_the_system_is_told_even_with_the_window_in_front(
    ctx, make_event, monkeypatch
) -> None:
    ctx.cluster.events = [make_event("a", last_seen=2000.0)]
    notifications = build(ctx)
    monkeypatch.setattr(ctx.ui.window, "isActiveWindow", lambda: True)

    notifications.poll()

    assert len(ctx.ui.system) == 1


def test_an_error_of_the_app_is_told_to_the_system_but_an_update_is_not(ctx) -> None:
    notifications = build(ctx)

    notifications.notice("error", "Boom", "it broke", "e", True)
    notifications.notice("info", "Update", "9.9.9", "u", False)
    notifications.notice("error", "Boom", "it broke", "e", False)  # nothing new

    ((title, message, _click),) = ctx.ui.system
    assert (title, message) == ("Boom", "it broke")


def test_a_long_message_is_cut_for_the_system(ctx, make_event) -> None:
    ctx.cluster.events = [make_event(last_seen=2000.0, message="x" * 1000)]
    notifications = build(ctx)

    notifications.poll()

    assert len(ctx.ui.system[0][1]) == 220


def test_a_notice_about_several_things_opens_the_panel(ctx, make_event) -> None:
    ctx.cluster.events = [
        make_event("a", last_seen=2000.0),
        make_event("b", last_seen=2001.0),
    ]
    notifications = build(ctx)

    notifications.poll()
    ctx.ui.system[0][2]()

    assert notifications.panel.opened and ctx.invoked == []
    notifications.open_panel()  # already open: it is left open
    assert notifications.panel.opened


def test_the_panel_shows_every_context_and_a_click_only_reads_the_card(
    ctx, make_event
) -> None:
    ctx.cluster.contexts = ["prod", "staging"]
    ctx.cluster.events = [make_event(last_seen=2000.0)]
    notifications = build(ctx)
    notifications.poll()
    notifications.toggle()
    cards = cards_of(notifications)
    assert {card.item.context for card in cards} == {"prod", "staging"}
    staging = next(card for card in cards if card.item.context == "staging")

    click_on(staging)

    assert ctx.invoked == []  # the context stays
    assert notifications.panel.opened  # and so does the panel
    assert notifications.store.unread() == 1  # only the one of prod is left


def test_a_notice_of_the_app_has_no_context_to_open(ctx) -> None:
    notifications = build(ctx)
    notifications.notice("error", "Boom", "it broke", "e", True)
    notifications.toggle()
    (card,) = cards_of(notifications)

    click_on(card)
    notifications.open_context(card.item)

    assert ctx.invoked == []


def test_a_context_the_app_cannot_open_is_said(ctx, make_event) -> None:
    ctx.cluster.events = [make_event(last_seen=2000.0)]
    notifications = build(ctx)
    notifications.poll()
    notifications.open_context(notifications.store.items()[0])
    report = ctx.invoked[0][1]["report"]

    report("There is no context prod.")

    assert ctx.ui.messages[-1][2] == "There is no context prod."


def cards_of(notifications):
    # the cards drawn before go with the next turn of the loop
    testing.settle()
    return [
        one
        for one in testing.find_all(notifications.panel.list, "frame")
        if one.objectName() == "noticeCard"
    ]


def click_on(card) -> None:
    testing.click(card, 5, 5, "release", "right")  # not the left one
    testing.click(card, -50, -50, "release")  # released outside the card
    testing.click(card, 5, 5, "release")


def test_a_context_that_cannot_be_read_is_listed_with_why_and_goes_when_it_can(
    ctx, make_event
) -> None:
    ctx.cluster.contexts = ["prod", "dead"]
    ctx.cluster.events = []
    ctx.cluster.failures["dead"] = RuntimeError("dial tcp: i/o timeout\ncluster away")
    notifications = build(ctx)

    notifications.poll()
    notifications.poll()  # the same notice is not piled up
    (one,) = notifications.store.items()

    assert one.context == "dead" and one.level == "warning"
    assert one.reason == "Could not read dead"
    assert one.message == "dial tcp: i/o timeout"  # the first line of what it said
    ((title, message, click),) = ctx.ui.system  # told once, when it first fails
    assert title == "Could not read dead"
    assert message == "dead: dial tcp: i/o timeout"
    assert notifications.bell.unread == 1
    click()
    assert ctx.invoked[-1][1]["context"] == "dead"
    assert notifications.bell.unread == 0  # the click read it

    ctx.cluster.failures.clear()
    for _ in range(3):  # after its pause
        notifications.poll()
    assert notifications.store.items() == []


def test_the_reason_a_context_failed_is_cut_and_may_be_empty() -> None:
    from kubescope.notifications.extension import first_line

    assert first_line("\n\n  a  \nb") == "a"
    assert first_line("   ") == ""
    assert len(first_line("x" * 1000)) == 300


def test_an_error_of_the_app_goes_back_to_the_context_it_happened_in(ctx) -> None:
    activate(ctx)  # type: ignore[arg-type]

    ctx.events.fire(
        "notification",
        level="error",
        title="Auth failed",
        message="token expired",
        key="e",
        repeat=True,
        context="prod",
    )

    ((_title, message, click),) = ctx.ui.system
    assert message == "prod: token expired"
    click()
    assert ctx.invoked[-1][1]["context"] == "prod"


def test_the_same_alert_is_told_to_the_system_once_until_the_cooldown(ctx) -> None:
    clock = [2000.0]
    settings = NotificationSettings(ctx.settings)
    store = NotificationStore(ctx.data_directory / "n.json")
    notifications = Notifications(ctx, settings, store, now=lambda: clock[0])  # type: ignore[arg-type]

    for _ in range(5):  # the same error, again and again
        clock[0] += 10
        notifications.notice("error", "Boom", "it broke", "e", True, "prod")
    assert len(ctx.ui.system) == 1  # told once

    clock[0] += 1800  # long after
    notifications.notice("error", "Boom", "it broke", "e", True, "prod")
    assert len(ctx.ui.system) == 2

    notifications.notice("error", "Other", "another", "o", True, "prod")
    assert len(ctx.ui.system) == 3  # another alert is not held back
    assert [
        item.count for item in notifications.store.items() if item.reason == "Boom"
    ] == [6]


def test_an_event_that_comes_back_is_not_told_again_within_the_cooldown(
    ctx, make_event
) -> None:
    clock = [2000.0]
    settings = NotificationSettings(ctx.settings)
    store = NotificationStore(ctx.data_directory / "n.json")
    notifications = Notifications(ctx, settings, store, now=lambda: clock[0])  # type: ignore[arg-type]
    ctx.cluster.events = [make_event("a", name="api", last_seen=2000.0)]
    notifications.poll()

    clock[0] = 2100.0  # Kubernetes made the event again for the same thing
    ctx.cluster.events = [make_event("z", name="api", last_seen=2100.0, count=2)]
    notifications.poll()

    assert len(ctx.ui.system) == 1
    assert len(notifications.store.items()) == 1


def test_the_same_error_coming_back_when_switching_contexts_only_counts(ctx) -> None:
    clock = [2000.0]
    settings = NotificationSettings(ctx.settings)
    store = NotificationStore(ctx.data_directory / "n.json")
    notifications = Notifications(ctx, settings, store, now=lambda: clock[0])  # type: ignore[arg-type]
    notifications.notice(
        "error", "Login failed", "expired", "error:prod:x", True, "prod"
    )
    notifications.open_context(notifications.store.items()[0])  # the person read it
    assert notifications.bell.unread == 0

    for _ in range(4):  # switching back and forth: the banner shows it each time
        clock[0] += 20
        notifications.notice(
            "error", "Login failed", "expired", "error:prod:x", True, "prod"
        )

    (one,) = notifications.store.items()
    assert one.count == 5 and notifications.bell.unread == 0  # counted, not news
    assert len(ctx.ui.system) == 1

    clock[0] += 3600  # much later it is news again
    notifications.notice(
        "error", "Login failed", "expired", "error:prod:x", True, "prod"
    )
    assert notifications.bell.unread == 1


def test_an_error_of_a_context_that_cannot_be_read_is_folded_into_its_notice(
    ctx,
) -> None:
    ctx.cluster.contexts = ["dead"]
    ctx.cluster.failures["dead"] = RuntimeError("connection refused")
    notifications = build(ctx)
    notifications.notice("error", "Login failed", "x", "error:dead:a", True, "dead")
    notifications.notice("error", "Other", "y", "error:other:b", True, "other")
    notifications.notice("warning", "Careful", "z", "w", True, "dead")
    assert len(notifications.store.items()) == 3

    notifications.poll()  # it cannot be read: its own notice takes the place

    reasons = sorted(item.reason for item in notifications.store.items())
    assert reasons == ["Careful", "Could not read dead", "Other"]  # not the login one

    notifications.notice("error", "Login failed", "x", "error:dead:a", True, "dead")
    assert "Login failed" not in [item.reason for item in notifications.store.items()]


def test_the_first_look_waits_and_a_switch_of_context_does_not_read_the_clusters(
    ctx,
) -> None:
    notifications = build(ctx)

    assert notifications.first_look.isActive()
    assert notifications.first_look.interval() == 30_000
    notifications.context_changed()

    assert ctx.cluster.asked == []
    notifications.first_look.timeout.emit()
    assert [name for name, _types in ctx.cluster.asked] == ["prod"]


def test_unloading_it_takes_its_bell_out_of_the_top_bar(ctx) -> None:
    notifications = build(ctx)
    bell = notifications.bell

    notifications.close()
    assert not notifications.first_look.isActive()
    assert not notifications.timer.isActive()
    testing.settle()

    assert not ctx.ui.components.is_alive(bell)


def test_clearing_is_not_undone_by_the_next_look_at_the_clusters(
    ctx, make_event
) -> None:
    ctx.cluster.contexts = ["prod", "dead"]
    ctx.cluster.events = [make_event("a", name="api", last_seen=2000.0)]
    ctx.cluster.failures["dead"] = RuntimeError("connection refused")
    notifications = build(ctx)
    notifications.poll()
    assert len(notifications.store.items()) == 2  # an event and a dead context

    notifications.clear()
    for _ in range(4):  # the cluster still has the event, the context is still dead
        notifications.poll()
    assert notifications.store.items() == []

    ctx.cluster.events = [make_event("b", name="api", last_seen=6000.0)]
    notifications.poll()
    assert [item.name for item in notifications.store.items()] == ["api"]


def test_a_failed_sign_in_is_not_a_notification_the_banner_says_it(
    ctx, make_event
) -> None:
    ctx.cluster.contexts = ["prod", "dead", "gone"]
    ctx.cluster.events = []
    ctx.cluster.failures["dead"] = RuntimeError(
        "exec: process returned 255. aws: Token has expired and refresh failed"
    )
    ctx.cluster.failures["gone"] = RuntimeError("dial tcp: i/o timeout")
    notifications = build(ctx)

    notifications.poll()

    assert [item.context for item in notifications.store.items()] == ["gone"]
    assert [title for title, _message, _click in ctx.ui.system] == [
        "Could not read gone"
    ]


def test_a_context_listed_as_unreadable_that_now_fails_to_sign_in_is_taken_out(
    ctx, make_event
) -> None:
    ctx.cluster.contexts = ["dead"]
    ctx.cluster.failures["dead"] = RuntimeError("dial tcp: i/o timeout")
    notifications = build(ctx)
    notifications.poll()
    assert len(notifications.store.items()) == 1

    ctx.cluster.failures["dead"] = RuntimeError("Error loading SSO token: expired")
    for _ in range(3):  # after its pause
        notifications.poll()

    assert notifications.store.items() == []


def test_an_ignored_object_is_not_kept(ctx, make_event) -> None:
    ctx.cluster.contexts = ["prod"]
    ctx.cluster.events = [make_event("a")]
    ctx.settings["ignored"] = ["*/*"]
    notifications = build(ctx)

    notifications.poll()

    assert notifications.store.items() == []


def test_the_system_is_not_told_outside_the_window(ctx, make_event) -> None:
    from datetime import datetime

    ctx.cluster.events = [make_event("a", last_seen=2000.0)]
    notifications = build(ctx)
    moment = datetime.fromtimestamp(2000.0)
    hour = (moment.hour + 2) % 24  # a window that starts two hours from now
    ctx.settings["window_enabled"] = True
    ctx.settings["window_start"] = f"{hour:02d}:00"
    ctx.settings["window_end"] = f"{(hour + 1) % 24:02d}:00"

    notifications.poll()

    assert ctx.ui.system == [] and notifications.bell.unread == 1


def test_an_alert_that_keeps_happening_is_told_once_and_again_only_after_a_quiet_time(
    ctx, make_event
) -> None:
    clock = [2000.0]
    settings = NotificationSettings(ctx.settings)
    store = NotificationStore(ctx.data_directory / "n.json")
    notifications = Notifications(ctx, settings, store, now=lambda: clock[0])  # type: ignore[arg-type]
    ctx.cluster.events = [make_event("a", name="api", last_seen=1990.0)]
    notifications.poll()
    assert len(ctx.ui.system) == 1

    for minute in range(1, 50):  # it goes on for most of an hour, every minute
        clock[0] = 2000.0 + minute * 60
        ctx.cluster.events = [
            make_event("a", name="api", last_seen=clock[0] - 5, count=2 + minute)
        ]
        notifications.poll()
    assert len(ctx.ui.system) == 1  # no word about it going on
    assert notifications.store.items()[0].count == 51
    assert notifications.bell.unread == 1  # and nothing new to read

    clock[0] += 7200.0  # two hours of quiet, and then it happens again
    ctx.cluster.events = [make_event("a", name="api", last_seen=clock[0] - 5, count=99)]
    notifications.poll()

    assert len(ctx.ui.system) == 2


def test_the_time_a_card_shows_is_when_it_began(ctx, make_event) -> None:
    clock = [5000.0]
    settings = NotificationSettings(ctx.settings)
    store = NotificationStore(ctx.data_directory / "n.json")
    notifications = Notifications(ctx, settings, store, now=lambda: clock[0])  # type: ignore[arg-type]
    ctx.cluster.events = [
        make_event("a", name="api", last_seen=4990.0, count=9, first_seen=2480.0)
    ]
    notifications.poll()
    notifications.toggle()

    (card,) = cards_of(notifications)
    labels = testing.texts(card)

    assert any("9×" in text and "42m" in text for text in labels)


def test_an_alert_that_left_the_cluster_leaves_the_panel(ctx, make_event) -> None:
    ctx.cluster.events = [make_event("a", name="api"), make_event("b", name="web")]
    notifications = build(ctx)
    notifications.poll()
    assert len(notifications.store.items()) == 2

    ctx.cluster.events = [make_event("b", name="web")]
    notifications.poll()

    assert [item.name for item in notifications.store.items()] == ["web"]


def test_the_kinds_the_person_turns_off_are_not_shown_counted_nor_told(
    ctx, make_event
) -> None:
    ctx.cluster.events = [
        make_event("a", name="api", reason="BackOff", last_seen=2000.0),
        make_event("b", name="web", reason="Unhealthy", last_seen=2000.0),
    ]
    ctx.settings["hidden"] = ["warning", "normal"]
    notifications = build(ctx)

    notifications.poll()

    assert [item.reason for item in notifications.visible()] == ["BackOff"]
    assert len(notifications.store.items()) == 2  # kept, only not shown
    assert notifications.bell.unread == 1
    ((title, _, _),) = ctx.ui.system
    assert title == "BackOff"

    ctx.settings["hidden"] = ["error", "warning", "normal", "info"]
    notifications.refresh()
    assert notifications.visible() == [] and notifications.bell.unread == 0
    ctx.ui.system.clear()
    notifications.announce(notifications.store.items())
    assert ctx.ui.system == []


def test_the_settings_choose_the_kinds_shown(ctx) -> None:
    notifications = build(ctx)
    ctx.settings.pop("hidden")  # what nobody chose: the defaults
    ctx.settings.pop("silent")
    panel = NotificationSettingsPanel(
        UiComponents(), notifications.settings, notifications.apply_settings
    )
    panel.load()
    assert {k for k, box in panel.kinds.items() if box.isChecked()} == {
        "error",
        "pod",
        "info",
    }
    assert {k for k, box in panel.told.items() if box.isChecked()} == {
        "error",
        "pod",
        "info",
    }

    panel.kinds["warning"].setChecked(True)
    panel.told["warning"].setChecked(True)
    panel.save()
    assert ctx.settings["hidden"] == ["normal", "action", "task"]
    assert ctx.settings["silent"] == ["normal", "action", "task"]
    panel.load()
    assert panel.kinds["warning"].isChecked()

    ctx.settings["hidden"] = "nope"  # damaged: the defaults
    assert notifications.settings.shown == ["error", "info", "pod"]


def test_informative_events_are_read_only_when_asked_and_not_told_to_the_system(
    ctx, make_event
) -> None:
    ctx.cluster.events = [
        make_event("n", name="api", reason="Pulled", type="Normal", last_seen=2000.0),
        make_event("w", name="web", reason="Unhealthy", last_seen=2000.0),
    ]
    notifications = build(ctx)
    notifications.poll()
    assert ctx.cluster.asked[-1][1] == ("Warning",)  # not asked for by default

    ctx.settings["hidden"] = ["info"]
    notifications._busy = False
    notifications.poll()

    assert ctx.cluster.asked[-1][1] == ("Warning", "Normal")
    assert sorted(item.reason for item in notifications.visible()) == [
        "Pulled",
        "Unhealthy",
    ]
    assert "Pulled" not in [title for title, _, _ in ctx.ui.system]

    ctx.settings["hidden"] = ["normal"]  # off again: kept, not shown
    notifications.refresh()
    assert [item.reason for item in notifications.visible()] == ["Unhealthy"]
    ctx.cluster.events = [ctx.cluster.events[1]]
    notifications.poll()
    assert any(item.reason == "Pulled" for item in notifications.store.items())


def test_a_card_has_small_buttons_to_read_it_and_to_go_to_its_context(
    ctx, make_event
) -> None:
    ctx.cluster.events = [make_event(last_seen=2000.0)]
    notifications = build(ctx)
    notifications.poll()
    notifications.toggle()
    (card,) = cards_of(notifications)
    assert [one.text() for one in card.buttons] == ["Mark as read", "Go to context"]

    card.buttons[0].click()

    assert notifications.store.unread() == 0
    assert notifications.panel.opened and ctx.invoked == []
    (card,) = cards_of(notifications)
    # read already: only the way to the context
    assert [one.text() for one in card.buttons] == ["Go to context"]

    card.buttons[0].click()

    assert ctx.invoked[0][1]["context"] == "prod"
    assert not notifications.panel.opened


def test_a_notice_of_the_app_has_no_button_to_a_context(ctx) -> None:
    notifications = build(ctx)
    notifications.notice("error", "Boom", "it broke", "e", True)
    notifications.toggle()
    (card,) = cards_of(notifications)

    assert [one.text() for one in card.buttons] == ["Mark as read"]


def test_what_the_app_did_is_kept_and_told_by_the_kind_the_person_chose(
    ctx,
) -> None:
    notifications = build(ctx)
    clicked: list[int] = []

    notifications.notice(
        "info",
        "KubeScope",
        "Scaled api",
        "action:1",
        True,
        "prod",
        "action",
        lambda: clicked.append(1),
        True,
    )
    notifications.notice(
        "info", "KubeScope", "web is ready", "pod:1", True, "prod", "pod", None, True
    )

    assert sorted(i.message for i in notifications.visible()) == [
        "Scaled api",
        "web is ready",
    ]
    assert [(t, m) for t, m, _c in ctx.ui.system] == [
        ("KubeScope", "Scaled api"),
        ("KubeScope", "web is ready"),
    ]
    ctx.ui.system[0][2]()
    assert clicked == [1]
    ctx.ui.system[1][2]()  # no click given: the panel opens
    assert notifications.panel.opened

    ctx.settings["silent"] = ["action", "pod"]  # no longer told, still listed
    notifications.notice(
        "info", "KubeScope", "done again", "action:2", True, "", "action", None, True
    )
    ctx.settings["hidden"] = ["action"]  # not listed: not told either, even if asked
    ctx.settings["silent"] = []
    notifications.notice(
        "info", "KubeScope", "third", "action:3", True, "", "action", None, True
    )
    assert len(ctx.ui.system) == 2
    assert [i.message for i in notifications.visible()] == ["web is ready"]


def test_a_notice_of_something_done_is_not_told_when_the_system_is_off_or_not_asked(
    ctx,
) -> None:
    ctx.settings["system_notifications"] = False
    notifications = build(ctx)

    notifications.notice(
        "info", "KubeScope", "Scaled", "action:1", True, "", "action", None, True
    )
    notifications.notice(
        "info", "KubeScope", "Quiet", "action:2", True, "", "action", None, False
    )
    assert ctx.ui.system == []  # the system is off, or was not asked


def test_the_kinds_an_earlier_version_kept_are_read_and_new_ones_are_on(ctx) -> None:
    ctx.settings["shown"] = ["error", "info"]  # kept when only these four existed
    settings = NotificationSettings(ctx.settings)

    assert settings.shown == ["error", "info", "action", "pod", "task"]
    settings.shown = ["warning"]
    assert settings.shown == ["warning"]  # what is chosen now wins


def test_the_kinds_can_be_put_back_to_the_defaults(ctx) -> None:
    ctx.settings["hidden"] = []
    ctx.settings["silent"] = []
    notifications = build(ctx)
    panel = NotificationSettingsPanel(
        UiComponents(), notifications.settings, notifications.apply_settings
    )
    panel.load()
    assert all(box.isChecked() for box in panel.kinds.values())

    panel.reset.click()

    assert {k for k, box in panel.kinds.items() if box.isChecked()} == {
        "error",
        "pod",
        "info",
    }
    assert {k for k, box in panel.told.items() if box.isChecked()} == {
        "error",
        "pod",
        "info",
    }
    assert ctx.settings["hidden"] == []  # nothing is kept until it is saved
    panel.save()
    assert ctx.settings["hidden"] == ["warning", "normal", "action", "task"]
