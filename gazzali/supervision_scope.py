"""Who supervises whom: the lab is the boundary.

Memberships are ended, not deleted (lab_members.ended_at), so every query here
counts ACTIVE memberships only: a student who left the lab is no longer supervised.

A professor works only with the students of the labs they lead — labs where they
hold the lab role 'pi' or 'admin', or are the lab's registered PI. A student is a
user with the platform role 'student' who is a member of such a lab. A professor
can neither see nor act on any other student; a platform admin can see everyone.

Every supervision check (reports, reviews, follow-ups, meetings, attendance,
journeys, readiness, skills, progress reports, cohort, analytics, AI usage) goes
through this module so the rule lives in one place.
"""

from __future__ import annotations

from pathlib import Path

from .db import get_db
from .models import User

LEADER_LAB_ROLES = ("pi", "admin")


def led_lab_ids(db: Path, professor_id: str) -> list[str]:
    """Labs the user leads: lab role pi/admin, or labs.pi_id."""
    with get_db(db) as conn:
        rows = conn.execute(
            f"""SELECT id FROM labs WHERE pi_id = ?
                UNION
                SELECT lab_id FROM lab_members WHERE user_id = ? AND ended_at IS NULL AND role IN ({','.join('?' * len(LEADER_LAB_ROLES))})""",
            (professor_id, professor_id, *LEADER_LAB_ROLES),
        ).fetchall()
    return [r[0] for r in rows]


def lab_students(db: Path, professor_id: str) -> list[dict]:
    """The students of the labs the professor leads: [{student_id, username, lab_id, lab_name, joined_at}].

    A student in two of the professor's labs appears once (their first lab by name).
    """
    labs = led_lab_ids(db, professor_id)
    if not labs:
        return []
    with get_db(db) as conn:
        rows = conn.execute(
            f"""SELECT u.id AS student_id, u.username, l.id AS lab_id, l.name AS lab_name, m.joined_at
                  FROM lab_members m
                  JOIN users u ON u.id = m.user_id
                  JOIN labs l  ON l.id = m.lab_id
                 WHERE m.lab_id IN ({','.join('?' * len(labs))}) AND m.ended_at IS NULL
                   AND u.role = 'student' AND u.id != ?
                 ORDER BY u.username, l.name""",
            (*labs, professor_id),
        ).fetchall()
    seen: dict[str, dict] = {}
    for r in rows:
        seen.setdefault(r["student_id"], dict(r))
    return list(seen.values())


def lab_student_ids(db: Path, professor_id: str) -> list[str]:
    return [s["student_id"] for s in lab_students(db, professor_id)]


def supervises(db: Path, professor_id: str, student_id: str) -> bool:
    """True when the student is in a lab the professor leads."""
    return student_id in set(lab_student_ids(db, professor_id))


def can_view_student(db: Path, user: User, student_id: str) -> bool:
    """The student themselves, an admin, or a professor leading one of the student's labs."""
    return user.id == student_id or user.is_admin or supervises(db, user.id, student_id)


def shares_led_lab(db: Path, professor_id: str, student_id: str) -> bool:
    """Whether a supervisor assignment between the two is allowed (same lab, professor leads it)."""
    return supervises(db, professor_id, student_id)


def lab_leaders_of(db: Path, student_id: str) -> list[dict]:
    """The professors leading the student's labs: [{professor_id, username, lab_id, lab_name}]."""
    with get_db(db) as conn:
        rows = conn.execute(
            f"""SELECT DISTINCT u.id AS professor_id, u.username, l.id AS lab_id, l.name AS lab_name
                  FROM lab_members sm
                  JOIN labs l ON l.id = sm.lab_id
                  JOIN users u ON (u.id = l.pi_id OR u.id IN (
                       SELECT lm.user_id FROM lab_members lm
                        WHERE lm.lab_id = l.id AND lm.ended_at IS NULL AND lm.role IN ({','.join('?' * len(LEADER_LAB_ROLES))})))
                 WHERE sm.user_id = ? AND sm.ended_at IS NULL AND u.id != ?
                 ORDER BY l.name, u.username""",
            (*LEADER_LAB_ROLES, student_id, student_id),
        ).fetchall()
    return [dict(r) for r in rows]
