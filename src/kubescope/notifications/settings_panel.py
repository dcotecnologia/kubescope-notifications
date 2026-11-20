"""The section of the Settings of the extension: how often the cluster is
looked at."""

from collections.abc import Callable

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QWidget

from kubescope.notifications.settings import DEFAULT, NotificationSettings


class NotificationSettingsPanel(QWidget):
    def __init__(
        self, settings: NotificationSettings, apply: Callable[[], None]
    ) -> None:
        super().__init__()
        self.settings = settings
        self._apply = apply
        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.interval = QComboBox()
        self.interval.setMinimumWidth(200)
        self.interval.setToolTip(
            self.tr("How often the events of the cluster are read.")
        )
        form.addRow(self.tr("Look for new events every"), self.interval)
        self.system = QCheckBox(
            self.tr("Tell the operating system when something new happens")
        )
        self.system.setToolTip(
            self.tr("Shows a notice of the system, which opens the app when clicked.")
        )
        form.addRow(self.system)
        self._fill(DEFAULT)

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
