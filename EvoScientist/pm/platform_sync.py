"""Freshness heartbeat for the desired-state mirror (DMZ -> cluster).

WHY THIS EXISTS. platform-control refuses to WIDEN access from a document
nobody has re-pushed inside PLATFORM_DESIRED_STALE_AFTER (24h at time of
writing) — a deliberate fail-closed property: never widen a grant nobody
pushed. Mutations push immediately, so nothing here delays a change. But a
document that simply STOPS changing goes stale, and then a correct, approved,
unrevoked grant quietly stops working. On 2026-08-26 that took a delivered
cohort away from the very project it was delivered for, five days after the
last governance change, with no error anywhere except the empty notebook.

This module is the pulse the consumer was always waiting for. It compares what
the cluster stores against what Medai holds, and pushes only what needs it:

  * cluster has NO document       -> push. The mutation push was lost.
  * cluster is BEHIND Medai       -> push. A mutation push failed; this is the
                                    retry that fire-and-forget pushes never
                                    had, and it is why the sweep runs often.
  * matches, but is AGEING        -> touch: re-push identical intent at the
                                    same generation. platform-control accepts
                                    that as a freshness stamp and leaves the
                                    generation alone (a bumped counter would
                                    mean "something changed", and nothing did).
  * matches and is fresh          -> nothing. Steady state is one GET.
  * cluster is AHEAD of Medai     -> loud warning, no write. Someone pushed
                                    from elsewhere, or this database was
                                    restored from a backup; guessing would
                                    overwrite the newer intent.

Only documents whose staleness would REMOVE access are refreshed. A dataset
that is expired or revoked loses nothing by going stale, because the guard
freezes expansion while revocations always apply.

Deliberately never raises: a failed sweep must not take the app down. Exit code
is 0 unless --strict is given.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from .db import get_db, get_db_path

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10

# Refresh a document once it is older than this. It MUST stay well under the
# cluster's staleness ceiling — the gap between the two is how long the DMZ can
# be unreachable before researchers start losing access.
_DEFAULT_REFRESH_AFTER = 3600

# Statuses whose document must keep proving itself. Anything else may go stale
# harmlessly: the guard only blocks WIDENING, never revocation.
_GRANTING_STATUSES = ("approved", "delivering", "sealed")


def _refresh_after() -> int:
    raw = os.environ.get("MEDAI_PLATFORM_REFRESH_AFTER_SECONDS", "")
    try:
        value = int(raw) if raw else _DEFAULT_REFRESH_AFTER
    except ValueError:
        logger.warning("MEDAI_PLATFORM_REFRESH_AFTER_SECONDS=%r is not an integer; using %d",
                       raw, _DEFAULT_REFRESH_AFTER)
        return _DEFAULT_REFRESH_AFTER
    return value if value > 0 else _DEFAULT_REFRESH_AFTER


def _endpoint() -> tuple[str, str] | None:
    base = os.environ.get("MEDAI_PLATFORM_CONTROL_URL", "").rstrip("/")
    token = os.environ.get("MEDAI_PLATFORM_CONTROL_TOKEN", "")
    return (base, token) if base and token else None


def _ssl_context() -> ssl.SSLContext | None:
    ca = os.environ.get("MEDAI_PLATFORM_CONTROL_CA", "")
    return ssl.create_default_context(cafile=ca) if ca else None


def _stored(path: str) -> dict | None:
    """GET one mirrored document. None means the cluster does not have it, and
    None is also what any transport failure returns — the caller then pushes,
    which is the safe direction: a redundant push costs one request."""
    ep = _endpoint()
    if ep is None:
        return None
    base, token = ep
    req = urllib.request.Request(base + path, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS, context=_ssl_context()) as resp:
            return json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            logger.warning("desired-state GET %s failed http=%s", path, exc.code)
        return None
    except Exception as exc:
        logger.warning("desired-state GET %s failed: %s", path, exc)
        return None


def _age_seconds(pushed_at: str | None) -> float | None:
    """Seconds since the cluster last stamped this document, or None if unknown."""
    if not pushed_at:
        return None
    try:
        stamp = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("unparseable pushed_at %r", pushed_at)
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return (datetime.now(UTC) - stamp).total_seconds()


def _decide(stored: dict | None, mine: int, refresh_after: int) -> tuple[str, str]:
    """(action, why) for one document. Pure, so the table of cases is testable."""
    if stored is None:
        return "push", "the cluster has no document"
    theirs = int(stored.get("generation") or 0)
    if theirs < mine:
        return "push", f"cluster is behind (stored {theirs}, Medai {mine})"
    if theirs > mine:
        return "skip-ahead", f"cluster is AHEAD (stored {theirs}, Medai {mine})"
    age = _age_seconds(stored.get("pushed_at"))
    if age is None:
        return "touch", "no readable pushed_at"
    if age > refresh_after:
        return "touch", f"stamped {int(age)}s ago, past the {refresh_after}s refresh window"
    return "fresh", f"stamped {int(age)}s ago"


def sync(db_path: Path, *, apply: bool = True) -> dict:
    """One pass. Returns a summary dict; never raises."""
    from .crud.researchers import researcher_generation
    from .platform_push import push_dataset, push_researcher

    refresh_after = _refresh_after()
    summary = {"pushed": 0, "touched": 0, "fresh": 0, "failed": 0, "ahead": 0,
               "refresh_after_seconds": refresh_after, "dry_run": not apply}

    if _endpoint() is None:
        logger.info("platform-control is not configured; nothing to sync")
        summary["disabled"] = True
        return summary

    with get_db(db_path) as conn:
        people = [r["email"] for r in conn.execute(
            """SELECT DISTINCT LOWER(u.email) AS email
                 FROM users u
                 JOIN project_members pm ON pm.user_id = u.id
                 JOIN projects p         ON p.id = pm.project_id
                WHERE u.email IS NOT NULL AND u.email <> '' AND p.archived_at IS NULL
                ORDER BY 1""").fetchall()]
        datasets = [(r["id"], r["generation"]) for r in conn.execute(
            f"""SELECT id, generation FROM datasets
                 WHERE status IN ({','.join('?' * len(_GRANTING_STATUSES))})
                 ORDER BY id""", _GRANTING_STATUSES).fetchall()]

    for email in people:
        mine = researcher_generation(db_path, email)
        stored = _stored("/v1/desired/researchers/" + quote(email, safe=""))
        action, why = _decide(stored, mine, refresh_after)
        _record(summary, "researcher", email, action, why, apply,
                lambda: push_researcher(db_path, email, bump=(action == "push")))

    for dataset_id, generation in datasets:
        stored = _stored("/v1/desired/datasets/" + quote(dataset_id, safe=""))
        action, why = _decide(stored, int(generation or 0), refresh_after)
        _record(summary, "dataset", dataset_id, action, why, apply,
                lambda: push_dataset(db_path, dataset_id))

    logger.info("desired-state sync: %s", json.dumps(summary))
    return summary


def _record(summary: dict, kind: str, name: str, action: str, why: str,
            apply: bool, do_push) -> None:
    """Apply one decision and count it. Never raises."""
    if action == "fresh":
        summary["fresh"] += 1
        return
    if action == "skip-ahead":
        summary["ahead"] += 1
        logger.warning("%s %s: %s — refusing to overwrite newer intent", kind, name, why)
        return
    logger.info("%s %s: %s -> %s%s", kind, name, why, action,
                " (dry run)" if not apply else "")
    if not apply:
        return
    try:
        ok = do_push()
    except Exception as exc:
        logger.warning("%s %s: push raised: %s", kind, name, exc)
        ok = False
    if ok:
        summary["pushed" if action == "push" else "touched"] += 1
    else:
        summary["failed"] += 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Keep the desired-state mirror fresh.")
    ap.add_argument("--apply", action="store_true", help="write; without it, report only")
    ap.add_argument("--strict", action="store_true", help="exit non-zero if anything failed")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    summary = sync(get_db_path(), apply=args.apply)
    print(json.dumps(summary))
    return 1 if (args.strict and summary.get("failed")) else 0


if __name__ == "__main__":
    sys.exit(main())
