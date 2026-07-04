"""Audit logging — records user actions for security and accountability."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import AuditLogEntry


def log_action(
    db_path: Path,
    user_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: str | None = None,
    ip_address: str | None = None,
) -> AuditLogEntry:
    entry_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO audit_log (id, user_id, action, entity_type, entity_id, details, ip_address, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry_id, user_id, action, entity_type, entity_id, details, ip_address, now),
        )
    return AuditLogEntry(
        id=entry_id, user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        details=details, ip_address=ip_address, created_at=now,
    )


def list_logs(
    db_path: Path,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
) -> list[AuditLogEntry]:
    query = "SELECT * FROM audit_log WHERE 1=1"
    params: list = []
    if entity_type:
        query += " AND entity_type = ?"
        params.append(entity_type)
    if entity_id:
        query += " AND entity_id = ?"
        params.append(entity_id)
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        AuditLogEntry(
            id=r["id"], user_id=r["user_id"], action=r["action"],
            entity_type=r["entity_type"], entity_id=r["entity_id"],
            details=r["details"], ip_address=r["ip_address"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
