"""Soft delete helper — adds deleted_at to queries instead of hard DELETE."""

from __future__ import annotations

from datetime import UTC, datetime


def soft_delete_field() -> str:
    """Returns the SQL set clause for soft-deleting."""
    now = datetime.now(UTC).isoformat()
    return f"deleted_at = '{now}'"


def active_where() -> str:
    """Returns WHERE clause to exclude soft-deleted rows."""
    return "deleted_at IS NULL"
