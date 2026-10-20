"""The DMZ-side pull of delivery facts.

The one loop that runs cluster -> Medai, and the only one where the CLUSTER is the authority:
it alone knows that a delivery finished and the ingest key was retired. These tests pin the
policy down field by field, because a sync that writes one thing too many would be a governance
system quietly overwriting governance decisions.
"""

from __future__ import annotations

import json

import pytest

from gazzali import platform_pull
from gazzali.crud.datasets import create_dataset, get_dataset, update_dataset
from gazzali.crud.labs import create_lab
from gazzali.crud.users import create_user
from gazzali.auth import hash_password


# ── the policy, on its own ──────────────────────────────────────────────────


def test_the_policy_moves_exactly_one_field_one_way() -> None:
    # The case this exists for.
    assert platform_pull.decide_action("approved", "sealed") == "seal"
    assert platform_pull.decide_action("delivering", "sealed") == "seal"
    # Medai ahead of a stale mirror: push the fact, write nothing locally.
    assert platform_pull.decide_action("sealed", "approved") == "repush"
    assert platform_pull.decide_action("sealed", "delivering") == "repush"
    # Already agreed.
    assert platform_pull.decide_action("sealed", "sealed") is None
    assert platform_pull.decide_action("approved", "approved") is None


def test_the_policy_never_touches_a_governance_decision() -> None:
    # Expiry and revocation belong to Medai. A cluster document must never be able to
    # resurrect, retire, or reinterpret one.
    for medai in ("expired", "revoked"):
        for cluster in ("approved", "delivering", "sealed", "expired", "revoked", "draft"):
            assert platform_pull.decide_action(medai, cluster) is None, (medai, cluster)
    # And a cluster that claims a terminal state never moves Medai there.
    for cluster in ("expired", "revoked"):
        for medai in ("approved", "delivering", "sealed"):
            assert platform_pull.decide_action(medai, cluster) is None, (medai, cluster)


def test_the_policy_never_advances_a_draft() -> None:
    # A draft has not passed the two-human chain. No delivery fact can approve it.
    for cluster in ("approved", "delivering", "sealed", "expired", "revoked"):
        assert platform_pull.decide_action("draft", cluster) is None, cluster


def test_the_policy_ignores_statuses_it_does_not_understand() -> None:
    assert platform_pull.decide_action("approved", "") is None
    assert platform_pull.decide_action("", "sealed") is None
    assert platform_pull.decide_action("teleported", "sealed") is None


# ── the sync, against a fake catalogue ──────────────────────────────────────


@pytest.fixture
def catalogue(monkeypatch):
    """Replace the HTTP read with a list a test controls. Nothing touches the network."""
    entries: list[dict] = []

    def _fetch():
        return entries

    monkeypatch.setattr(platform_pull, "fetch_catalogue", _fetch)
    return entries


@pytest.fixture
def pushes(monkeypatch):
    """Capture the pushes the sync makes, without a network call."""
    sent: list[str] = []
    monkeypatch.setattr("gazzali.platform_push.push_dataset",
                        lambda db, dataset_id: sent.append(dataset_id) or True)
    return sent


def _entry(dataset_id: str, status: str) -> dict:
    return {"desired": {"dataset": {"id": dataset_id, "status": status}}}


def _dataset(tmp_db, status: str = "approved"):
    owner = create_user(tmp_db, username="pi", password_hash=hash_password("p"), email="pi@x.co")
    lab = create_lab(tmp_db, name="Lab", pi_id=owner.id)
    ds = create_dataset(tmp_db, name="Cohort", purpose="p", lab_id=lab.id,
                        requested_by=owner.id, accession_list=["ACC1"])
    update_dataset(tmp_db, ds.id, status=status, retention_until="2027-12-31")
    return get_dataset(tmp_db, ds.id)


def test_a_delivered_cohort_is_recorded_in_medai(tmp_db, catalogue, pushes) -> None:
    ds = _dataset(tmp_db, "approved")
    catalogue.append(_entry(ds.id, "sealed"))

    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert report.sealed == [ds.id]
    assert get_dataset(tmp_db, ds.id).status == "sealed"
    # The generation moved and the fact was pushed, so the mirror and Medai agree.
    assert get_dataset(tmp_db, ds.id).generation > ds.generation
    assert pushes == [ds.id]


def test_a_dry_run_changes_nothing(tmp_db, catalogue, pushes) -> None:
    ds = _dataset(tmp_db, "approved")
    catalogue.append(_entry(ds.id, "sealed"))

    report = platform_pull.sync_delivery_facts(tmp_db, apply=False)
    assert report.sealed == [ds.id]          # it says what it would do...
    assert get_dataset(tmp_db, ds.id).status == "approved"   # ...and does none of it
    assert pushes == []


