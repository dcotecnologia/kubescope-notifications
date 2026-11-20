"""Fixtures of the tests of the notifications."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Never read or write the real user settings during tests."""
    monkeypatch.setenv("KUBESCOPE_CONFIG_DIR", str(tmp_path / "config"))
    home = tmp_path / "isolated-home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))


@pytest.fixture(autouse=True)
def light_theme():
    from kubescope import theme

    theme.set_theme("light")
    yield
    theme.set_theme("light")


@pytest.fixture(autouse=True)
def delete_the_windows():
    """Delete what a test shows before the application goes away: a window that
    outlives it crashes the run when it ends."""
    if QApplication.instance() is None:
        QApplication([])
    before = set(QApplication.topLevelWidgets())
    yield
    for widget in set(QApplication.topLevelWidgets()) - before:
        widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


class FakeUi:
    """`ctx.ui`: runs an action at once and remembers what was added."""

    def __init__(self) -> None:
        self.window = QWidget()
        self.window.resize(900, 600)
        self.central = QWidget(self.window)
        self.central.resize(900, 600)
        self.buttons: list[tuple[str, QWidget]] = []
        self.system: list[tuple] = []  # what was told to the operating system

    def themed(self, color, text=False):
        return color

    def add_top_bar_button(self, owner, button):
        button.setParent(self.central)
        button.move(840, 7)
        self.buttons.append((owner, button))

    def show_system_notification(self, title, message, on_click=None):
        self.system.append((title, message, on_click))
        return True

    def run_action(self, function, on_success, *arguments, on_error=None, quiet=False):
        try:
            answer = function(*arguments)
        except Exception as error:
            if on_error is None:
                raise
            on_error(str(error))
            return
        on_success(answer)


class FakeCluster:
    def __init__(self) -> None:
        self.contexts: list[str] = ["prod"]
        self.events: list = []  # what every context answers
        self.failure: Exception | None = None  # every context fails
        self.failures: dict[str, Exception] = {}  # these contexts fail
        self.asked: list[tuple] = []

    def list_contexts(self):
        return list(self.contexts)

    def get_events(self, context, types=("Warning",)):
        self.asked.append((context, types))
        failure = self.failures.get(context) or self.failure
        if failure is not None:
            raise failure
        return self.events


class FakeEvents:
    def __init__(self) -> None:
        self.handlers: dict[str, list] = {}

    def on(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)
        return lambda: None

    def fire(self, event, **arguments):
        for handler in self.handlers.get(event, []):
            handler(**arguments)


class FakeSettings(dict):
    def set(self, key, value):
        self[key] = value


class FakeCtx:
    """What the app gives the extension, in the hands of the test."""

    id = "kubescope.notifications"

    def __init__(self, data_directory) -> None:
        self.ui: FakeUi | None = FakeUi()
        self.cluster = FakeCluster()
        self.events = FakeEvents()
        self.settings = FakeSettings()
        self.current_context: str | None = "prod"
        self.data_directory = data_directory
        self.sections: list[tuple] = []
        self.cleanups: list = []

    def add_settings_section(self, title, factory):
        self.sections.append((title, factory))

    def on_unload(self, callback):
        self.cleanups.append(callback)


@pytest.fixture
def ctx(tmp_path):
    return FakeCtx(tmp_path / "data")


@pytest.fixture
def make_event():
    return _make_event


def _make_event(uid="u1", reason="BackOff", last_seen=1000.0, **fields):
    from kubescope.sdk.models import ClusterEvent

    values = {
        "uid": uid,
        "type": "Warning",
        "reason": reason,
        "namespace": "ns",
        "kind": "Pod",
        "name": "api",
        "message": "Back-off restarting failed container",
        "count": 1,
        "first_seen": last_seen,
        "last_seen": last_seen,
    }
    values.update(fields)
    return ClusterEvent(**values)
