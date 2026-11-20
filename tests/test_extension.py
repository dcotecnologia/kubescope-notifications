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


def test_the_bell_goes_to_the_top_bar_and_the_cluster_is_read_for_its_context(
    ctx, make_event
) -> None:
    ctx.cluster.events = [make_event("a"), make_event("b", reason="Unhealthy")]
    notifications = build(ctx)
    assert ctx.ui.buttons == [("kubescope.notifications", notifications.bell)]

    notifications.poll()

    assert ctx.cluster.asked == [("prod", ("Warning",))]
    assert notifications.bell.unread == 2
    assert len(notifications.store.items()) == 2


def test_nothing_is_read_without_a_context_or_while_a_read_is_going(ctx) -> None:
    notifications = build(ctx)
    ctx.current_context = None

    notifications.poll()
    ctx.current_context = "prod"
    notifications._busy = True
    notifications.poll()

    assert ctx.cluster.asked == []


def test_a_read_that_fails_keeps_what_is_kept_and_the_next_one_goes_on(
    ctx, make_event
) -> None:
    ctx.cluster.events = [make_event()]
    notifications = build(ctx)
    notifications.poll()
    ctx.cluster.failure = RuntimeError("not signed in")

    notifications.poll()

    assert len(notifications.store.items()) == 1 and not notifications._busy
    ctx.cluster.failure = None
    notifications.poll()
    assert len(ctx.cluster.asked) == 3


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
    assert panel.interval.value() == 30
    panel.interval.setValue(120)
    assert panel.save() is True
    assert notifications.timer.interval() == 120000


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