def test_a_stale_mirror_is_repushed_without_writing_to_medai(tmp_db, catalogue, pushes) -> None:
    ds = _dataset(tmp_db, "sealed")
    catalogue.append(_entry(ds.id, "approved"))

    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert report.repushed == [ds.id] and report.sealed == []
    after = get_dataset(tmp_db, ds.id)
    assert after.status == "sealed"           # unchanged
    assert after.generation > ds.generation   # bumped so the push is accepted
    assert pushes == [ds.id]


def test_a_dataset_the_cluster_knows_and_medai_does_not_is_reported_never_created(
    tmp_db, catalogue, pushes
) -> None:
    catalogue.append(_entry("f" * 32, "sealed"))
    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert report.unknown_to_medai == ["f" * 32]
    assert report.changed == 0 and pushes == []
    assert get_dataset(tmp_db, "f" * 32) is None


def test_a_governance_decision_is_left_alone_and_reported(tmp_db, catalogue, pushes) -> None:
    ds = _dataset(tmp_db, "revoked")
    catalogue.append(_entry(ds.id, "sealed"))

    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert report.changed == 0 and pushes == []
    assert get_dataset(tmp_db, ds.id).status == "revoked"
    # Silence would be wrong: the divergence is real and a human should see it.
    assert any(ds.id in note for note in report.divergent)


def test_one_bad_dataset_does_not_abort_the_rest(tmp_db, catalogue, monkeypatch) -> None:
    first = _dataset(tmp_db, "approved")
    owner = create_user(tmp_db, username="pi2", password_hash=hash_password("p"), email="pi2@x.co")
    lab = create_lab(tmp_db, name="Lab2", pi_id=owner.id)
    second = create_dataset(tmp_db, name="Second", purpose="p", lab_id=lab.id,
                            requested_by=owner.id, accession_list=["ACC2"])
    update_dataset(tmp_db, second.id, status="approved", retention_until="2027-12-31")
    catalogue.extend([_entry(first.id, "sealed"), _entry(second.id, "sealed")])

    calls: list[str] = []

    def _explode(db, dataset_id):
        calls.append(dataset_id)
        if dataset_id == first.id:
            raise RuntimeError("the cluster hung up")
        return True

    monkeypatch.setattr("gazzali.platform_push.push_dataset", _explode)
    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert len(calls) == 2                       # both were attempted
    assert report.sealed == [second.id]
    assert any(first.id in e for e in report.errors)


def test_an_entry_with_no_id_is_an_error_not_a_crash(tmp_db, catalogue) -> None:
    catalogue.append({"desired": {"dataset": {"status": "sealed"}}})
    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert report.errors and report.checked == 0


def test_an_unreadable_catalogue_changes_nothing(tmp_db, monkeypatch) -> None:
    ds = _dataset(tmp_db, "approved")

    def _boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(platform_pull, "fetch_catalogue", _boom)
    with pytest.raises(RuntimeError):
        platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert get_dataset(tmp_db, ds.id).status == "approved"


def test_the_cli_reports_failure_without_raising(tmp_db, monkeypatch, capsys) -> None:
    def _boom():
        raise RuntimeError("connection refused")

    monkeypatch.setattr(platform_pull, "fetch_catalogue", _boom)
    assert platform_pull.main(["--apply"]) == 1
    out = capsys.readouterr().out
    assert "FAILED" in out and "nothing was changed" in out


def test_the_cli_defaults_to_dry_run(tmp_db, catalogue, pushes, capsys) -> None:
    ds = _dataset(tmp_db, "approved")
    catalogue.append(_entry(ds.id, "sealed"))

    assert platform_pull.main([]) == 0
    assert "dry-run" in capsys.readouterr().out
    assert get_dataset(tmp_db, ds.id).status == "approved"


