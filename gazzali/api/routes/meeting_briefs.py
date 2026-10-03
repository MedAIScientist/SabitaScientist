"""AI meeting briefs: before a 1:1, what changed, what is stuck, and what to ask.

Grounding is the whole point. The model only sees what was RECORDED here — weekly
reports, their items, follow-ups and attendance — and is told to use nothing else.
When nothing is recorded the job fails with that reason instead of letting the
model invent a summary. Course work, grades and transcripts are deliberately not
part of supervision here and are never included.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import partial

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from ...crud import followups as followups_crud
from ...crud import meeting_briefs as briefs_crud
from ...crud import supervision as supervision_crud
from ...crud.ai_jobs import AiJobError, create_job, run_tracked
from ...crud.ai_usage import UsageContext
from ...crud.users import get_user_by_id
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user
from .followups import is_supervisor, to_response

router = APIRouter()

_WEEKS = 4

BRIEF_SYSTEM = """You prepare a research supervisor for a one-to-one meeting with a student.
Use ONLY the facts in the provided record. Never invent results, numbers, dates, papers or
events. If something is not in the record, do not mention it. Quote item titles exactly.
Write in the language of the record. Be brief and concrete.

Output exactly these Markdown sections:
## What changed
## What is stuck
## Three questions to ask
Questions must be specific to the record (e.g. an open follow-up, a blocker, a missed week)."""

AGENDA_SYSTEM = """You prepare the agenda for a research group's weekly meeting.
Use ONLY the facts in the provided records. Never invent anything. Quote names and item
titles exactly. Write in the language of the records.

Output Markdown: a short "## Highlights" list, then "## Needs discussion" (blockers, help
requests, overdue follow-ups — one line each, naming the student), then "## Suggested order"
(students in the order worth discussing, with one reason each)."""


def student_record(db, student_id: str, weeks: int = _WEEKS) -> str:
    """What was recorded about one student recently, as plain text for the model."""
    since = (date.today() - timedelta(weeks=weeks)).isoformat()
    lines: list[str] = []
    for r in supervision_crud.list_reports(db, student_id=student_id, date_from=since, limit=weeks + 1):
        risk = r.risk_override or r.risk_level
        lines.append(f"Week of {r.week_start}: report {r.status}, review {r.review_status}, risk {risk}.")
        for label, text in (("Accomplished", r.accomplished), ("Next focus", r.next_focus),
                            ("Support requested", r.support_requested), ("Supervisor feedback", r.feedback)):
            if text:
                lines.append(f"  {label}: {text}")
        for i in supervision_crud.list_report_items(db, r.id):
            bits = [f"status {i.status or '—'}", f"progress {i.progress_pct}%", f"risk {i.risk_level}"]
            if i.needs_help:
                bits.append("NEEDS HELP")
            lines.append(f"  Item “{i.item_title}”: " + ", ".join(bits))
            for label, text in (("changed", i.what_changed), ("blocker", i.blocker), ("next", i.next_step)):
                if text:
                    lines.append(f"    {label}: {text}")
        att = supervision_crud.get_attendance(db, student_id, r.week_start)
        if att and att.status != "not_set":
            lines.append(f"  Meeting attendance: {att.status}")
    for f in followups_crud.list_followups(db, student_ids=[student_id], status="open"):
        info = to_response(f)
        lines.append(
            f"Open follow-up (asked {info.weeks_open} week(s) ago"
            + (f", due {f.due_date}" + (", OVERDUE" if info.overdue else "") if f.due_date else "")
            + f"): {f.text}" + (f" — student's note: {f.student_note}" if f.student_note else "")
        )
    return "\n".join(lines)


def _require_supervisor(db, user: User, student_id: str) -> None:
    if not (user.is_admin or is_supervisor(db, user.id, student_id)):
        raise HTTPException(status_code=404, detail="Student not found")


class BriefResponse(BaseModel):
    id: str
    student_id: str | None = None
    content: str
    created_at: str


async def _make_brief(professor_id: str, student_id: str | None, system: str, record: str) -> str:
    from ..._ai import run_llm_direct_async

    db = get_db_path()
    if not record.strip():
        raise AiJobError("Nothing has been recorded in the last weeks (no weekly updates or follow-ups), "
                         "so there is nothing to summarise yet.")
    text = await run_llm_direct_async(
        system_prompt=system, user_prompt=f"Record:\n{record}", temperature=0.2,
        context=UsageContext(task="meeting-brief" if student_id else "meeting-agenda", user_id=professor_id),
    )
    if not text.strip():
        return None  # type: ignore[return-value]  # run_tracked reports "no text"
    briefs_crud.save_brief(db, professor_id=professor_id, student_id=student_id, content=text.strip())
    return "/meeting" + (f"?student={student_id}" if student_id else "")


@router.post("/students/{student_id}/meeting-brief", status_code=202)
def start_student_brief(student_id: str, background_tasks: BackgroundTasks,
                        current_user: User = Depends(get_current_user)):
    db = get_db_path()
    _require_supervisor(db, current_user, student_id)
    student = get_user_by_id(db, student_id)
    record = student_record(db, student_id)
    job = create_job(db, kind="meeting-brief", title=f"Meeting brief: {student.username if student else student_id}",
                     user_id=current_user.id)
    background_tasks.add_task(run_tracked, job.id, partial(_make_brief, current_user.id, student_id, BRIEF_SYSTEM, record))
    return {"job_id": job.id}


@router.get("/students/{student_id}/meeting-brief", response_model=BriefResponse | None)
def latest_student_brief(student_id: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    _require_supervisor(db, current_user, student_id)
    return briefs_crud.latest_brief(db, professor_id=current_user.id, student_id=student_id)


@router.post("/meeting-agenda", status_code=202)
def start_group_agenda(background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)):
    if not (current_user.is_admin or current_user.role == "professor"):
        raise HTTPException(status_code=403, detail="Only supervisors prepare a group agenda")
    db = get_db_path()
    parts = []
    from ...supervision_scope import lab_students

    for st in lab_students(db, current_user.id):
        record = student_record(db, st["student_id"], weeks=1)
        if record.strip():
            parts.append(f"### Student: {st['username']} ({st['lab_name']})\n{record}")
    job = create_job(db, kind="meeting-agenda", title="Group meeting agenda", user_id=current_user.id)
    background_tasks.add_task(run_tracked, job.id, partial(_make_brief, current_user.id, None, AGENDA_SYSTEM, "\n\n".join(parts)))
    return {"job_id": job.id}


@router.get("/meeting-agenda", response_model=BriefResponse | None)
def latest_group_agenda(current_user: User = Depends(get_current_user)):
    return briefs_crud.latest_brief(get_db_path(), professor_id=current_user.id, student_id=None)
