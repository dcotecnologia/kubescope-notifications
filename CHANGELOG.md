# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.0] - 2026-11-24

### Added

- A time window for the notices of the system (outside it they are still kept in the bell) and a list of objects to ignore, as `Kind/name` or `context/Kind/name` with `*` and `?`, in the Settings of the extension by @danilogco

## [1.0.0] - 2026-11-21

### Added

- Notifications of KubeScope as an extension written against the SDK only: a bell in the top bar, beside the Settings, with the number of notifications not read; the Warning events of the context in use are read from time to time, kept in a cache on disk and listed, the newest first, in a panel that slides in from the right, with **Mark all as read** and **Clear**; the events are told apart as warnings and errors, and the time between two reads is chosen in **Settings → Notifications**; every context of the kubeconfig is read in the background (one that fails is left alone for longer each time), the cards name the context and a click on one opens that context, a context that cannot be read is listed with why, except when it is a failed sign-in, which the banner of the app already says, an alert is told apart by its object, reason and context, so it is not listed twice when Kubernetes makes its event again, and the system is told about the same alert once in 30 minutes, what you clear does not come back with the next look at the cluster, only when it happens again, unread ones are highlighted and the ones you read are crossed out (a click reads one), the same error coming back only counts instead of showing as news again, the first look comes 30 seconds after the start and no longer at every switch of context, and a new notification also shows a notice of the operating system, even with KubeScope in front, whose click opens the app, and the errors, the warnings and the new versions that KubeScope itself tells about are listed with them; the panel is resized by dragging its left edge, and the width is kept by @danilogco

[Unreleased]: https://github.com/dcotecnologia/kubescope-notifications/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/dcotecnologia/kubescope-notifications/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/dcotecnologia/kubescope-notifications/releases/tag/v1.0.0
