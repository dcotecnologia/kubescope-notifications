# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for a vulnerability. Use
[GitHub private vulnerability reporting](https://github.com/dcotecnologia/kubescope-notifications/security/advisories/new)
for this repository, or write to the maintainers listed in `pyproject.toml`. We acknowledge a report
within a few days, tell you what we found, and credit you in the release notes if you want.

## Supported versions

Only the latest release receives fixes.

## What it is

An extension is Python code that runs inside KubeScope with the same rights as the app. Its permissions
(`kubescope-extension.toml`) catch mistakes and tell you what it does; they are **not a sandbox**. Read
[the security notes of the SDK](https://github.com/dcotecnologia/kubescope-sdk/blob/main/docs/permissions.md)
before you install any extension.

## Guarantees this project keeps

- It asks for the least permissions it needs, and the README says why it asks for each one.
- It reads clusters and accounts only through the services the app lends it, and changes nothing outside the write mode.
- It never stores or logs credentials or secrets, and it makes no network request of its own beyond what the README says.
- Every release is a tag; KubeScope installs what it recommends only if the files are the ones whose hash it pinned.
- **What it keeps on disk is the text of Warning events.** The cache of the notifications (`notifications.json` in the data folder of the extension) holds the reason, the object, the namespace and the message of the events of the clusters you used, which can name objects of your cluster. The file is readable only by you, keeps at most 500 notifications, and **Clear** in the panel deletes them. No credentials are in it, and nothing in it is sent anywhere.
- **It reads every context of your kubeconfig in the background.** Each look at a context uses the credentials and sign-in programs of that context (for example `aws eks get-token`), the way the app does when you open it, four at a time and every 60 seconds by default; a context that fails is left alone for longer each time. It only reads events, and changes nothing in a cluster.
