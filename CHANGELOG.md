# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Notifications of KubeScope as an extension written against the SDK only: a bell in the top bar, beside the Settings, with the number of notifications not read; the Warning events of the context in use are read from time to time, kept in a cache on disk and listed, the newest first, in a panel that slides in from the right, with **Mark all as read** and **Clear**; the events are told apart as warnings and errors, and the time between two reads is chosen in **Settings → Notifications**; every context of the kubeconfig is read in the background (one that fails is left alone for longer each time), the cards name the context and a click on one opens that context, a context that cannot be read is listed with why, an alert is told apart by its object, reason and context, so it is not listed twice when Kubernetes makes its event again, and the system is told about the same alert once in 30 minutes, a new notification also shows a notice of the operating system, even with KubeScope in front, whose click opens the app, and the errors, the warnings and the new versions that KubeScope itself tells about are listed with them; the panel is resized by dragging its left edge, and the width is kept by @danilogco

[Unreleased]: https://github.com/dcotecnologia/kubescope-notifications/commits/main
