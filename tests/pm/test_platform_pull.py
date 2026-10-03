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
