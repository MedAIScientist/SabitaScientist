"""Pull delivery facts from platform-control back into Medai (DMZ -> cluster, GET only).

The firewall is a one-way door: this host may call the cluster, the cluster can never call
back. Every other flow in this system is therefore a PUSH — Medai is the system of record and
tells the cluster what it wants. This module closes the one loop that runs the other way.

"sealed" is not an opinion Medai holds about a cohort. It is a fact about the BUCKET: the
one-time ingest key has been retired and a seal receipt was written, by the cluster, at the
moment a delivery completed. Medai cannot be told that, so it has to ask — and until it does,
its own row keeps saying "approved", every later push walks the mirror backwards, and
"delivered and frozen" quietly becomes untrue.

DELIBERATELY NARROW. It moves delivery facts forward, and only forward:

    Medai approved|delivering  +  cluster sealed      ->  Medai sealed (+ seal time, content root)
    Medai approved             +  cluster delivering  ->  Medai delivering
    Medai sealed               +  cluster sealed      ->  fill a MISSING seal time / content root

and, for a mirror that fell behind:

    Medai sealed|delivering  +  cluster behind it  ->  re-push (no Medai write at all)

The seal time and content root are what platform-control observed AT the seal (the root read from
the deliverer's own manifest in the bucket); Medai, the system of record, used to hold neither.
They are filled in only where Medai has none — a value Medai already holds is never overwritten.

Nothing else is ever written. Expiry and revocation are governance decisions that belong to
Medai alone and are never touched here; a draft is never advanced; nothing ever moves
backwards; a dataset the cluster knows and Medai does not is reported, never created.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15

# The statuses this sync may move a dataset OUT of. Anything else — draft (not approved yet),
# sealed (already there), expired or revoked (governance decisions) — is left exactly alone.
_SEALABLE = ("approved", "delivering")

# What the cluster must say for the seal to be recorded.
_SEALED = "sealed"
_DELIVERING = "delivering"
_ROOT_RE = re.compile(r"[0-9a-f]{64}")


@dataclass
class SyncReport:
    """What one run saw and did. Printed for the cron log and asserted in tests."""

    checked: int = 0
    sealed: list[str] = field(default_factory=list)
    delivering: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    repushed: list[str] = field(default_factory=list)
    # Recorded (or already right) in Medai, but the push to the platform failed. Not an error
    # that stops the live watch: retrying the sync would never re-push (the row already matches),
    # and the */5 desired-sync re-pushes the current generation anyway.
    push_failed: list[str] = field(default_factory=list)
    unknown_to_medai: list[str] = field(default_factory=list)
    divergent: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def changed(self) -> int:
        return len(self.sealed) + len(self.delivering) + len(self.evidence) + len(self.repushed)

    def summary(self) -> str:
        parts = [
            f"checked={self.checked}",
            f"sealed={len(self.sealed)}",
            f"repushed={len(self.repushed)}",
        ]
        if self.delivering:
            parts.append(f"delivering={len(self.delivering)}")
        if self.evidence:
            parts.append(f"evidence={len(self.evidence)}")
        if self.unknown_to_medai:
            parts.append(f"unknown_to_medai={len(self.unknown_to_medai)}")
        if self.divergent:
            parts.append(f"divergent={len(self.divergent)}")
        if self.push_failed:
            parts.append(f"push_failed={len(self.push_failed)}")
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
    if medai_status == "approved" and cluster_status == _DELIVERING:
        return "deliver"
    if medai_status == _SEALED and cluster_status in _SEALABLE:
        return "repush"
    if medai_status == _DELIVERING and cluster_status == "approved":
        return "repush"
    return None


def _mirror_behind(medai_generation: int, cluster_generation: object) -> bool:
    """True only when the catalogue PROVES the mirror holds an older generation than Medai's; an
    absent or malformed value is unknown, and unknown keeps the safe old behaviour (bump)."""
    return (isinstance(cluster_generation, int) and not isinstance(cluster_generation, bool)
            and cluster_generation < medai_generation)


def _evidence_note(fill: dict) -> str:
    parts = []
    if "sealed_at" in fill:
        parts.append(f"sealed_at={fill['sealed_at']}")
    if "content_root_sha256" in fill:
        parts.append(f"content_root={fill['content_root_sha256'][:16]}…")
    return f" ({', '.join(parts)})" if parts else ""


def seal_evidence(desired: dict) -> tuple[str | None, str | None]:
    """(sealed_at, content_root) from the catalogue's `sealed` block, each None when absent or not
    well-formed. Validated here because they land in Medai's record verbatim."""
    facts = desired.get("sealed") if isinstance(desired.get("sealed"), dict) else {}
    at: str | None = None
    raw_at = facts.get("at")
    if isinstance(raw_at, str) and raw_at:
        try:
            at = datetime.fromisoformat(raw_at).isoformat()
        except ValueError:
            at = None
    root = facts.get("content_root_sha256")
    return at, root if isinstance(root, str) and _ROOT_RE.fullmatch(root) else None


