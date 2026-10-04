"""One call for a professor to see every student they supervise and who needs them.

Per student: this week's update, recent consistency, risk, follow-ups, overdue
tasks, blocked work, help requests, research in progress and graduation readiness,
plus plain-language reasons. Sorted so the student who needs attention is first.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException

from ...db import get_db, get_db_path
from ...models import User
from ...supervision_scope import lab_students
from ..deps import get_current_user

router = APIRouter()

WEEKS = 8
_DONE_ITEMS = ("accepted", "published", "rejected")


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _student_row(conn, student: dict, today: date) -> dict:
    sid = student["student_id"]
    this_week = _monday(today).isoformat()
    since = (_monday(today) - timedelta(weeks=WEEKS)).isoformat()
    reports = conn.execute(
        "SELECT * FROM weekly_reports WHERE student_id = ? AND week_start >= ? ORDER BY week_start DESC",
        (sid, since),
    ).fetchall()
    current = next((r for r in reports if r["week_start"] == this_week), None)
    submitted = [r for r in reports if r["status"] == "submitted"]
    last = submitted[0] if submitted else None
    recent_weeks = {r["week_start"] for r in submitted if r["week_start"] < this_week}
    awaiting_review = [r for r in submitted if r["review_status"] != "reviewed" and not r["reviewed_at"]]
    blocked = conn.execute(
        """SELECT item_title, blocker FROM weekly_report_items
            WHERE report_id = ? AND (status = 'blocked' OR needs_help = 1)""",
        (last["id"],),
    ).fetchall() if last else []
    fu = conn.execute(
        """SELECT COUNT(*) AS open, SUM(CASE WHEN due_date IS NOT NULL AND due_date < ? THEN 1 ELSE 0 END) AS overdue
             FROM supervision_followups WHERE student_id = ? AND status = 'open'""",
        (today.isoformat(), sid),
    ).fetchone()
    tasks = conn.execute(
        """SELECT COUNT(*) AS open, SUM(CASE WHEN deadline IS NOT NULL AND deadline < ? THEN 1 ELSE 0 END) AS overdue
             FROM tasks WHERE assignee_id = ? AND status != 'done'""",
        (today.isoformat(), sid),
    ).fetchone()
    journey = conn.execute(
        "SELECT level, thesis_title FROM academic_journeys WHERE student_id = ? ORDER BY status = 'active' DESC, created_at DESC LIMIT 1",
        (sid,),
    ).fetchone()
    pubs = conn.execute(
        f"SELECT COUNT(*) FROM publications WHERE created_by = ? AND status NOT IN ({','.join('?' * len(_DONE_ITEMS))})",
        (sid, *_DONE_ITEMS),
    ).fetchone()[0]
    risk = (last["risk_override"] or last["risk_level"]) if last else None
    help_text = (last["support_requested"] or "").strip() if last else ""

    if current is None:
        week = "not_started"
    elif current["status"] != "submitted":
        week = "draft"
    elif current["review_status"] == "reviewed" or current["reviewed_at"]:
        week = "reviewed"
    else:
        week = "submitted"

    reasons: list[str] = []
    score = 0
    if (fu["overdue"] or 0) > 0:
        reasons.append(f"{fu['overdue']} overdue follow-up{'s' if fu['overdue'] > 1 else ''}")
        score += 3
    if risk == "high":
        reasons.append("high risk last week")
        score += 3
    if help_text and awaiting_review:
        reasons.append("asked for help")
        score += 3
    if blocked:
        reasons.append(f"{len(blocked)} blocked item{'s' if len(blocked) > 1 else ''}")
        score += 2
    if (tasks["overdue"] or 0) > 0:
        reasons.append(f"{tasks['overdue']} overdue task{'s' if tasks['overdue'] > 1 else ''}")
        score += 2
    missed = WEEKS - len(recent_weeks)
    if missed >= 2:
        reasons.append(f"no update in {missed} of the last {WEEKS} weeks")
        score += 1 + missed // 3
    if awaiting_review:
        reasons.append(f"{len(awaiting_review)} update{'s' if len(awaiting_review) > 1 else ''} to review")
        score += 1

    return {
        "student_id": sid,
        "name": student["username"],
        "lab_name": student.get("lab_name"),
        "level": journey["level"] if journey else None,
        "thesis_title": journey["thesis_title"] if journey else None,
        "this_week": week,
        "last_submitted": last["week_start"] if last else None,
        "weeks_submitted": len(recent_weeks),
        "weeks_window": WEEKS,
        "risk": risk,
        "help_requested": help_text or None,
        "awaiting_review": len(awaiting_review),
        "followups_open": fu["open"] or 0,
        "followups_overdue": fu["overdue"] or 0,
        "tasks_open": tasks["open"] or 0,
        "tasks_overdue": tasks["overdue"] or 0,
        "blocked": [{"title": b["item_title"], "blocker": b["blocker"]} for b in blocked],
        "active_papers": pubs,
        "attention": score,
        "reasons": reasons,
    }


@router.get("/supervision/students/overview")
def students_overview(current_user: User = Depends(get_current_user)):
    if current_user.role != "professor" and not current_user.is_admin:
        raise HTTPException(403, "for professors")
    db = get_db_path()
    students = list({s["student_id"]: s for s in lab_students(db, current_user.id)}.values())
    today = date.today()
    with get_db(db) as conn:
        rows = [_student_row(conn, s, today) for s in students]
    return sorted(rows, key=lambda r: (-r["attention"], r["name"].lower()))
