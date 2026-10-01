"""Semester progress report for one student, as a print-ready page and a Word file.

Built from what was recorded during the term — weekly updates and the supervisor's
feedback, attendance, follow-ups, publications and the skills check — and laid out
to make thesis-committee (TİK) and graduate-school forms quick to fill in.

No PDF or Word library: the page prints to PDF from the browser, and Word opens the
same HTML served as .doc (editable). Course work, grades and thesis phases are
deliberately not part of this report.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from ...crud import followups as followups_crud
from ...crud import supervision as supervision_crud
from ...crud.users import get_user_by_id
from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user
from .followups import is_supervisor
from .skills import LEVELS, SKILLS, term_of

router = APIRouter()


def term_range(term: str) -> tuple[date, date]:
    """'2026 Fall' → 1 Sep 2026 – 31 Jan 2027; '2027 Spring' → 1 Feb – 31 Aug 2027."""
    try:
        year_s, season = term.split()
        year = int(year_s)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="term must look like '2026 Fall' or '2027 Spring'") from exc
    if season == "Fall":
        return date(year, 9, 1), date(year + 1, 1, 31)
    if season == "Spring":
        return date(year, 2, 1), date(year, 8, 31)
    raise HTTPException(status_code=400, detail="term must be Fall or Spring")


def _e(text) -> str:
    return escape(str(text)) if text not in (None, "") else "—"


def build_report_html(db, student_id: str, term: str) -> str:
    start, end = term_range(term)
    s, e = start.isoformat(), end.isoformat()
    student = get_user_by_id(db, student_id)
    assignment = supervision_crud.get_active_supervisor(db, student_id)
    supervisor = get_user_by_id(db, assignment.professor_id) if assignment else None
    journey = supervision_crud.get_active_journey(db, student_id)

    reports = sorted(supervision_crud.list_reports(db, student_id=student_id, date_from=s, date_to=e),
                     key=lambda r: r.week_start)
    weeks_in_term = max(1, min((end - start).days, (date.today() - start).days) // 7 + 1) if date.today() >= start else 0
    submitted = [r for r in reports if r.status == "submitted"]
    attendance = Counter()
    for r in reports:
        att = supervision_crud.get_attendance(db, student_id, r.week_start)
        if att and att.status != "not_set":
            attendance[att.status] += 1

    fus = [f for f in followups_crud.list_followups(db, student_ids=[student_id]) if s <= f.created_at[:10] <= e]
    with get_db(db) as conn:
        pubs = conn.execute(
            "SELECT title, venue, venue_type, status, submitted_at, accepted_at, published_at FROM publications "
            "WHERE created_by = ? ORDER BY created_at", (student_id,)).fetchall()
        skills = conn.execute(
            "SELECT perspective, scores_json, comment FROM skill_assessments WHERE student_id = ? AND term = ?",
            (student_id, term)).fetchall()

    def in_term(d) -> bool:
        return bool(d) and s <= d[:10] <= e

    pub_rows = [p for p in pubs if in_term(p["submitted_at"]) or in_term(p["accepted_at"]) or in_term(p["published_at"])]
    drafts = [p for p in pubs if p["status"] == "draft"]
    skill_by = {r["perspective"]: (json.loads(r["scores_json"]), r["comment"]) for r in skills}

    week_rows = "".join(
        f"<tr><td>{_e(r.week_start)}</td><td>{_e(r.status)}</td><td>{_e(r.risk_override or r.risk_level)}</td>"
        f"<td>{_e(r.accomplished)}</td><td>{_e(r.next_focus)}</td><td>{_e(r.feedback)}</td></tr>"
        for r in reports) or "<tr><td colspan=6>No weekly updates recorded this term.</td></tr>"
    fu_rows = "".join(
        f"<tr><td>{_e(f.created_at[:10])}</td><td>{_e(f.text)}</td><td>{_e(f.status)}</td>"
        f"<td>{_e((f.closed_at or '')[:10])}</td><td>{_e(f.student_note)}</td></tr>"
        for f in fus) or "<tr><td colspan=5>No follow-ups this term.</td></tr>"
    pub_html = "".join(
        f"<tr><td>{_e(p['title'])}</td><td>{_e(p['venue'])}</td><td>{_e(p['venue_type'])}</td><td>{_e(p['status'])}</td>"
        f"<td>{_e((p['submitted_at'] or '')[:10])}</td></tr>" for p in pub_rows
    ) or "<tr><td colspan=5>No papers submitted, accepted or published this term.</td></tr>"
    skill_html = "".join(
        f"<tr><td>{_e(label)}</td>"
        + "".join(f"<td>{_e(skill_by.get(p, ({}, None))[0].get(key))}</td>" for p in ("self", "supervisor"))
        + "</tr>" for key, label in SKILLS.items())
    skill_comments = "".join(f"<p><b>{_e(p.title())}:</b> {_e(c)}</p>" for p, (_, c) in skill_by.items() if c)
    att_text = ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in sorted(attendance.items())) or "No attendance recorded."

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Semester report — {_e(student.username if student else student_id)} — {_e(term)}</title>
<style>
 body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt; color: #111; max-width: 900px; margin: 24px auto; padding: 0 16px; }}
 h1 {{ font-size: 18pt; margin: 0 0 4px; }} h2 {{ font-size: 13pt; margin: 22px 0 6px; border-bottom: 1px solid #999; }}
 table {{ border-collapse: collapse; width: 100%; font-size: 10pt; }} th, td {{ border: 1px solid #bbb; padding: 4px 6px; text-align: left; vertical-align: top; }}
 th {{ background: #f0f0f0; }} .meta td {{ border: none; padding: 2px 8px 2px 0; }} .box {{ border: 1px solid #999; min-height: 90px; padding: 6px; }}
 @media print {{ body {{ margin: 0 auto; }} }}
</style></head><body>
<h1>Semester progress report</h1>
<table class="meta">
 <tr><td><b>Student</b></td><td>{_e(student.username if student else student_id)}</td><td><b>Term</b></td><td>{_e(term)} ({s} – {e})</td></tr>
 <tr><td><b>Supervisor</b></td><td>{_e(supervisor.username if supervisor else None)}</td><td><b>Degree</b></td><td>{_e(journey.level if journey else None)}{(' · ' + escape(journey.programme)) if journey and journey.programme else ''}</td></tr>
 <tr><td><b>Thesis title</b></td><td colspan=3>{_e(journey.thesis_title if journey else None)}</td></tr>
 <tr><td><b>Prepared</b></td><td colspan=3>{date.today().isoformat()}</td></tr>
</table>

<h2>Weekly updates</h2>
<p>{len(submitted)} of {weeks_in_term} weeks submitted. Meeting attendance — {escape(att_text)}</p>
<table><tr><th>Week</th><th>Status</th><th>Risk</th><th>Accomplished</th><th>Next focus</th><th>Supervisor feedback</th></tr>{week_rows}</table>

<h2>Follow-ups requested by the supervisor</h2>
<p>{sum(f.status == 'done' for f in fus)} done, {sum(f.status == 'open' for f in fus)} still open, {sum(f.status == 'dropped' for f in fus)} dropped.</p>
<table><tr><th>Asked</th><th>Request</th><th>Status</th><th>Closed</th><th>Student's note</th></tr>{fu_rows}</table>

<h2>Publications</h2>
<table><tr><th>Title</th><th>Venue</th><th>Type</th><th>Status</th><th>Submitted</th></tr>{pub_html}</table>
<p>Drafts in progress: {escape(', '.join(p['title'] for p in drafts)) if drafts else 'none'}.</p>

<h2>Skills check ({_e(term)}; 1 {LEVELS[1]} – 4 {LEVELS[4]})</h2>
<table><tr><th>Skill</th><th>Self</th><th>Supervisor</th></tr>{skill_html}</table>{skill_comments}

<h2>Supervisor's overall assessment</h2>
<div class="box"></div>
<h2>Plan for next term</h2>
<div class="box"></div>
</body></html>"""


def _load(db, user: User, student_id: str) -> None:
    if not (user.is_admin or user.id == student_id or is_supervisor(db, user.id, student_id)):
        raise HTTPException(status_code=404, detail="Student not found")


@router.get("/students/{student_id}/semester-report", response_class=HTMLResponse)
def semester_report(student_id: str, term: str | None = Query(None), current_user: User = Depends(get_current_user)):
    db = get_db_path()
    _load(db, current_user, student_id)
    return HTMLResponse(build_report_html(db, student_id, term or term_of(date.today())))


@router.get("/students/{student_id}/semester-report.doc")
def semester_report_doc(student_id: str, term: str | None = Query(None), current_user: User = Depends(get_current_user)):
    db = get_db_path()
    _load(db, current_user, student_id)
    t = term or term_of(date.today())
    student = get_user_by_id(db, student_id)
    name = (student.username if student else student_id).replace(" ", "_")
    return Response(
        content=build_report_html(db, student_id, t), media_type="application/msword",
        headers={"Content-Disposition": f'attachment; filename="semester-report-{name}-{t.replace(" ", "-")}.doc"'},
    )