def missing_evidence(row, at: str | None, root: str | None) -> dict:
    """The seal facts Medai does not hold yet — never one it holds (no overwrite, ever)."""
    out = {}
    if at and not row.sealed_at:
        out["sealed_at"] = at
    if root and not row.content_root_sha256:
        out["content_root_sha256"] = root
    return out


def _get_json(path: str, *, timeout: float = _TIMEOUT_SECONDS) -> dict:
    """GET one platform-control document. Read-only; raises on any failure."""
    base = os.environ.get("MEDAI_PLATFORM_CONTROL_URL", "").rstrip("/")
    token = os.environ.get("MEDAI_PLATFORM_CONTROL_TOKEN", "")
    if not base or not token:
        raise RuntimeError(
            "MEDAI_PLATFORM_CONTROL_URL/TOKEN are unset, so there is nothing to sync against"
        )
    req = urllib.request.Request(f"{base}{path}", headers={"Authorization": f"Bearer {token}"})
    # The gateway serves the platform's INTERNAL CA, which no system store carries. Pin the CA,
    # never the 90-day leaf — the same rule the push client follows.
    ca = os.environ.get("MEDAI_PLATFORM_CONTROL_CA", "")
    ctx = ssl.create_default_context(cafile=ca) if ca else None
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        doc = json.loads(resp.read() or b"{}")
    if not isinstance(doc, dict):
        raise RuntimeError(f"platform-control answered {path} with something that is not an object")
    return doc


def fetch_catalogue() -> list[dict]:
    """GET platform-control's dataset catalogue. Read-only; raises on any failure."""
    doc = _get_json("/v1/desired/datasets")
    entries = doc.get("datasets")
    if not isinstance(entries, list):
        raise RuntimeError("the catalogue answered no 'datasets' array")
    return entries


def bucket_usage(dataset_id: str) -> tuple[int, int] | None:
    """(objects, bytes) in the dataset's bucket per platform-control's catalogue, or None when the
    cluster lists no such dataset or no bucket for it yet. Raises when the catalogue cannot be read
    — or when it could not read THIS bucket: platform-control reports a failed lookup as
    `exists: false` plus `bucket_error`, which must never pass for "not created yet".

    Medai never learns that a delivery has started (nothing sets 'delivering'), so the bucket's
    own contents are the only evidence that something may be writing to it."""
    for entry in fetch_catalogue():
        spec = ((entry or {}).get("desired") or {}).get("dataset") or {}
        if str(spec.get("id") or "") == dataset_id:
            bucket = (entry or {}).get("bucket") or {}
            # On the ENTRY, not inside `bucket` (internal/tenancy/desired.go: BucketError).
            if (entry or {}).get("bucket_error"):
                raise RuntimeError(f"platform-control could not read the bucket: {entry['bucket_error']}")
            if not bucket.get("exists"):
                return None
            return int(bucket.get("objects") or 0), int(bucket.get("bytes") or 0)
    return None


def wait_for_change(cursor: dict | None, *, wait_seconds: int = 25) -> dict:
    """GET /v1/events: answered at once when `cursor` is behind (or from a restarted
    platform-control), otherwise when the next platform-side fact lands, otherwise after
    `wait_seconds` with the same cursor. Returns {"epoch": str, "seq": int}."""
    query = {"wait": str(wait_seconds)}
    if cursor:
        query |= {"epoch": str(cursor["epoch"]), "after": str(cursor["seq"])}
    doc = _get_json(f"/v1/events?{urllib.parse.urlencode(query)}", timeout=wait_seconds + 15)
    epoch, seq = doc.get("epoch"), doc.get("seq")
    if not isinstance(epoch, str) or not epoch or not isinstance(seq, int) or isinstance(seq, bool):
        raise RuntimeError(f"the events answer carried no usable cursor: {doc!r}")
    return {"epoch": epoch, "seq": seq}


