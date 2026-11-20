from kubescope.notifications.reader import LONGEST_PAUSE, Backoff, read_all


class Reader:
    def __init__(self, contexts, failing=()):
        self.contexts = contexts
        self.failing = set(failing)
        self.asked: list[str] = []

    def list_contexts(self):
        return self.contexts

    def get_events(self, context, types=("Warning",)):
        self.asked.append(context)
        if context in self.failing:
            raise RuntimeError(f"{context} is not signed in")
        return [context]


def test_every_context_is_read_and_a_failure_is_the_reason_as_text() -> None:
    reader = Reader(["a", "b", "c"], failing={"b"})

    contexts, found = read_all(reader, set())  # type: ignore[arg-type]

    assert contexts == ["a", "b", "c"]
    assert found == {"a": ["a"], "b": "b is not signed in", "c": ["c"]}


def test_a_failure_without_a_message_is_named_by_its_kind() -> None:
    class Silent(Reader):
        def get_events(self, context, types=("Warning",)):
            raise TimeoutError()

    _contexts, found = read_all(Silent(["a"]), set())  # type: ignore[arg-type]

    assert found == {"a": "TimeoutError"}


def test_the_skipped_contexts_are_not_read_and_with_none_left_nothing_is() -> None:
    reader = Reader(["a", "b"])

    _contexts, found = read_all(reader, {"a"})  # type: ignore[arg-type]
    assert found == {"b": ["b"]} and reader.asked == ["b"]

    _contexts, found = read_all(reader, {"a", "b"})  # type: ignore[arg-type]
    assert found == {} and reader.asked == ["b"]


def test_a_context_that_keeps_failing_is_left_alone_for_longer_each_time() -> None:
    backoff = Backoff()
    skipped_rounds: list[int] = []

    for _ in range(3):  # fails, waits, fails again...
        backoff.failed("dead")
        waited = 0
        while "dead" in backoff.round():
            waited += 1
        skipped_rounds.append(waited)

    assert skipped_rounds == [1, 2, 4]


def test_the_pause_is_never_longer_than_the_longest() -> None:
    backoff = Backoff()
    for _ in range(40):
        backoff.failed("dead")

    waited = 0
    while "dead" in backoff.round():
        waited += 1

    assert waited == LONGEST_PAUSE


def test_a_context_that_works_again_or_left_the_kubeconfig_is_forgotten() -> None:
    backoff = Backoff()
    backoff.failed("a")
    backoff.failed("b")

    backoff.worked("a")
    backoff.forget(["a"])  # b is not in the kubeconfig any more

    assert backoff.round() == frozenset()
