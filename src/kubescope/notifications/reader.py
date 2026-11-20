"""Reading the events of every context of the kubeconfig, off the UI thread.

No Qt. A context that cannot be read (it is not signed in, the cluster is
away) is left alone for a growing number of rounds, so that a few dead contexts
do not spend a sign-in command at every look.
"""

from collections.abc import Collection
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from kubescope.sdk.models import ClusterEvent

WORKERS = 2  # contexts read at the same time; each may start a sign-in program
LONGEST_PAUSE = 30  # rounds a failing context is left alone, at most


class Reader(Protocol):
    def list_contexts(self) -> list[str]: ...

    def get_events(
        self, context: str, types: tuple[str, ...] = ...
    ) -> list[ClusterEvent]: ...


class Backoff:
    """Which contexts to skip in this round."""

    def __init__(self) -> None:
        self._failures: dict[str, int] = {}
        self._wait: dict[str, int] = {}

    def round(self) -> frozenset[str]:
        """Start a round; the contexts to leave out of it."""
        skipped = frozenset(name for name, left in self._wait.items() if left > 0)
        for name in skipped:
            self._wait[name] -= 1
        return skipped

    def failed(self, context: str) -> None:
        failures = self._failures.get(context, 0) + 1
        self._failures[context] = failures
        self._wait[context] = min(2 ** (failures - 1), LONGEST_PAUSE)

    def worked(self, context: str) -> None:
        self._failures.pop(context, None)
        self._wait.pop(context, None)

    def forget(self, keep: Collection[str]) -> None:
        """Drop what is known of the contexts that are not in the kubeconfig
        any more."""
        for name in [name for name in self._failures if name not in keep]:
            self.worked(name)


def read_all(
    reader: Reader, skip: Collection[str]
) -> tuple[list[str], dict[str, list[ClusterEvent] | str]]:
    """Every context of the kubeconfig, and the Warning events of each one
    that is not skipped; what could not be read is the reason, as text."""
    contexts = reader.list_contexts()
    due = [name for name in contexts if name not in skip]
    found: dict[str, list[ClusterEvent] | str] = {}
    if not due:
        return contexts, found
    with ThreadPoolExecutor(max_workers=min(WORKERS, len(due))) as pool:
        futures = {
            name: pool.submit(reader.get_events, name, ("Warning",)) for name in due
        }
        for name, future in futures.items():
            try:
                found[name] = future.result()
            except Exception as error:
                found[name] = str(error) or error.__class__.__name__
    return contexts, found
