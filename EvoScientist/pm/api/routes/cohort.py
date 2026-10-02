"""Cohort view: a supervisor's students side by side for one term, from recorded data.

Each row: weekly-update submission rate, follow-ups (asked / done / open / overdue,
median days to close), weeks at high risk, papers submitted, and the latest skills
averages. Group medians make outliers visible without any hidden score. No course
work, grades or thesis phases.
"""

from __future__ import annotations

import json
from datetime import date
from statistics import median

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ...crud import followups as followups_crud
from ...crud import supervision as supervision_crud
from ...crud.users import get_user_by_id
from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user
from .progress_report import term_range
from .skills import term_of

router = APIRouter()


class CohortRow(BaseModel):
    student_id: str
    name: str
    weeks_elapsed: int
    weeks_submitted: int
    submission_rate: float | None  # 0..1; None before the term starts
    high_risk_weeks: int
    followups_asked: int
    followups_done: int
    followups_open: int
    followups_overdue: int
    median_days_to_close: float | None
    papers_submitted: int
    skills_self: float | None
    skills_supervisor: float | None


class CohortView(BaseModel):
    term: str
    rows: list[CohortRow]
    medians: dict[str, float | None]


def _med(values: list[float]) -> float | None:
    return round(median(values), 2) if values else None


def _row(db, student_id: str, term: str) -> CohortRow:
    start, end = term_range(term)
    s, e = start.isoformat(), end.isoformat()
    today = date.today()
    elapsed = 0 if today < start else ((min(today, end) - start).days // 7 + 1)
    reports = supervision_crud.list_reports(db, student_id=student_id, date_from=s, date_to=e)
    submitted = [r for r in reports if r.status == "submitted"]
    fus = [f for f in followups_crud.list_followups(db, student_ids=[student_id]) if s <= f.created_at[:10] <= e]
    closed_days = [
        (date.fromisoformat(f.closed_at[:10]) - date.fromisoformat(f.created_at[:10])).days
        for f in fus if f.status == "done" and f.closed_at
    ]
    with get_db(db) as conn:
        papers = conn.execute(
            "SELECT COUNT(*) FROM publications WHERE created_by = ? AND submitted_at >= ? AND substr(submitted_at, 1, 10) <= ?",
            (student_id, s, e)).fetchone()[0]
        skills = {r["perspective"]: json.loads(r["scores_json"]) for r in conn.execute(
            "SELECT perspective, scores_json FROM skill_assessments WHERE student_id = ? AND term = ?",
            (student_id, term)).fetchall()}

    def avg(p: str) -> float | None:
        vals = list(skills.get(p, {}).values())
        return round(sum(vals) / len(vals), 2) if vals else None

    student = get_user_by_id(db, student_id)
    return CohortRow(
        student_id=student_id, name=student.username if student else student_id,
        weeks_elapsed=elapsed, weeks_submitted=len(submitted),
        submission_rate=round(min(1.0, len(submitted) / elapsed), 2) if elapsed else None,
        high_risk_weeks=sum((r.risk_override or r.risk_level) in ("high", "critical") for r in reports),
        followups_asked=len(fus),
        followups_done=sum(f.status == "done" for f in fus),
        followups_open=sum(f.status == "open" for f in fus),
        followups_overdue=sum(f.status == "open" and bool(f.due_date) and f.due_date < today.isoformat() for f in fus),
        median_days_to_close=_med([float(d) for d in closed_days]),
        papers_submitted=papers, skills_self=avg("self"), skills_supervisor=avg("supervisor"),
    )


@router.get("/cohort", response_model=CohortView)
def cohort(term: str | None = Query(None), current_user: User = Depends(get_current_user)):
    if not (current_user.is_admin or current_user.role == "professor"):
        raise HTTPException(status_code=403, detail="Supervisors only")
    db = get_db_path()
    t = term or term_of(date.today())
    term_range(t)  # validates the term
    from ...supervision_scope import lab_student_ids

    ids = lab_student_ids(db, current_user.id)
    rows = sorted((_row(db, sid, t) for sid in ids), key=lambda r: r.name.lower())
    medians = {
        key: _med([v for r in rows if (v := getattr(r, key)) is not None])
        for key in ("submission_rate", "median_days_to_close", "papers_submitted", "followups_open", "high_risk_weeks")
    }
    return CohortView(term=t, rows=rows, medians=medians)
