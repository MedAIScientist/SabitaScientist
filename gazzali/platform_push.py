"""Push a dataset's desired grant state to platform-control (DMZ -> cluster).

The firewall is a one-way door: this host may call the cluster, the cluster can
never call back. So grants are PUSHED — Medai is the system of record, and on
every governance mutation it sends the full desired state for the affected
dataset, stamped with the row's monotonic ``generation``. platform-control
persists the highest generation it has seen and reconciles Garage + CVAT toward
it; a replayed or out-of-order push is rejected there (409), never applied.

Deliberately fire-and-forget: a push failure must NEVER fail the governance
write (the hourly reconcile and the next mutation both retry), so every error
path logs and returns False. With MEDAI_PLATFORM_CONTROL_URL unset the module
is a no-op — the same env-gated pattern as the CVAT doorbell.
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

from .db import get_db

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 5


def _active(grant) -> bool:
    return grant.admin_approved_at is not None and grant.revoked_at is None


def _lab_name(db_path: Path, lab_id: str | None) -> str:
    """The lab's human name, or "" when there is no lab or it has vanished."""
    if not lab_id:
        return ""
    from .crud.labs import get_lab

    lab = get_lab(db_path, lab_id)
    return (lab.name or "") if lab else ""


def _project_name(db_path: Path, project_id: str) -> str:
    """The project's human name, or "" when it has vanished."""
    from .crud.projects import get_project

    project = get_project(db_path, project_id)
    return (project.name or "") if project else ""


def build_desired_state(db_path: Path, dataset_id: str) -> dict | None:
    """The full desired-state document for one dataset, or None if it vanished."""
    from .crud.datasets import get_dataset, list_grants

    ds = get_dataset(db_path, dataset_id)
    if ds is None:
        return None
    grants = []
    for g in list_grants(db_path, dataset_id):
        if g.admin_approved_at is None and g.revoked_at is None:
            continue  # pending — not yet a grant anywhere outside Medai
        entry = {
            "project_id": g.project_id,
            "expires_at": g.expires_at or "",
            "revoked": not _active(g),
            # Display only. The deliverer's console showed "1 project" and a hex id where a
            # team name belonged, which told the person reading it nothing they could act on.
            "project_name": _project_name(db_path, g.project_id),
        }
        if g.cvat_project_id:
            entry["annotate"] = {
                "cvat_project_id": int(g.cvat_project_id),
                "task_size": int(g.task_size or 0),
            }
        grants.append(entry)
    return {
        "generation": ds.generation,
        "dataset": {
            "id": ds.id,
            "lab_id": ds.lab_id,
            "bucket": ds.bucket or "",
            "quota_bytes": ds.estimated_bytes or 0,
            "max_objects": 0,
            "retention_until": ds.retention_until or "",
            "status": ds.status,
            "renders": bool(ds.renders),
            # The human labels. Nothing downstream is addressed by them — they exist so a
            # console can say "Ankle radiographs 2019-2025 · Musculoskeletal Imaging"
            # instead of two 32-character hex strings.
            "name": ds.name or "",
            "lab_name": _lab_name(db_path, ds.lab_id),
            # The APPROVED cohort definition travels with the push, so the
            # in-cluster deliverer (Curator) pulls exactly what the two-human
            # chain approved — never whatever a caller typed into a request.
            "accessions": ds.accession_list or [],
        },
        "grants": grants,
    }


def push_dataset(db_path: Path, dataset_id: str) -> bool | None:
    """PUT the desired state; True on 2xx, False on any failure, None if disabled."""
    base = os.environ.get("MEDAI_PLATFORM_CONTROL_URL", "").rstrip("/")
    token = os.environ.get("MEDAI_PLATFORM_CONTROL_TOKEN", "")
    if not base or not token:
        return None
    doc = build_desired_state(db_path, dataset_id)
    if doc is None:
        return False
    req = urllib.request.Request(
        f"{base}/v1/desired/datasets/{dataset_id}",
        data=json.dumps(doc).encode(),
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    # The cluster gateway serves a certificate signed by the platform's INTERNAL CA
    # (sabita-internal-ca), which no system trust store carries. Pin it explicitly via
    # MEDAI_PLATFORM_CONTROL_CA (path to the CA pem) — pin the CA, never the 90-day leaf.
    ca = os.environ.get("MEDAI_PLATFORM_CONTROL_CA", "")
    ctx = ssl.create_default_context(cafile=ca) if ca else None
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS, context=ctx) as resp:
            logger.info(
                "platform push ok dataset=%s generation=%s http=%s",
                dataset_id,
                doc["generation"],
                resp.status,
            )
            return True
    except urllib.error.HTTPError as exc:
        # 409 = platform-control already holds a newer generation; harmless.
        level = logging.INFO if exc.code == 409 else logging.WARNING
        logger.log(
            level,
            "platform push refused dataset=%s generation=%s http=%s",
            dataset_id,
            doc["generation"],
            exc.code,
        )
        return False
    except Exception as exc:  # URLError, timeout, DNS — never fail the caller
        logger.warning("platform push failed dataset=%s: %s", dataset_id, exc)
        return False


