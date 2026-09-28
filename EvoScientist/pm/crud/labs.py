from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Lab, LabMember


def create_lab(
    db_path: Path,
    name: str,
    pi_id: str | None = None,
    department: str = "",
    university: str = "",
) -> Lab:
    lab_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO labs (id, name, pi_id, department, university, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (lab_id, name, pi_id, department, university, now, now),
        )
    return Lab(
        id=lab_id,
        name=name,
        pi_id=pi_id,
        department=department,
        university=university,
        created_at=now,
        updated_at=now,
    )


def get_lab(db_path: Path, lab_id: str) -> Lab | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id, name, pi_id, department, university, created_at, updated_at FROM labs WHERE id = ?",
            (lab_id,),
        ).fetchone()
    return _row_to_lab(row) if row else None


def list_labs(db_path: Path) -> list[Lab]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, name, pi_id, department, university, created_at, updated_at FROM labs ORDER BY created_at DESC",
        ).fetchall()
    return [_row_to_lab(r) for r in rows]


def list_labs_for_user(db_path: Path, user_id: str) -> list[Lab]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT l.id, l.name, l.pi_id, l.department, l.university, l.created_at, l.updated_at
               FROM labs l
               JOIN lab_members lm ON l.id = lm.lab_id
               WHERE lm.user_id = ? AND lm.ended_at IS NULL
               ORDER BY l.created_at DESC""",
            (user_id,),
        ).fetchall()
    return [_row_to_lab(r) for r in rows]


def list_labs_where_pi(db_path: Path, user_id: str) -> list[Lab]:
    """Labs the user leads: either labs.pi_id points at them, or they hold a
    'pi'/'admin' row in lab_members.

    Both sources are needed because labs created before POST /labs started
    setting labs.pi_id still have pi_id NULL while their real PI only has the
    lab_members 'pi' row.
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT DISTINCT l.id, l.name, l.pi_id, l.department, l.university, l.created_at, l.updated_at
               FROM labs l
               LEFT JOIN lab_members lm ON l.id = lm.lab_id AND lm.user_id = ?
               WHERE l.pi_id = ? OR lm.role IN ('pi', 'admin')
               ORDER BY l.created_at DESC""",
            (user_id, user_id),
        ).fetchall()
    return [_row_to_lab(r) for r in rows]


def update_lab(
    db_path: Path,
    lab_id: str,
    name: str | None = None,
    pi_id: str | None = None,
    department: str | None = None,
    university: str | None = None,
) -> Lab:
    lab = get_lab(db_path, lab_id)
    if lab is None:
        raise ValueError(f"Lab {lab_id!r} not found")
    now = datetime.now(UTC).isoformat()
    new_name = name if name is not None else lab.name
    new_pi = pi_id if pi_id is not None else lab.pi_id
    new_dept = department if department is not None else lab.department
    new_uni = university if university is not None else lab.university
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE labs SET name = ?, pi_id = ?, department = ?, university = ?, updated_at = ? WHERE id = ?",
            (new_name, new_pi, new_dept, new_uni, now, lab_id),
        )
    lab.name = new_name
    lab.pi_id = new_pi
    lab.department = new_dept
    lab.university = new_uni
    lab.updated_at = now
    return lab


def delete_lab(db_path: Path, lab_id: str) -> bool:
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM labs WHERE id = ?", (lab_id,))
    return cur.rowcount > 0


def add_member(db_path: Path, lab_id: str, user_id: str, role: str) -> LabMember:
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        # Re-adding someone whose membership ENDED re-activates the row (fresh joined_at,
        # ended_at cleared) — a student who comes back is a new membership, not a constraint
        # violation against the historical one.
        # Reactivation applies to ENDED rows only: an ACTIVE duplicate must still surface as
        # the IntegrityError the route turns into 409 (adding someone twice is a caller mistake,
        # not a role change — that has its own endpoint).
        existing = conn.execute(
            "SELECT ended_at FROM lab_members WHERE lab_id = ? AND user_id = ?",
            (lab_id, user_id),
        ).fetchone()
        if existing is not None and existing["ended_at"] is not None:
            conn.execute(
                "UPDATE lab_members SET role = ?, joined_at = ?, ended_at = NULL "
                "WHERE lab_id = ? AND user_id = ?",
                (role, now, lab_id, user_id),
            )
        else:
            conn.execute(
                "INSERT INTO lab_members (lab_id, user_id, role, joined_at) VALUES (?, ?, ?, ?)",
                (lab_id, user_id, role, now),
            )
    return LabMember(lab_id=lab_id, user_id=user_id, role=role, joined_at=now)


def update_member_role(
    db_path: Path, lab_id: str, user_id: str, role: str
) -> LabMember | None:
    """Change an existing member's role. Returns None if not a member."""
    with get_db(db_path) as conn:
        cur = conn.execute(
            "UPDATE lab_members SET role = ? WHERE lab_id = ? AND user_id = ? AND ended_at IS NULL",
            (role, lab_id, user_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT lab_id, user_id, role, joined_at FROM lab_members "
            "WHERE lab_id = ? AND user_id = ? AND ended_at IS NULL",
            (lab_id, user_id),
        ).fetchone()
    return LabMember(lab_id=row["lab_id"], user_id=row["user_id"], role=row["role"], joined_at=row["joined_at"])


def remove_member(db_path: Path, lab_id: str, user_id: str) -> bool:
    """END a membership rather than deleting it: the row with ended_at IS the revocation
    order the cluster-side reconciler executes (CVAT membership removal, grant cleanup).
    Re-adding later re-activates (add_member clears ended_at via the UPSERT there)."""
    from datetime import UTC, datetime
    with get_db(db_path) as conn:
        cur = conn.execute(
            "UPDATE lab_members SET ended_at = ? WHERE lab_id = ? AND user_id = ? "
            "AND ended_at IS NULL",
            (datetime.now(UTC).isoformat(), lab_id, user_id),
        )
    return cur.rowcount > 0


def list_members(db_path: Path, lab_id: str) -> list[LabMember]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT lab_id, user_id, role, joined_at FROM lab_members "
            "WHERE lab_id = ? AND ended_at IS NULL ORDER BY joined_at",
            (lab_id,),
        ).fetchall()
    return [LabMember(lab_id=r["lab_id"], user_id=r["user_id"], role=r["role"], joined_at=r["joined_at"]) for r in rows]


def get_member_role(db_path: Path, lab_id: str, user_id: str) -> str | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT role FROM lab_members WHERE lab_id = ? AND user_id = ? AND ended_at IS NULL",
            (lab_id, user_id),
        ).fetchone()
    return row["role"] if row else None


def _row_to_lab(row) -> Lab:
    return Lab(
        id=row["id"],
        name=row["name"],
        pi_id=row["pi_id"],
        department=row["department"],
        university=row["university"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