@contextmanager
def sync_lock(db_path: Path) -> Iterator[None]:
    """One sync at a time across processes: the hourly cron and the live watcher may both run,
    and two of them sealing the same row would bump and push it twice for nothing."""
    with open(Path(db_path).parent / ".platform_sync.lock", "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def sync_delivery_facts(db_path: Path, *, apply: bool = False) -> SyncReport:
    """Reconcile the cluster's delivery facts into Medai. Writes only when apply is true."""
    from .crud.datasets import bump_generation, get_dataset, update_dataset_if_status
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

        at, root = seal_evidence(desired)
        if root and row.content_root_sha256 and row.content_root_sha256 != root:
            # Two records of the same cohort disagree about its content. Neither side is
            # rewritten; a person must look.
            report.divergent.append(f"{dataset_id}: content root medai={row.content_root_sha256[:12]}… "
                                    f"cluster={root[:12]}…")
            root = None
        action = decide_action(row.status, cluster_status)
        fill = missing_evidence(row, at, root)
        if action is None and row.status == _SEALED and cluster_status == _SEALED and fill:
            action = "evidence"
        if action is None:
            if row.status != cluster_status:
                report.divergent.append(f"{dataset_id}: medai={row.status} cluster={cluster_status}")
            continue

        label = f"{dataset_id} medai={row.status} cluster={cluster_status} -> {action}"
        bucket_for = {"seal": report.sealed, "deliver": report.delivering,
                      "evidence": report.evidence, "repush": report.repushed}[action]
        if not apply:
            logger.info("would %s", label)
            bucket_for.append(dataset_id)
            continue

        try:
            if action in ("seal", "deliver", "evidence"):
                # Record the fact — only if the row is still what was read, so a revoke that
                # landed meanwhile is never overwritten — then push so the mirror and Medai agree
                # on both the status and the generation.
                status = {"seal": _SEALED, "deliver": _DELIVERING}.get(action)
                # The system of record says who changed it — a row per write, in the same
                # transaction, like every other governance change in Medai.
                details = {"seal": f"sealed by the platform{_evidence_note(fill)}",
                           "deliver": "delivery started on the platform",
                           "evidence": f"seal evidence recorded{_evidence_note(fill)}"}[action]
                written = update_dataset_if_status(
                    db_path, dataset_id, row.status, status=status,
                    audit=(f"platform-{action}", details),
                    **(fill if action != "deliver" else {}))
                if written is None:
                    report.divergent.append(f"{dataset_id}: changed in Medai during the sync; left alone")
                    continue
            elif not _mirror_behind(row.generation, desired.get("generation")):
                # A re-push only needs a higher generation when the mirror is not already behind
                # Medai's; bumping on every retry would inflate the counter for nothing.
                bump_generation(db_path, dataset_id)
            if push_dataset(db_path, dataset_id) is False:
                # Medai's record is right; the mirror is behind until the next push (the */5
                # heartbeat re-pushes the current generation). Said, not swallowed.
                report.push_failed.append(dataset_id)
            bucket_for.append(dataset_id)
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
        with sync_lock(get_db_path()):
            report = sync_delivery_facts(get_db_path(), apply=apply)
    except Exception as exc:
        # A failure changes nothing: the catalogue read happens before any write, and the cron
        # wrapper keeps the non-zero exit visible in its log.
        print(f"platform status sync FAILED (nothing was changed): {exc}")
        return 1

    print(("applied " if apply else "dry-run ") + report.summary())
    for dataset_id in report.sealed:
        print(f"  sealed   {dataset_id}")
    for dataset_id in report.delivering:
        print(f"  delivering {dataset_id}")
    for dataset_id in report.evidence:
        print(f"  evidence {dataset_id}")
    for dataset_id in report.repushed:
        print(f"  repushed {dataset_id}")
    for note in report.divergent:
        print(f"  divergent (left alone) {note}")
    for dataset_id in report.unknown_to_medai:
        print(f"  unknown to medai (left alone) {dataset_id}")
    for dataset_id in report.push_failed:
        print(f"  PUSH FAILED {dataset_id} (Medai is right; the */5 desired-sync re-pushes it)")
    for err in report.errors:
        print(f"  ERROR {err}")
    return 1 if report.errors or report.push_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