def test_fetch_catalogue_refuses_to_run_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("MEDAI_PLATFORM_CONTROL_URL", raising=False)
    monkeypatch.delenv("MEDAI_PLATFORM_CONTROL_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="unset"):
        platform_pull.fetch_catalogue()


# ── seal evidence, delivery start, and the event cursor (2026-10-17) ─────────
#
# Two cohorts sealed at 14:44-14:45Z were recorded in Medai at 15:17Z by the hourly pull, without
# their seal time or content root. These pin what the pull now carries, and that it carries it
# forward only: a value Medai already holds is never overwritten.

ROOT = "5f1c0a3c8e2b4d6f8a0b2c4d6e8f0a1b3c5d7e9f1a2b4c6d8e0f2a4b6c8d0e2f"


def _sealed_entry(dataset_id: str, *, at="2026-10-17T14:45:39Z", root=ROOT) -> dict:
    entry = _entry(dataset_id, "sealed")
    entry["desired"]["sealed"] = {"at": at, "content_root_sha256": root, "objects": 63,
                                  "bytes": 334742670}
    return entry


def test_the_policy_records_a_delivery_that_has_started() -> None:
    assert platform_pull.decide_action("approved", "delivering") == "deliver"
    assert platform_pull.decide_action("delivering", "approved") == "repush"
    assert platform_pull.decide_action("delivering", "delivering") is None
    assert platform_pull.decide_action("draft", "delivering") is None


def test_a_seal_arrives_with_its_time_and_content_root(tmp_db, catalogue, pushes) -> None:
    ds = _dataset(tmp_db, "delivering")
    catalogue.append(_sealed_entry(ds.id))
    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    after = get_dataset(tmp_db, ds.id)
    assert report.sealed == [ds.id]
    assert after.status == "sealed"
    assert after.sealed_at == "2026-10-17T14:45:39+00:00"
    assert after.content_root_sha256 == ROOT
    assert pushes == [ds.id]


def test_a_delivery_starting_is_recorded_and_pushed(tmp_db, catalogue, pushes) -> None:
    ds = _dataset(tmp_db, "approved")
    catalogue.append(_entry(ds.id, "delivering"))
    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert report.delivering == [ds.id]
    assert get_dataset(tmp_db, ds.id).status == "delivering"
    assert pushes == [ds.id]


def test_an_old_seal_gets_its_missing_evidence_and_nothing_else(tmp_db, catalogue, pushes) -> None:
    ds = _dataset(tmp_db, "sealed")
    catalogue.append(_sealed_entry(ds.id))
    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    after = get_dataset(tmp_db, ds.id)
    assert report.evidence == [ds.id]
    assert report.sealed == []
    assert (after.status, after.sealed_at, after.content_root_sha256) == (
        "sealed", "2026-10-17T14:45:39+00:00", ROOT)
    # Run again: nothing is missing any more, so nothing happens.
    pushes.clear()
    assert platform_pull.sync_delivery_facts(tmp_db, apply=True).changed == 0
    assert pushes == []


def test_evidence_medai_holds_is_never_overwritten(tmp_db, catalogue, pushes) -> None:
    ds = _dataset(tmp_db, "sealed")
    update_dataset(tmp_db, ds.id, sealed_at="2026-10-17T14:45:00+00:00")
    catalogue.append(_sealed_entry(ds.id))
    platform_pull.sync_delivery_facts(tmp_db, apply=True)
    after = get_dataset(tmp_db, ds.id)
    assert after.sealed_at == "2026-10-17T14:45:00+00:00", "a held value moved"
    assert after.content_root_sha256 == ROOT, "only the missing field is filled"


def test_two_records_of_one_cohort_that_disagree_are_reported_not_rewritten(
        tmp_db, catalogue, pushes) -> None:
    ds = _dataset(tmp_db, "sealed")
    update_dataset(tmp_db, ds.id, content_root_sha256="a" * 64)
    catalogue.append(_sealed_entry(ds.id))
    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert get_dataset(tmp_db, ds.id).content_root_sha256 == "a" * 64
    assert any("content root" in d for d in report.divergent)


@pytest.mark.parametrize(("at", "root"), [("yesterday", ROOT), ("2026-10-17T14:45:39Z", "not-hex"),
                                          ("", ""), (None, None)])
def test_malformed_seal_evidence_is_not_recorded(tmp_db, catalogue, pushes, at, root) -> None:
    ds = _dataset(tmp_db, "approved")
    catalogue.append(_sealed_entry(ds.id, at=at, root=root))
    platform_pull.sync_delivery_facts(tmp_db, apply=True)
    after = get_dataset(tmp_db, ds.id)
    assert after.status == "sealed", "the seal itself is still a fact"
    good_at = at == "2026-10-17T14:45:39Z"
    assert (after.sealed_at is not None) == good_at
    assert (after.content_root_sha256 is not None) == (root == ROOT)


def test_the_event_cursor_is_asked_for_correctly_and_checked(monkeypatch) -> None:
    asked: list[tuple[str, float]] = []

    def _get(path, *, timeout):
        asked.append((path, timeout))
        return {"epoch": "e1", "seq": 7}

    monkeypatch.setattr(platform_pull, "_get_json", _get)
    assert platform_pull.wait_for_change(None, wait_seconds=25) == {"epoch": "e1", "seq": 7}
    assert platform_pull.wait_for_change({"epoch": "e1", "seq": 6}, wait_seconds=25)["seq"] == 7
    assert asked[0] == ("/v1/events?wait=25", 40)
    assert asked[1][0] == "/v1/events?wait=25&epoch=e1&after=6"
    for bad in ({}, {"epoch": "", "seq": 1}, {"epoch": "e", "seq": "1"}, {"epoch": "e", "seq": True}):
        monkeypatch.setattr(platform_pull, "_get_json", lambda path, *, timeout, b=bad: b)
        with pytest.raises(RuntimeError):
            platform_pull.wait_for_change(None)


# ── review findings (2026-10-17) ─────────────────────────────────────────────


def test_a_revoke_landing_mid_sync_is_never_overwritten(tmp_db, catalogue, monkeypatch) -> None:
    """The sync decides from a read and writes afterwards. A revoke committed in between must win:
    the write is conditional on the status that was read, so nothing is written or pushed."""
    ds = _dataset(tmp_db, "approved")
    catalogue.append(_entry(ds.id, "delivering"))
    pushed: list[str] = []
    monkeypatch.setattr("gazzali.platform_push.push_dataset",
                        lambda db, i: pushed.append(get_dataset(db, i).status) or True)
    real = platform_pull.decide_action

    def racing(medai, cluster):
        update_dataset(tmp_db, ds.id, status="revoked")   # the admin's revoke commits here
        return real(medai, cluster)

    monkeypatch.setattr(platform_pull, "decide_action", racing)
    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert get_dataset(tmp_db, ds.id).status == "revoked"
    assert pushed == []
    assert any("changed in Medai during the sync" in d for d in report.divergent)


def test_every_write_the_sync_makes_leaves_an_audit_row(tmp_db, catalogue, pushes) -> None:
    from gazzali.crud.audit import list_logs

    ds = _dataset(tmp_db, "approved")
    catalogue.append(_sealed_entry(ds.id))
    platform_pull.sync_delivery_facts(tmp_db, apply=True)
    rows = list_logs(tmp_db, entity_type="dataset", entity_id=ds.id)
    sealed = [r for r in rows if r.action == "platform-seal"]
    assert len(sealed) == 1
    assert "sealed_at=2026-10-17T14:45:39+00:00" in (sealed[0].details or "")
    assert sealed[0].user_id is None, "the platform, not a person, made this change"


def test_a_failed_push_is_reported_not_swallowed(tmp_db, catalogue, monkeypatch) -> None:
    ds = _dataset(tmp_db, "approved")
    catalogue.append(_sealed_entry(ds.id))
    monkeypatch.setattr("gazzali.platform_push.push_dataset", lambda db, i: False)
    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert get_dataset(tmp_db, ds.id).status == "sealed", "Medai's record is still right"
    assert report.push_failed == [ds.id]
    assert report.errors == [], "a push the */5 heartbeat repeats must not stall the live watch"


def test_a_repush_bumps_the_generation_only_when_the_mirror_is_not_behind(
        tmp_db, catalogue, pushes) -> None:
    """A push the platform keeps refusing must not inflate the generation on every retry."""
    ds = _dataset(tmp_db, "sealed")
    behind = _entry(ds.id, "delivering")
    behind["desired"]["generation"] = ds.generation - 1     # the mirror is already behind Medai
    catalogue.append(behind)
    platform_pull.sync_delivery_facts(tmp_db, apply=True)
    platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert get_dataset(tmp_db, ds.id).generation == ds.generation, "bumped although already ahead"
    assert pushes == [ds.id, ds.id]

    catalogue[0]["desired"]["generation"] = ds.generation   # level: the push needs a higher one
    platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert get_dataset(tmp_db, ds.id).generation == ds.generation + 1


def test_a_status_change_never_lands_without_its_audit_row(tmp_db, catalogue, pushes) -> None:
    """One transaction: when the audit row cannot be written, the change is not written either,
    and the next sync tries both again."""
    from gazzali.db import get_db

    ds = _dataset(tmp_db, "approved")
    catalogue.append(_sealed_entry(ds.id))
    with get_db(tmp_db) as conn:
        conn.execute("ALTER TABLE audit_log RENAME TO audit_log_away")
    report = platform_pull.sync_delivery_facts(tmp_db, apply=True)
    assert get_dataset(tmp_db, ds.id).status == "approved", "the change landed without its audit row"
    assert report.errors
    assert pushes == []
    with get_db(tmp_db) as conn:
        conn.execute("ALTER TABLE audit_log_away RENAME TO audit_log")
    assert platform_pull.sync_delivery_facts(tmp_db, apply=True).sealed == [ds.id]
