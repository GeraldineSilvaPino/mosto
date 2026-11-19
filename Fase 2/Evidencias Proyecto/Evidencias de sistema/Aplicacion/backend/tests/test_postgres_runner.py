"""A failed shutdown must never authorize deletion of the temporary cluster."""
from types import SimpleNamespace

from scripts import test_postgres as runner


def test_slow_checkpoint_is_observed_until_stopped(monkeypatch):
    statuses = iter([0, 0, 3])
    calls = []
    def run(*args):
        calls.append(args)
        return SimpleNamespace(returncode=next(statuses) if args[-1] == "status" else 0)
    monkeypatch.setattr(runner.time, "sleep", lambda _: None)
    assert runner.stop_temporary_cluster(run, "isolated-data")
    assert calls[0][-2:] == ("-W", "stop")
    assert len(calls) == 4


def test_unknown_status_or_deadline_preserves_cluster():
    assert not runner.stop_temporary_cluster(lambda *args: SimpleNamespace(returncode=4), "data")
    assert not runner.stop_temporary_cluster(lambda *args: SimpleNamespace(returncode=0), "data", timeout=0)
