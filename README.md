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

- **Looks at every cluster for you.** Every context of your kubeconfig is read in the background, four at a time,
  every 60 seconds, the first look 30 seconds after the start (set in **Settings → Notifications**, from 15 seconds to an hour), and the Warning events are
  kept. A context that cannot be read, because it is not signed in or the cluster is away, keeps what it had and is
  left alone for a growing number of rounds (up to 30), so a few dead contexts do not run a sign-in command at every
  look.
- **Tells the operating system.** A new notification also shows a notice of the system, which brings KubeScope
  forward and opens the panel when you click it. Several new ones make one notice. It is not shown for what happened
  before the app started, or for the notice of a new version, which the app tells by itself; you can turn it off in **Settings → Notifications**. It needs a system tray; without the
  background mode the extension makes one only to carry the notice.
- **Warnings and errors.** Kubernetes has no level above Warning, so an event whose reason says that
  something failed (`BackOff`, `FailedScheduling`, `ImagePullBackOff`, `OOMKilling`, ...) is shown as an error
  and the others as warnings.
- **One notification for an alert that repeats.** An alert is a thing, a reason and a context: when Kubernetes makes the
  event again for the same pod and reason, or an error of the app comes back, it keeps the count and the time of the last
  time instead of a new line; and the operating system is told about the same alert once, not again for 30 minutes.
- **What the app itself tells.** The errors KubeScope shows in its banner, the warnings and errors of its message boxes and the notice of a **new version** of the app are listed too, with the same bell (an update is told once per version; an error that repeats counts instead of piling up).
- **Contexts that cannot be read are listed, except for a sign-in.** A context that cannot be read (the cluster is away, a
  timeout) gets one notification saying why, which goes away when it can be read again; clicking it opens that context.
  A failed sign-in (an expired SSO token, for example) is not listed: KubeScope already says it in its banner.
- **Click to go there.** A card names its context, and clicking it (or the notice of the system, when it is about one
  thing) switches KubeScope to that context and closes the panel; an error or a warning of the app goes back to the context that was in use when it happened, and only the notice of a new
  version has none.
- **Read and unread.** An unread card is highlighted; clicking a card reads it, and it is crossed out. **Mark all as read**
  reads them all. Opening the panel does not read anything, and an alert that happens again after you read it is unread
  again, unless it is the same error coming back within 30 minutes, which only counts. The red number on the bell is
  how many are unread.
- **A panel that slides in.** Click the bell: the list opens from the right, the newest first, with the object,
  the namespace, the message and how long ago. **Mark all as read** and **Clear** are in its header. What you clear does not come back with the next look at the cluster
  (Kubernetes keeps an event for about an hour): it returns only when it happens again, and a context that was not signed in
  is listed again only after it worked and failed again.
- **A panel you can resize.** Drag its left edge to make it wider or narrower (300 to 900 px, as far as the window allows); the width is kept.
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