# ── Researcher memberships: the last mile of the imaging path ────────────────────
#
# A delivered cohort and an approved grant put the pixels in a bucket the PROJECT
# can read. A person's notebook, though, holds a per-session key that by shape
# opens exactly one bucket — their own workspace — so without this push a
# researcher could not open the very dataset that was delivered for them.
#
# platform-control cannot look membership up: the firewall is a one-way door and
# Medai is the system of record. So the same push discipline datasets use applies
# here — the FULL current membership for one person, stamped with a monotonic
# generation, on every change. platform-control crosses it with the dataset
# documents (which already say which project may read which cohort) and grants
# the person's next session key read access accordingly.
#
# Removal needs no soft-delete: the document is the complete current set, so a
# hard DELETE from project_members simply produces a shorter list next push, and
# the session key that carried the old access expires on its own within a day.


def build_researcher_state(db_path: Path, email: str, *, bump: bool = True) -> dict | None:
    """The membership document for one person, or None if they have no address.

    Only ACTIVE, non-archived projects count. The generation comes from a
    per-person counter bumped inside this call, so two pushes can never claim
    the same generation and a delayed one is refused rather than applied.
    """
    from .crud.researchers import bump_researcher_generation, researcher_generation

    email = (email or "").strip().lower()
    if not email:
        return None
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT DISTINCT p.id
                 FROM projects p
                 JOIN project_members pm ON pm.project_id = p.id
                 JOIN users u           ON u.id = pm.user_id
                WHERE LOWER(u.email) = ? AND p.archived_at IS NULL
                ORDER BY p.id""",
            (email,),
        ).fetchall()
    # bump=False builds a FRESHNESS TOUCH: the same document at the same
    # generation, which platform-control accepts as proof the membership is
    # still live. Bumping for a heartbeat would make the counter say "something
    # changed" every hour, and then a real change could not be told from a
    # pulse. A person who has never been pushed still has to start at 1.
    generation = researcher_generation(db_path, email) if not bump else 0
    if not generation:
        generation = bump_researcher_generation(db_path, email)
    return {
        "generation": generation,
        "email": email,
        "projects": [r["id"] for r in rows],
    }


def push_researcher(db_path: Path, email: str, *, bump: bool = True) -> bool | None:
    """PUT one person's membership; True on 2xx, False on failure, None if off.

    bump=False re-sends the CURRENT generation — a freshness touch, used by the
    periodic sync to keep an unchanged membership inside the cluster's staleness
    window without pretending it changed.
    """
    base = os.environ.get("MEDAI_PLATFORM_CONTROL_URL", "").rstrip("/")
    token = os.environ.get("MEDAI_PLATFORM_CONTROL_TOKEN", "")
    if not base or not token:
        return None
    doc = build_researcher_state(db_path, email, bump=bump)
    if doc is None:
        return False
    req = urllib.request.Request(
        f"{base}/v1/desired/researchers/{quote(doc['email'], safe='')}",
        data=json.dumps(doc).encode(),
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    ca = os.environ.get("MEDAI_PLATFORM_CONTROL_CA", "")
    ctx = ssl.create_default_context(cafile=ca) if ca else None
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS, context=ctx) as resp:
            logger.info(
                "researcher push ok email=%s generation=%s projects=%d http=%s",
                doc["email"],
                doc["generation"],
                len(doc["projects"]),
                resp.status,
            )
            return True
    except urllib.error.HTTPError as exc:
        level = logging.INFO if exc.code == 409 else logging.WARNING
        logger.log(
            level,
            "researcher push refused email=%s generation=%s http=%s",
            doc["email"],
            doc["generation"],
            exc.code,
        )
        return False
    except Exception as exc:  # URLError, timeout, DNS — never fail the caller
        logger.warning("researcher push failed email=%s: %s", doc["email"], exc)
        return False


def push_researchers_for_user_id(db_path: Path, user_id: str) -> bool | None:
    """Push the membership of one user, looked up by id.

    The membership routes know a user id, not an address; a user with no email
    cannot be entitled to anything (the workspace ledger is keyed by address),
    which is a no-op rather than an error.
    """
    with get_db(db_path) as conn:
        row = conn.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or not row["email"]:
        return None
    return push_researcher(db_path, row["email"])


def push_all_researchers(db_path: Path) -> tuple[int, int]:
    """Re-push every member of every live project. Returns (pushed, failed).

    The safety net behind the per-change pushes: a push that was lost while
    platform-control was down would otherwise leave someone unable to open
    their data until their next membership change. A periodic sweep costs one
    small PUT per person and converges everything.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT DISTINCT LOWER(u.email) AS email
                 FROM users u
                 JOIN project_members pm ON pm.user_id = u.id
                 JOIN projects p         ON p.id = pm.project_id
                WHERE u.email IS NOT NULL AND u.email <> '' AND p.archived_at IS NULL
                ORDER BY 1""",
        ).fetchall()
    pushed = failed = 0
    for row in rows:
        if push_researcher(db_path, row["email"]):
            pushed += 1
        else:
            failed += 1
    logger.info("researcher sweep: %d pushed, %d failed", pushed, failed)
    return pushed, failed


def project_member_emails(db_path: Path, project_id: str) -> list[str]:
    """The addresses of a project's current members.

    Collected BEFORE a destructive change (archive, delete) so the members can
    still be re-pushed once their membership is gone — the row that says who to
    tell is the same row the change removes.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT DISTINCT LOWER(u.email) AS email
                 FROM users u
                 JOIN project_members pm ON pm.user_id = u.id
                WHERE pm.project_id = ? AND u.email IS NOT NULL AND u.email <> ''
                ORDER BY 1""",
            (project_id,),
        ).fetchall()
    return [r["email"] for r in rows]


def push_researchers(db_path: Path, emails: list[str]) -> None:
    """Push several memberships, one PUT each. Never raises."""
    for email in emails:
        try:
            push_researcher(db_path, email)
        except Exception as exc:  # a push must never fail a governance write
            logger.warning("researcher push raised for %s: %s", email, exc)


def ensure_project_space(db_path: Path, project_id: str) -> bool | None:
    """Provision a project's team bucket. True on 2xx, False on failure, None if off.

    Membership is only worth something if the bucket exists: the entitlement a
    session gets is a list of BUCKETS, and platform-control will not invent one
    for a project nobody provisioned. Before this call, project buckets appeared
    only as a side effect of a dataset grant, so a brand-new team had nowhere to
    put anything and every membership push warned that the project "has no
    bucket yet".

    A project's bucket is its shared workspace for renders, annotations and
    models — useful from the day the project exists, not only once imaging
    arrives.
    """
    base = os.environ.get("MEDAI_PLATFORM_CONTROL_URL", "").rstrip("/")
    token = os.environ.get("MEDAI_PLATFORM_CONTROL_TOKEN", "")
    if not base or not token:
        return None
    from .crud.projects import get_project

    project = get_project(db_path, project_id)
    if project is None:
        return False
    req = urllib.request.Request(
        f"{base}/v1/dataspaces/proj/{quote(project_id, safe='')}",
        data=json.dumps({"name": project.name}).encode(),
        method="PUT",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    ca = os.environ.get("MEDAI_PLATFORM_CONTROL_CA", "")
    ctx = ssl.create_default_context(cafile=ca) if ca else None
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS, context=ctx) as resp:
            logger.info("project space ensured project=%s http=%s", project_id, resp.status)
            return True
    except urllib.error.HTTPError as exc:
        logger.warning("project space refused project=%s http=%s", project_id, exc.code)
        return False
    except Exception as exc:  # never fail the governance write
        logger.warning("project space failed project=%s: %s", project_id, exc)
        return False


def ensure_all_project_spaces(db_path: Path) -> tuple[int, int]:
    """Provision the bucket of every live project. Returns (ensured, failed)."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id FROM projects WHERE archived_at IS NULL ORDER BY created_at"
        ).fetchall()
    ok = bad = 0
    for row in rows:
        if ensure_project_space(db_path, row["id"]):
            ok += 1
        else:
            bad += 1
    logger.info("project space sweep: %d ensured, %d failed", ok, bad)
    return ok, bad


