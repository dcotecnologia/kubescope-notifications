"""The section of the Settings of the extension: how often the cluster is
looked at."""

from collections.abc import Callable

from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from kubescope.notifications.settings import (
    DEFAULT,
    HIDDEN,
    MAXIMUM,
    MINIMUM,
    SILENT,
    NotificationSettings,
)


class NotificationSettingsPanel(QWidget):
    def __init__(
        self, settings: NotificationSettings, apply: Callable[[], None]
    ) -> None:
        super().__init__()
        self.settings = settings
        self._apply = apply
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(
            self._note(
                self.tr(
                    "Warnings and errors of every context of your kubeconfig, "
                    "and what KubeScope itself reports, are kept here. Click the "
                    "bell in the top bar to read them."
                )
            )
        )

        layout.addSpacing(6)
        layout.addWidget(self._title(self.tr("Reading")))
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(QLabel(self.tr("Look for new events every")))
        self.interval = QSpinBox()  # whole seconds, within what the app allows
        self.interval.setRange(MINIMUM, MAXIMUM)
        self.interval.setSuffix(self.tr(" seconds"))
        self.interval.setKeyboardTracking(False)
        self.interval.setMinimumWidth(140)
        row.addWidget(self.interval)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(
            self._note(
                self.tr(
                    "Every context of your kubeconfig is read in the background, "
                    "two at a time. One that is not signed in is left alone for "
                    "longer each time."
                )
            )
        )

        layout.addSpacing(10)
        layout.addWidget(self._title(self.tr("Kinds shown")))
        names = {
            "error": self.tr("Errors of the cluster"),
            "warning": self.tr("Warnings of the cluster and of the app"),
            "normal": self.tr("Informative events of the cluster"),
            "action": self.tr("Confirmations of your actions"),
            "pod": self.tr("Status of Pods after an action"),
            "task": self.tr("Finished activities"),
            "info": self.tr("Updates of the app"),
        }
        table = QFrame()
        table.setObjectName("kindsTable")
        table.setStyleSheet(
            "QFrame#kindsTable { border: 1px solid rgba(128, 128, 128, 90);"
            " border-radius: 8px; }"
            "QFrame#kindsTable QLabel, QFrame#kindsTable QCheckBox"
            " { border: 0; }"
            "QFrame#kindsTable QFrame#kindsRule"
            " { background: rgba(128, 128, 128, 60); border: 0; }"
        )
        grid = QGridLayout(table)
        grid.setContentsMargins(14, 8, 14, 8)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        grid.setColumnStretch(0, 1)
        center = Qt.AlignmentFlag.AlignCenter
        for column, text in ((1, self.tr("Show")), (2, self.tr("Tell the system"))):
            head = self._note(text.upper())
            head.setAlignment(center)
            head.setMinimumWidth(120)
            head.setContentsMargins(0, 4, 0, 8)
            grid.addWidget(head, 0, column)
        self.kinds: dict[str, QCheckBox] = {}  # listed and counted
        self.told: dict[str, QCheckBox] = {}  # told to the operating system
        for row, (kind, name) in enumerate(names.items(), start=1):
            rule = QFrame()
            rule.setObjectName("kindsRule")
            rule.setFixedHeight(1)
            grid.addWidget(rule, row * 2 - 1, 0, 1, 3)
            label = QLabel(name)
            label.setMinimumHeight(36)
            grid.addWidget(label, row * 2, 0)
            self.kinds[kind] = QCheckBox()
            self.told[kind] = QCheckBox()
            grid.addWidget(self.kinds[kind], row * 2, 1, center)
            grid.addWidget(self.told[kind], row * 2, 2, center)
        layout.addWidget(table)
        reset_row = QHBoxLayout()
        self.reset = QPushButton(self.tr("Restore the defaults"))
        self.reset.setProperty("variant", "secondary")  # the buttons of the app
        self.reset.clicked.connect(self._reset_kinds)
        reset_row.addWidget(self.reset)
        reset_row.addStretch(1)
        layout.addLayout(reset_row)
        layout.addWidget(
            self._note(
                self.tr(
                    "A kind that is off is not listed, counted in the bell nor "
                    "told to the system; it is kept, and comes back when turned on."
                )
            )
        )

        layout.addSpacing(10)
        layout.addWidget(self._title(self.tr("System notices")))
        self.system = QCheckBox(
            self.tr("Tell the operating system when something new happens")
        )
        layout.addWidget(self.system)
        hint = self._note(
            self.tr("Shows a notice of the system, which opens the app when clicked.")
        )
        hint.setContentsMargins(26, 0, 0, 0)  # under the text, not under the box
        layout.addWidget(hint)

        self.window_on = QCheckBox(self.tr("Tell the system only between these hours"))
        layout.addWidget(self.window_on)
        hours = QHBoxLayout()
        hours.setContentsMargins(26, 0, 0, 0)
        hours.setSpacing(12)
        self.start = QTimeEdit()
        self.end = QTimeEdit()
        for edit in (self.start, self.end):
            edit.setDisplayFormat("HH:mm")
        hours.addWidget(QLabel(self.tr("From")))
        hours.addWidget(self.start)
        hours.addWidget(QLabel(self.tr("to")))
        hours.addWidget(self.end)
        hours.addStretch(1)
        layout.addLayout(hours)
        window_hint = self._note(
            self.tr(
                "Outside these hours the notifications are still kept in the "
                "bell, but the system is not told. An end before the start runs "
                "over midnight."
            )
        )
        window_hint.setContentsMargins(26, 0, 0, 0)
        layout.addWidget(window_hint)
        self.window_on.toggled.connect(self._window_toggled)

        layout.addSpacing(10)
        layout.addWidget(self._title(self.tr("Ignored objects")))
        self.ignored = QPlainTextEdit()
        self.ignored.setMaximumHeight(110)
        self.ignored.setPlaceholderText("Pod/batch-*\nprod/Deployment/api")
        layout.addWidget(self.ignored)
        layout.addWidget(
            self._note(
                self.tr(
                    "One per line, as Kind/name or context/Kind/name. * and ? "
                    "stand for any text. What matches is not kept nor told."
                )
            )
        )
        layout.addStretch(1)
        self.interval.setValue(DEFAULT)

    @staticmethod
    def _note(text: str) -> QLabel:
        """A line of explanation, quieter than what it explains."""
        label = QLabel(text)
        label.setProperty("variant", "muted")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _title(text: str) -> QLabel:
        """The title of a group of the section, like the one of the card."""
        label = QLabel(text.upper())
        label.setProperty("variant", "cardTitle")
        return label

    def _reset_kinds(self) -> None:
        """Mark the kinds as they are by default; what is kept is what Save
        writes, as with the rest of the section."""
        for kind in self.kinds:
            self.kinds[kind].setChecked(kind not in HIDDEN)
            self.told[kind].setChecked(kind not in SILENT)

    def _window_toggled(self, on: bool) -> None:
        self.start.setEnabled(on)
        self.end.setEnabled(on)

    def load(self) -> None:
        self.interval.setValue(self.settings.interval)
        for kind in self.kinds:
            self.kinds[kind].setChecked(kind in self.settings.shown)
            self.told[kind].setChecked(kind in self.settings.told)
        self.system.setChecked(self.settings.system_notifications)
        self.window_on.setChecked(self.settings.window_enabled)
        self.start.setTime(QTime.fromString(self.settings.window_start, "HH:mm"))
        self.end.setTime(QTime.fromString(self.settings.window_end, "HH:mm"))
        self._window_toggled(self.settings.window_enabled)
        self.ignored.setPlainText("\n".join(self.settings.ignored))

    def save(self) -> bool:
        self.interval.interpretText()  # what is typed and not yet confirmed
        self.settings.interval = self.interval.value()
        self.settings.shown = [
            kind for kind, box in self.kinds.items() if box.isChecked()
        ]
        self.settings.told = [
            kind for kind, box in self.told.items() if box.isChecked()
        ]
        self.settings.system_notifications = self.system.isChecked()
        self.settings.window_enabled = self.window_on.isChecked()
        self.settings.window_start = self.start.time().toString("HH:mm")
        self.settings.window_end = self.end.time().toString("HH:mm")
        self.settings.ignored = self.ignored.toPlainText().splitlines()
        self._apply()
        return True
