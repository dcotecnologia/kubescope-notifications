"""The section of the Settings of the extension: how often the cluster is
looked at."""

from collections.abc import Callable

from PySide6.QtWidgets import QFormLayout, QSpinBox, QWidget

from kubescope.notifications.settings import (
    DEFAULT,
    MAXIMUM,
    MINIMUM,
    NotificationSettings,
)


class NotificationSettingsPanel(QWidget):
    def __init__(
        self, settings: NotificationSettings, apply: Callable[[], None]
    ) -> None:
        super().__init__()
        self.settings = settings
        self._apply = apply
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        self.interval = QSpinBox()
        self.interval.setRange(MINIMUM, MAXIMUM)
        self.interval.setSuffix(" s")
        self.interval.setValue(DEFAULT)
        self.interval.setToolTip(
            self.tr("How often the events of the cluster are read, in seconds.")
        )
        form.addRow(self.tr("Look for new events every"), self.interval)

    def load(self) -> None:
        self.interval.setValue(self.settings.interval)

    def save(self) -> bool:
        self.settings.interval = self.interval.value()
        self._apply()
        return True