# ── Announcements: the ONE pair of calls every membership change must make ────────
#
# These exist because hooking the HTTP routes was not enough. A project can also be
# created by the AI assistant's pm_create_project tool and by accepting an admission,
# both of which call the crud layer directly — so a project created that way got no
# bucket and its owner got no membership push, and their notebook could not open the
# cohort that had been granted to it. The hooks therefore live in crud, where every
# caller passes through, and these helpers are what crud calls.
#
# Both are fire-and-forget by contract: a governance write must never fail because the
# cluster was unreachable, and the periodic sweeps converge whatever was missed.


def announce_new_project(db_path: Path, project_id: str, owner_user_id: str) -> None:
    """Provision a new project's bucket, then push its owner's membership.

    In that order: a membership naming a bucket that does not exist yet entitles nothing.
    """
    try:
        ensure_project_space(db_path, project_id)
    except Exception as exc:
        logger.warning("project space announce raised project=%s: %s", project_id, exc)
    announce_membership_change(db_path, owner_user_id)


def announce_membership_change(db_path: Path, user_id: str) -> None:
    """Push one person's membership after it changed. Never raises."""
    try:
        push_researchers_for_user_id(db_path, user_id)
    except Exception as exc:
        logger.warning("membership announce raised user=%s: %s", user_id, exc)
