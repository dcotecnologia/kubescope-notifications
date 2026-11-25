# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.2.0] - 2026-11-24

### Changed

- An alert that keeps happening (an autoscaler that fails every few seconds) is one notification: its count and its last time move on, it is neither unread again nor told again to the system, and it is a new one only when it comes back after an hour of quiet by @danilogco
- A notification shows how long ago it began, and the list is ordered by when each began by @danilogco
- A notification whose event is no longer in the cluster leaves the panel by @danilogco
- What the person cleared stays away while it keeps happening, and comes back only after an hour of quiet by @danilogco
- A click on a card only marks it as read: the panel and the context stay as they are by @danilogco

### Fixed

- A new notification of an event that began before the last time everything was marked as read was shown already read (crossed out and faded); a notification is new from when it is first told here by @danilogco

### Added

- The Settings of the extension choose the kinds of notification shown (errors, warnings, updates of the app): a kind that is off is not listed, counted nor told, and is kept by @danilogco
- Informative (Normal) events of the cluster can be turned on in the Settings, off by default because they are many; they are listed and counted but not told to the system by @danilogco
- Each notification has small buttons to mark it as read and to go to the context it came from by @danilogco
- The Settings choose, for each kind of notification, whether it is listed and whether the system is told: errors, warnings, informative events, confirmations of your actions, the state of a Pod after one, finished activities and updates of the app; what the app did is now kept in the bell by @danilogco
- The seconds between two looks at the cluster are any whole number from 15 to 3600, typed or stepped, not one of a fixed list by @danilogco
- The kinds of notification have a button to restore the defaults: only errors of the cluster, the state of a Pod after an action and the updates of the app are listed and told by @danilogco
- A click anywhere else of the window closes the panel by @danilogco

## [1.1.0] - 2026-11-24

### Added

- A time window for the notices of the system (outside it they are still kept in the bell) and a list of objects to ignore, as `Kind/name` or `context/Kind/name` with `*` and `?`, in the Settings of the extension by @danilogco

## [1.0.0] - 2026-11-21

### Added

- Notifications of KubeScope as an extension written against the SDK only: a bell in the top bar, beside the Settings, with the number of notifications not read; the Warning events of the context in use are read from time to time, kept in a cache on disk and listed, the newest first, in a panel that slides in from the right, with **Mark all as read** and **Clear**; the events are told apart as warnings and errors, and the time between two reads is chosen in **Settings → Notifications**; every context of the kubeconfig is read in the background (one that fails is left alone for longer each time), the cards name the context and a click on one opens that context, a context that cannot be read is listed with why, except when it is a failed sign-in, which the banner of the app already says, an alert is told apart by its object, reason and context, so it is not listed twice when Kubernetes makes its event again, and the system is told about the same alert once in 30 minutes, what you clear does not come back with the next look at the cluster, only when it happens again, unread ones are highlighted and the ones you read are crossed out (a click reads one), the same error coming back only counts instead of showing as news again, the first look comes 30 seconds after the start and no longer at every switch of context, and a new notification also shows a notice of the operating system, even with KubeScope in front, whose click opens the app, and the errors, the warnings and the new versions that KubeScope itself tells about are listed with them; the panel is resized by dragging its left edge, and the width is kept by @danilogco

[Unreleased]: https://github.com/dcotecnologia/kubescope-notifications/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/dcotecnologia/kubescope-notifications/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/dcotecnologia/kubescope-notifications/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/dcotecnologia/kubescope-notifications/releases/tag/v1.0.0
