# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Notifications of KubeScope as an extension written against the SDK only: a bell in the top bar, beside the Settings, with the number of notifications not read; the Warning events of the context in use are read from time to time, kept in a cache on disk and listed, the newest first, in a panel that slides in from the right, with **Mark all as read** and **Clear**; the events are told apart as warnings and errors, and the time between two reads is chosen in **Settings → Notifications**; the errors, the warnings and the new versions that KubeScope itself tells about are listed with them; the panel is resized by dragging its left edge, and the width is kept by @danilogco

[Unreleased]: https://github.com/dcotecnologia/kubescope-notifications/commits/main
