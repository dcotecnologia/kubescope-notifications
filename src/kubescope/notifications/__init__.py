"""Notifications for KubeScope: the Warning and Error events of the cluster,
cached and listed in a panel."""

from kubescope.sdk import Context


def activate(ctx: Context) -> None:
    """What the app calls to run the extension."""
    from kubescope.notifications import extension

    extension.activate(ctx)
