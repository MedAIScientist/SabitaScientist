"""Pull delivery facts from platform-control back into Medai (DMZ -> cluster, GET only).

The firewall is a one-way door: this host may call the cluster, the cluster can never call
back. Every other flow in this system is therefore a PUSH — Medai is the system of record and
tells the cluster what it wants. This module closes the one loop that runs the other way.

"sealed" is not an opinion Medai holds about a cohort. It is a fact about the BUCKET: the
one-time ingest key has been retired and a seal receipt was written, by the cluster, at the
moment a delivery completed. Medai cannot be told that, so it has to ask — and until it does,
its own row keeps saying "approved", every later push walks the mirror backwards, and
"delivered and frozen" quietly becomes untrue.

DELIBERATELY NARROW. It moves one field in one direction:

    Medai approved|delivering  +  cluster sealed  ->  Medai sealed

and, for a mirror that fell behind before the cluster-side ratchet existed:

    Medai sealed  +  cluster approved|delivering  ->  re-push (no Medai write at all)

Nothing else is ever written. Expiry and revocation are governance decisions that belong to
Medai alone and are never touched here; a draft is never advanced; nothing ever moves
backwards; a dataset the cluster knows and Medai does not is reported, never created.
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15

# The statuses this sync may move a dataset OUT of. Anything else — draft (not approved yet),
# sealed (already there), expired or revoked (governance decisions) — is left exactly alone.
_SEALABLE = ("approved", "delivering")

# What the cluster must say for the seal to be recorded.
_SEALED = "sealed"


@dataclass
class SyncReport:
    """What one run saw and did. Printed for the cron log and asserted in tests."""

    checked: int = 0
    sealed: list[str] = field(default_factory=list)
    repushed: list[str] = field(default_factory=list)
    unknown_to_medai: list[str] = field(default_factory=list)
    divergent: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def changed(self) -> int:
        return len(self.sealed) + len(self.repushed)

    def summary(self) -> str:
        parts = [
            f"checked={self.checked}",
            f"sealed={len(self.sealed)}",
            f"repushed={len(self.repushed)}",
        ]
        if self.unknown_to_medai:
            parts.append(f"unknown_to_medai={len(self.unknown_to_medai)}")
        if self.divergent:
            parts.append(f"divergent={len(self.divergent)}")
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        return " ".join(parts)


def decide_action(medai_status: str, cluster_status: str) -> str | None:
    """The whole policy, as one pure function so it can be reasoned about and tested.

    Returns "seal" (record the delivery in Medai), "repush" (Medai is ahead; the mirror needs
    the fact), or None (nothing to do, or nothing this sync is allowed to touch).
    """
    if medai_status in _SEALABLE and cluster_status == _SEALED:
        return "seal"
    if medai_status == _SEALED and cluster_status in _SEALABLE:
        return "repush"
    return None


def fetch_catalogue() -> list[dict]:
    """GET platform-control's dataset catalogue. Read-only; raises on any failure."""
    base = os.environ.get("MEDAI_PLATFORM_CONTROL_URL", "").rstrip("/")
    token = os.environ.get("MEDAI_PLATFORM_CONTROL_TOKEN", "")
    if not base or not token:
        raise RuntimeError(
            "MEDAI_PLATFORM_CONTROL_URL/TOKEN are unset, so there is nothing to sync against"
        )
    req = urllib.request.Request(
        f"{base}/v1/desired/datasets",
        headers={"Authorization": f"Bearer {token}"},
    )
    # The gateway serves the platform's INTERNAL CA, which no system store carries. Pin the CA,
    # never the 90-day leaf — the same rule the push client follows.
    ca = os.environ.get("MEDAI_PLATFORM_CONTROL_CA", "")
    ctx = ssl.create_default_context(cafile=ca) if ca else None
    with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS, context=ctx) as resp:
        doc = json.loads(resp.read() or b"{}")
    entries = doc.get("datasets")
    if not isinstance(entries, list):
        raise RuntimeError("the catalogue answered no 'datasets' array")
    return entries


def sync_delivery_facts(db_path: Path, *, apply: bool = False) -> SyncReport:
    """Reconcile the cluster's delivery facts into Medai. Writes only when apply is true."""
    from .crud.datasets import bump_generation, get_dataset, update_dataset
    from .platform_push import push_dataset

    report = SyncReport()
    for entry in fetch_catalogue():
        desired = (entry or {}).get("desired") or {}
        spec = desired.get("dataset") or {}
        dataset_id = str(spec.get("id") or "")
        cluster_status = str(spec.get("status") or "")
        if not dataset_id:
            report.errors.append("a catalogue entry carried no dataset id")
            continue
        report.checked += 1

        row = get_dataset(db_path, dataset_id)
        if row is None:
            # The cluster holds documents Medai has never heard of — a throwaway test, or a
            # dataset deleted upstream. Reported so it is visible, never created: this sync is
            # not allowed to invent governance.
            report.unknown_to_medai.append(dataset_id)
            continue

        action = decide_action(row.status, cluster_status)
        if action is None:
            if row.status != cluster_status:
                report.divergent.append(f"{dataset_id}: medai={row.status} cluster={cluster_status}")
            continue

        label = f"{dataset_id} medai={row.status} cluster={cluster_status} -> {action}"
        if not apply:
            logger.info("would %s", label)
            (report.sealed if action == "seal" else report.repushed).append(dataset_id)
            continue

        try:
            if action == "seal":
                # Record the fact, then bump and push so the mirror and Medai agree on both
                # the status and the generation. Without the bump the push would 409.
                update_dataset(db_path, dataset_id, status=_SEALED)
                bump_generation(db_path, dataset_id)
                push_dataset(db_path, dataset_id)
                report.sealed.append(dataset_id)
            else:
                bump_generation(db_path, dataset_id)
                push_dataset(db_path, dataset_id)
                report.repushed.append(dataset_id)
            logger.info("%s: done", label)
        except Exception as exc:  # one bad dataset must not abort the rest
            report.errors.append(f"{dataset_id}: {exc}")
            logger.warning("%s: failed: %s", label, exc)
    return report


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: `python -m gazzali.platform_pull [--apply]`.

    Read-only by default, so a human (or a first cron run) can see what it would change.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    apply = "--apply" in args
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from .db import get_db_path

    try:
        report = sync_delivery_facts(get_db_path(), apply=apply)
    except Exception as exc:
        # A failure changes nothing: the catalogue read happens before any write, and the cron
        # wrapper keeps the non-zero exit visible in its log.
        print(f"platform status sync FAILED (nothing was changed): {exc}")
        return 1

    print(("applied " if apply else "dry-run ") + report.summary())
    for dataset_id in report.sealed:
        print(f"  sealed   {dataset_id}")
    for dataset_id in report.repushed:
        print(f"  repushed {dataset_id}")
    for note in report.divergent:
        print(f"  divergent (left alone) {note}")
    for dataset_id in report.unknown_to_medai:
        print(f"  unknown to medai (left alone) {dataset_id}")
    for err in report.errors:
        print(f"  ERROR {err}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
