"""The section of the Settings of the extension: how often the cluster is
looked at."""

from collections.abc import Callable
from typing import Any

from kubescope.sdk import translate

from kubescope.notifications.settings import (
    DEFAULT,
    HIDDEN,
    MAXIMUM,
    MINIMUM,
    SILENT,
    NotificationSettings,
)


class NotificationSettingsPanel:
    def __init__(
        self,
        components: Any,
        settings: NotificationSettings,
        apply: Callable[[], None],
    ) -> None:
        self.components = components
        self.settings = settings
        self._apply = apply

        self.widget = components.widget(load=self.load, save=self.save)
        # whole seconds, within what the app allows
        self.interval = components.number_field(MINIMUM, MAXIMUM)
        self.interval.setSuffix(translate("NotificationSettingsPanel", " seconds"))
        self.interval.setKeyboardTracking(False)
        self.interval.setMinimumWidth(140)
        names = {
            "error": translate("NotificationSettingsPanel", "Errors of the cluster"),
            "warning": translate(
                "NotificationSettingsPanel", "Warnings of the cluster and of the app"
            ),
            "normal": translate(
                "NotificationSettingsPanel", "Informative events of the cluster"
            ),
            "action": translate(
                "NotificationSettingsPanel", "Confirmations of your actions"
            ),
            "pod": translate(
                "NotificationSettingsPanel", "Status of Pods after an action"
            ),
            "task": translate("NotificationSettingsPanel", "Finished activities"),
            "info": translate("NotificationSettingsPanel", "Updates of the app"),
        }
        table, (self.kinds, self.told) = components.check_matrix(
            [
                translate("NotificationSettingsPanel", "Show"),
                translate("NotificationSettingsPanel", "Tell the system"),
            ],
            list(names.items()),
        )
        self.reset = components.button(
            translate("NotificationSettingsPanel", "Restore the defaults"),
            on_click=self._reset_kinds,
        )
        self.system = components.checkbox(
            translate(
                "NotificationSettingsPanel",
                "Tell the operating system when something new happens",
            )
        )
        self.window_on = components.checkbox(
            translate(
                "NotificationSettingsPanel", "Tell the system only between these hours"
            )
        )
        self.start = components.time_field()
        self.end = components.time_field()
        hours = components.row(
            components.label(translate("NotificationSettingsPanel", "From")),
            self.start,
            components.label(translate("NotificationSettingsPanel", "to")),
            self.end,
            None,
        )
        hours.setContentsMargins(26, 0, 0, 0)
        self.ignored = components.text_area("Pod/batch-*\nprod/Deployment/api", 110)
        layout = components.column(
            self._note(
                translate(
                    "NotificationSettingsPanel",
                    "Warnings and errors of every context of your kubeconfig, "
                    "and what KubeScope itself reports, are kept here. Click the "
                    "bell in the top bar to read them.",
                )
            ),
            components.spacer(6),
            self._title(translate("NotificationSettingsPanel", "Reading")),
            components.row(
                components.label(
                    translate("NotificationSettingsPanel", "Look for new events every")
                ),
                self.interval,
                None,
            ),
            self._note(
                translate(
                    "NotificationSettingsPanel",
                    "Every context of your kubeconfig is read in the background, "
                    "two at a time. One that is not signed in is left alone for "
                    "longer each time.",
                )
            ),
            components.spacer(10),
            self._title(translate("NotificationSettingsPanel", "Kinds shown")),
            table,
            components.row(self.reset, None),
            self._note(
                translate(
                    "NotificationSettingsPanel",
                    "A kind that is off is not listed, counted in the bell nor "
                    "told to the system; it is kept, and comes back when turned on.",
                )
            ),
            components.spacer(10),
            self._title(translate("NotificationSettingsPanel", "System notices")),
            self.system,
            self._note(
                translate(
                    "NotificationSettingsPanel",
                    "Shows a notice of the system, which opens the app when clicked.",
                ),
                indent=True,
            ),
            self.window_on,
            hours,
            self._note(
                translate(
                    "NotificationSettingsPanel",
                    "Outside these hours the notifications are still kept in the "
                    "bell, but the system is not told. An end before the start "
                    "runs over midnight.",
                ),
                indent=True,
            ),
            components.spacer(10),
            self._title(translate("NotificationSettingsPanel", "Ignored objects")),
            self.ignored,
            self._note(
                translate(
                    "NotificationSettingsPanel",
                    "One per line, as Kind/name or context/Kind/name. * and ? "
                    "stand for any text. What matches is not kept nor told.",
                )
            ),
            None,
        )
        layout.setContentsMargins(0, 0, 0, 0)
        self.widget.setLayout(layout)
        self.window_on.toggled.connect(self._window_toggled)
        self.interval.setValue(DEFAULT)

    def _note(self, text: str, indent: bool = False) -> Any:
        """A line of explanation, quieter than what it explains; `indent` puts
        it under the text of a check box, not under its box."""
        label = self.components.label(text, "muted", wrap=True)
        if indent:
            label.setContentsMargins(26, 0, 0, 0)
        return label

    def _title(self, text: str) -> Any:
        """The title of a group of the section, like the one of the card."""
        return self.components.label(text.upper(), "cardTitle")

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
        self.components.set_time(self.start, self.settings.window_start)
        self.components.set_time(self.end, self.settings.window_end)
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
        self.settings.window_start = self.components.time_text(self.start)
        self.settings.window_end = self.components.time_text(self.end)
        self.settings.ignored = self.ignored.toPlainText().splitlines()
        self._apply()
        return True
