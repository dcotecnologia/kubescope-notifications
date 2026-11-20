# KubeScope Notifications

[![CI](https://github.com/dcotecnologia/kubescope-notifications/actions/workflows/ci.yml/badge.svg)](https://github.com/dcotecnologia/kubescope-notifications/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fdcotecnologia%2Fkubescope-notifications%2Fbadges%2Fcoverage.json)](https://github.com/dcotecnologia/kubescope-notifications/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/dcotecnologia/kubescope-notifications)](https://github.com/dcotecnologia/kubescope-notifications/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.15](https://img.shields.io/badge/python-3.15-3776AB.svg?logo=python&logoColor=white)](pyproject.toml)
[![Qt for Python](https://img.shields.io/badge/Qt-PySide6-41CD52.svg?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython-6/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-D7FF64.svg?logo=ruff&logoColor=black)](https://docs.astral.sh/ruff/)
[![KubeScope extension](https://img.shields.io/badge/KubeScope-extension-326CE5.svg?logo=kubernetes&logoColor=white)](https://github.com/dcotecnologia/kubescope)

Notifications for [KubeScope](https://github.com/dcotecnologia/kubescope): a bell in the top bar that keeps the
**Warning and Error events** of your cluster and lists them, the newest first, in a panel that slides in from
the right.

It is an **extension** written against the [KubeScope SDK](https://github.com/dcotecnologia/kubescope-sdk)
and nothing else of the app. Install it in **Settings → Extensions**.

## What it does

- **Looks at the cluster for you.** While the selected context is signed in, it reads the events of every
  namespace every 60 seconds (set in **Settings → Notifications**, from 15 seconds to an hour) and keeps the
  Warning ones. A read that fails, because the context is not signed in, leaves what is kept as it is.
- **Warnings and errors.** Kubernetes has no level above Warning, so an event whose reason says that
  something failed (`BackOff`, `FailedScheduling`, `ImagePullBackOff`, `OOMKilling`, ...) is shown as an error
  and the others as warnings.
- **One notification for an event that repeats.** It keeps the count and the time of the last time, instead of
  a new line each time.
- **What the app itself tells.** The errors KubeScope shows in its banner, the warnings and errors of its message boxes and the notice of a **new version** of the app are listed too, with the same bell (an update is told once per version; an error that repeats counts instead of piling up).
- **A bell with a count.** The red number is what happened since you last opened the panel.
- **A panel that slides in.** Click the bell: the list opens from the right, the newest first, with the object,
  the namespace, the message and how long ago. **Mark all as read** and **Clear** are in its header.
- **A cache that survives a restart.** The notifications are kept on disk (at most 500), so they are there when
  you open the app.

## Requirements

KubeScope 2.2 or newer (the extension API `0`) and the SDK 1.3 or newer (the notices of the app need the event `notification`), which the app brings.

## Install

In **Settings → Extensions** either:

- **Install from GitHub...** and type `dcotecnologia/kubescope-notifications`, or
- **Install from a folder...** and pick the `kubescope-extension.toml` of a clone of this repository.

A dialog shows where it comes from, its permissions and the sha256 of its content before anything of it runs.

## Permissions

| Permission | Why |
| ---------- | --- |
| `cluster.read` | Read the events of the cluster of the selected context |
| `ui.window` | Put the bell in the top bar and draw the panel over the window |
| `ui.settings` | Its section of the Settings, for the time between two reads |

It only reads; it changes nothing in a cluster. See [SECURITY.md](SECURITY.md) for what it keeps on disk.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md). The extension is `src/kubescope/notifications`: `store.py` (the cache, no
Qt), `bell.py` and `panel.py` (the widgets) and `extension.py` (what the app calls).

## License

[MIT](LICENSE)
