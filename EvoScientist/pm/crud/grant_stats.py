"""Aggregate reporting over the grants a caller is allowed to see."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from ..db import get_db
from ..models import Grant

# A grant is "decided" once the funder has answered. draft/submitted/under_review
# are still in flight, so counting them would drag the success rate toward zero.
_DECIDED_STATUSES = ("awarded", "active", "rejected", "closed")
_WON_STATUSES = ("awarded", "active")
_ENDS_SOON_DAYS = 90


def _today() -> date:
    return datetime.now(UTC).date()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _plan_counters(
    db_path: Path, grant_ids: list[str]
) -> tuple[int, int, float, float]:
    """Return (overdue milestones, open reports, planned budget, spent budget)."""
    if not grant_ids:
        return 0, 0, 0.0, 0.0
    placeholders = ",".join("?" * len(grant_ids))
    today = _today().isoformat()
    with get_db(db_path) as conn:
        row = conn.execute(
            f"""SELECT
                  SUM(CASE WHEN completed_at IS NULL AND due_date IS NOT NULL
                           AND due_date < ? THEN 1 ELSE 0 END) AS overdue,
                  SUM(CASE WHEN completed_at IS NULL AND kind = 'report'
                           THEN 1 ELSE 0 END) AS open_reports
                FROM grant_milestones WHERE grant_id IN ({placeholders})""",
            [today, *grant_ids],
        ).fetchone()
        budget = conn.execute(
            f"""SELECT COALESCE(SUM(planned_amount),0) AS planned,
                       COALESCE(SUM(spent_amount),0) AS spent
                FROM grant_budget_items WHERE grant_id IN ({placeholders})""",
            grant_ids,
        ).fetchone()
    return (
        int(row["overdue"] or 0),
        int(row["open_reports"] or 0),
        float(budget["planned"] or 0.0),
        float(budget["spent"] or 0.0),
    )


def summarize(db_path: Path, grants: list[Grant]) -> dict:
    """Return dashboard counters for the given (already visibility-filtered) grants."""
    by_status: dict[str, int] = {}
    totals: dict[str, dict[str, float]] = {}
    for g in grants:
        by_status[g.status] = by_status.get(g.status, 0) + 1
        currency = g.currency or "TRY"
        bucket = totals.setdefault(
            currency,
            {"currency": currency, "requested": 0.0, "awarded": 0.0, "count": 0},
        )
        bucket["requested"] += g.amount_requested or 0.0
        bucket["awarded"] += g.amount_awarded or 0.0
        bucket["count"] += 1

    decided = [g for g in grants if g.status in _DECIDED_STATUSES]
    won = [g for g in decided if g.status in _WON_STATUSES]

    horizon = _today() + timedelta(days=_ENDS_SOON_DAYS)
    today = _today()
    ending_soon = 0
    for g in grants:
        if g.status not in _WON_STATUSES:
            continue
        end = _parse_date(g.end_date)
        if end and today <= end <= horizon:
            ending_soon += 1

    overdue, open_reports, planned, spent = _plan_counters(
        db_path, [g.id for g in grants]
    )

    return {
        "total": len(grants),
        "by_status": by_status,
        "totals_by_currency": sorted(totals.values(), key=lambda b: b["currency"]),
        "decided": len(decided),
        "won": len(won),
        "success_rate": round(len(won) / len(decided), 4) if decided else None,
        "ending_soon": ending_soon,
        "overdue_milestones": overdue,
        "open_reports": open_reports,
        "budget_planned": planned,
        "budget_spent": spent,
    }
