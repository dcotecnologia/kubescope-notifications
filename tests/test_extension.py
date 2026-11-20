import kubescope.notifications as package
from kubescope.notifications import extension
from kubescope.notifications.extension import Notifications, activate
from kubescope.notifications.settings import NotificationSettings
from kubescope.notifications.settings_panel import NotificationSettingsPanel
from kubescope.notifications.store import NotificationStore


def build(ctx, now=2000.0) -> Notifications:
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
    assert len(notifications.store.items()) == 1 and not notifications._busy
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


def test_the_bell_opens_the_panel_and_what_was_seen_is_read(ctx, make_event) -> None:
    ctx.cluster.events = [make_event()]
    notifications = build(ctx)
    notifications.poll()
    assert notifications.bell.unread == 1

    notifications.bell.click()

    assert notifications.panel.opened and notifications.bell.isChecked()
    assert notifications.bell.unread == 0 and notifications.store.unread() == 0

    notifications.bell.click()  # again: it closes
    assert not notifications.panel.opened and not notifications.bell.isChecked()


def test_an_event_that_comes_while_the_panel_is_open_does_not_ask_for_attention(
    ctx, make_event
) -> None:
    notifications = build(ctx, now=500.0)
    notifications.toggle()
    ctx.cluster.events = [make_event(last_seen=900.0)]

    notifications.poll()

    assert notifications.bell.unread == 0 and len(notifications.store.items()) == 1


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
        notifications.settings, notifications.apply_settings
    )
    panel.load()
    assert panel.interval.currentData() == 30
    assert panel.system.isChecked()  # on unless turned off
    panel.interval.setCurrentIndex(panel.interval.findData(120))
    panel.system.setChecked(False)
    assert panel.save() is True
    assert notifications.timer.interval() == 120000
    assert ctx.settings["system_notifications"] is False
    panel.load()
    assert not panel.system.isChecked()


def test_a_time_that_is_not_one_of_the_usual_is_kept_in_the_list(ctx) -> None:
    ctx.settings["interval"] = 45
    notifications = build(ctx)
    panel = NotificationSettingsPanel(
        notifications.settings, notifications.apply_settings
    )

    panel.load()

    assert panel.interval.currentData() == 45
    assert panel.interval.currentText() == "45 seconds"


def test_activating_it_wires_the_events_the_settings_and_the_cleanup(
    ctx, make_event
) -> None:
    ctx.cluster.events = [make_event()]

    activate(ctx)  # type: ignore[arg-type]

    assert [title for title, _ in ctx.sections] == ["Notifications"]
    ctx.events.fire("context_changed", context="prod")
    assert ctx.cluster.asked == [("prod", ("Warning",))]
    ctx.events.fire("theme_changed")
    (_title, factory) = ctx.sections[0]
    assert isinstance(factory(), NotificationSettingsPanel)
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
    click()
    assert notifications.panel.opened
    click()  # already open: it is left open
    assert notifications.panel.opened


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


def test_the_system_is_not_told_when_it_is_turned_off_or_the_window_is_in_front(
    ctx, make_event, monkeypatch
) -> None:
    ctx.cluster.events = [make_event("a", last_seen=2000.0)]
    notifications = build(ctx)
    ctx.settings["system_notifications"] = False
    notifications.poll()
    assert ctx.ui.system == []

    ctx.settings["system_notifications"] = True
    ctx.cluster.events = [make_event("b", last_seen=2001.0)]
    monkeypatch.setattr(ctx.ui.window, "isActiveWindow", lambda: True)
    notifications.poll()
    assert ctx.ui.system == []


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
