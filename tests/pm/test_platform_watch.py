"""The live watch: platform facts reach Medai within seconds, through a held request."""

from __future__ import annotations

import pytest

from gazzali import platform_pull, platform_watch


@pytest.fixture
def wired(monkeypatch, tmp_path):
    """A watch whose held request and sync are both stand-ins; nothing touches the network."""
    calls = {"syncs": 0, "cursor": {"epoch": "e1", "seq": 3}, "errors": []}

    def _wait(cursor, *, wait_seconds):
        return dict(calls["cursor"])

    def _sync(db, *, apply):
        assert apply is True
        calls["syncs"] += 1
        report = platform_pull.SyncReport()
        report.errors = list(calls["errors"])
        return report

    monkeypatch.setattr(platform_pull, "wait_for_change", _wait)
    monkeypatch.setattr(platform_pull, "sync_delivery_facts", _sync)
    return calls, tmp_path / "pm.db"


def test_the_first_answer_always_syncs_to_catch_up(wired) -> None:
    calls, db = wired
    assert platform_watch.step(db, None) == {"epoch": "e1", "seq": 3}
    assert calls["syncs"] == 1


def test_a_quiet_answer_does_not_sync(wired) -> None:
    calls, db = wired
    platform_watch.step(db, {"epoch": "e1", "seq": 3})
    assert calls["syncs"] == 0


@pytest.mark.parametrize("cursor", [{"epoch": "e1", "seq": 2}, {"epoch": "e0", "seq": 3}])
def test_a_moved_cursor_or_a_restarted_platform_syncs(wired, cursor) -> None:
    calls, db = wired
    platform_watch.step(db, cursor)
    assert calls["syncs"] == 1


def test_a_failed_sync_does_not_advance_the_cursor(wired) -> None:
    """Raising keeps the old cursor in the loop, so the next held request answers at once and the
    sync is retried instead of forgotten."""
    calls, db = wired
    calls["errors"] = ["ds1: push failed"]
    with pytest.raises(RuntimeError, match="push failed"):
        platform_watch.step(db, {"epoch": "e1", "seq": 2})


def test_it_only_starts_when_configured_and_not_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("MEDAI_PLATFORM_CONTROL_URL", raising=False)
    assert platform_watch.start_platform_watch(tmp_path / "pm.db") is None
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_URL", "https://platform.example")
    monkeypatch.setenv("MEDAI_PLATFORM_CONTROL_TOKEN", "t")
    monkeypatch.setenv("MEDAI_PLATFORM_WATCH", "0")
    assert platform_watch.start_platform_watch(tmp_path / "pm.db") is None


def test_only_one_watcher_per_host(tmp_path) -> None:
    first = platform_watch._claim(tmp_path / "pm.db")
    assert first is not None
    try:
        assert platform_watch._claim(tmp_path / "pm.db") is None, "a second watcher started"
    finally:
        first.close()
    again = platform_watch._claim(tmp_path / "pm.db")
    assert again is not None, "the lock must be free once its holder is gone"
    again.close()


def test_the_loop_backs_off_to_a_minute_and_resets_after_a_success(monkeypatch, tmp_path) -> None:
    """A platform that is down — or an older build with no /v1/events (404) — is asked at most
    once a minute, never in a busy loop; the first success puts the pace back."""
    outcomes = [RuntimeError("down")] * 8 + [{"epoch": "e", "seq": 1}, RuntimeError("down")]
    slept: list[float] = []

    def fake_step(db, cursor):
        out = outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out

    monkeypatch.setattr(platform_watch, "step", fake_step)
    platform_watch.run_forever(tmp_path / "pm.db", sleep=slept.append, keep_going=lambda: bool(outcomes))
    assert slept == [1, 2, 4, 8, 16, 32, 60, 60, 1]


def test_the_watch_makes_its_own_lines_audible(monkeypatch, capfd) -> None:
    import logging

    for name in ("gazzali.platform_watch", "gazzali.platform_pull", "gazzali.platform_push"):
        log = logging.getLogger(name)
        # Restored after the test, so the handler, level and propagation set here never leak.
        monkeypatch.setattr(log, "handlers", [])
        monkeypatch.setattr(log, "propagate", log.propagate)
        monkeypatch.setattr(log, "level", log.level)
    monkeypatch.setattr(logging.root, "handlers", [])
    monkeypatch.setattr(logging.root, "level", logging.WARNING)
    platform_watch._make_audible()
    logging.getLogger("gazzali.platform_pull").info("1 sealed")
    assert "1 sealed" in capfd.readouterr().err


def test_a_failed_push_does_not_stall_the_watch(wired, monkeypatch) -> None:
    """Retrying the sync would never re-push (the row already matches); the */5 heartbeat does.
    So a push failure advances the cursor instead of turning the held request into a poll."""
    _calls, db = wired

    def _sync(db, *, apply):
        report = platform_pull.SyncReport()
        report.push_failed = ["ds1"]
        return report

    monkeypatch.setattr(platform_pull, "sync_delivery_facts", _sync)
    assert platform_watch.step(db, {"epoch": "e1", "seq": 2}) == {"epoch": "e1", "seq": 3}
