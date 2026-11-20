"""The section of the Settings of the extension: how often the cluster is
looked at."""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from kubescope.notifications.settings import DEFAULT, NotificationSettings


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
        self.interval = QComboBox()
        self.interval.setMinimumWidth(220)
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
        layout.addStretch(1)
        self._fill(DEFAULT)

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

    def _choices(self) -> list[tuple[str, int]]:
        return [
            (self.tr("15 seconds"), 15),
            (self.tr("30 seconds"), 30),
            (self.tr("1 minute"), 60),
            (self.tr("2 minutes"), 120),
            (self.tr("5 minutes"), 300),
            (self.tr("15 minutes"), 900),
            (self.tr("1 hour"), 3600),
        ]

    def _fill(self, chosen: int) -> None:
        """List the usual times and select `chosen`; a time kept by an older
        version that is not one of them is listed too, so nothing is lost."""
        self.interval.clear()
        for label, seconds in self._choices():
            self.interval.addItem(label, seconds)
        if self.interval.findData(chosen) < 0:
            self.interval.addItem(
                self.tr("{seconds} seconds").format(seconds=chosen), chosen
            )
        self.interval.setCurrentIndex(self.interval.findData(chosen))

    def load(self) -> None:
        self._fill(self.settings.interval)
        self.system.setChecked(self.settings.system_notifications)

    def save(self) -> bool:
        self.settings.interval = self.interval.currentData()
        self.settings.system_notifications = self.system.isChecked()
        self._apply()
        return True
