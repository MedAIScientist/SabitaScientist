"""CRUD operations for grant budget items."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import GrantBudgetItem

CATEGORIES = ("personnel", "equipment", "consumables", "travel", "services", "other")

# Only these columns may be written by an update — the keys arrive from a request
# body, so they are whitelisted rather than interpolated straight into SQL.
_UPDATE_COLUMNS = (
    "category",
    "description",
    "planned_amount",
    "spent_amount",
    "position",
)


def _row_to_item(r) -> GrantBudgetItem:
    return GrantBudgetItem(
        id=r["id"],
        grant_id=r["grant_id"],
        category=r["category"],
        description=r["description"],
        planned_amount=r["planned_amount"],
        spent_amount=r["spent_amount"],
        position=r["position"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def create_budget_item(
    db_path: Path,
    grant_id: str,
    category: str = "other",
    description: str | None = None,
    planned_amount: float = 0.0,
    spent_amount: float = 0.0,
    position: int = 0,
) -> GrantBudgetItem:
    """Insert a budget line and return it."""
    item_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO grant_budget_items
               (id,grant_id,category,description,planned_amount,spent_amount,position,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                item_id,
                grant_id,
                category,
                description,
                planned_amount,
                spent_amount,
                position,
                now,
                now,
            ),
        )
    return GrantBudgetItem(
        id=item_id,
        grant_id=grant_id,
        category=category,
        description=description,
        planned_amount=planned_amount,
        spent_amount=spent_amount,
        position=position,
        created_at=now,
        updated_at=now,
    )


def list_budget_items(db_path: Path, grant_id: str) -> list[GrantBudgetItem]:
    """Return a grant's budget lines, in display order."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM grant_budget_items WHERE grant_id=? ORDER BY position, created_at",
            (grant_id,),
        ).fetchall()
    return [_row_to_item(r) for r in rows]


def get_budget_item(db_path: Path, item_id: str) -> GrantBudgetItem | None:
    with get_db(db_path) as conn:
        r = conn.execute(
            "SELECT * FROM grant_budget_items WHERE id=?", (item_id,)
        ).fetchone()
    return _row_to_item(r) if r else None


def update_budget_item(
    db_path: Path, item_id: str, fields: dict
) -> GrantBudgetItem | None:
    """Apply the given column changes; returns the row, or None if unknown.

    Only keys present in ``fields`` are written, so a caller can clear a nullable
    column by passing an explicit None.
    """
    updates = {k: v for k, v in fields.items() if k in _UPDATE_COLUMNS}
    if updates:
        now = datetime.now(UTC).isoformat()
        set_clause = ", ".join(f"{k}=?" for k in updates)
        with get_db(db_path) as conn:
            conn.execute(
                f"UPDATE grant_budget_items SET {set_clause}, updated_at=? WHERE id=?",
                [*updates.values(), now, item_id],
            )
    return get_budget_item(db_path, item_id)


def delete_budget_item(db_path: Path, item_id: str) -> bool:
    with get_db(db_path) as conn:
        return (
            conn.execute(
                "DELETE FROM grant_budget_items WHERE id=?", (item_id,)
            ).rowcount
            > 0
        )
