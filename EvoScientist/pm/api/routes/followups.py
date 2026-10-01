"""Follow-ups from weekly-report reviews, for the student and their supervisor.

Who may do what:
* the student sees their own follow-ups and may mark them done / not done, with a note;
* the student's ACTIVE supervisor (or a platform admin) sees and closes them,
  including dropping one that no longer applies.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ...crud import followups as followups_crud
from ...crud import supervision as supervision_crud
from ...db import get_db_path
from ...models import SupervisionFollowup, User
from ..deps import get_current_user

router = APIRouter()


class FollowupIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    due_date: str | None = None  # YYYY-MM-DD


class FollowupResponse(BaseModel):
    id: str
    student_id: str
    professor_id: str
    report_id: str | None = None
    text: str
    due_date: str | None = None
    status: str
    student_note: str | None = None
    created_at: str
    closed_at: str | None = None
    weeks_open: int  # whole weeks since it was asked, until it was closed
    overdue: bool


class FollowupUpdate(BaseModel):
    status: Literal["open", "done", "dropped"]
    note: str | None = Field(default=None, max_length=2000)


def is_supervisor(db, professor_id: str, student_id: str) -> bool:
    assignment = supervision_crud.get_active_supervisor(db, student_id)
    return assignment is not None and assignment.professor_id == professor_id


def to_response(f: SupervisionFollowup) -> FollowupResponse:
    start = datetime.fromisoformat(f.created_at)
    end = datetime.fromisoformat(f.closed_at) if f.closed_at else datetime.now(UTC)
    overdue = f.status == "open" and bool(f.due_date) and f.due_date < date.today().isoformat()
    return FollowupResponse(**f.__dict__, weeks_open=max(0, (end - start).days // 7), overdue=overdue)


@router.get("/followups", response_model=list[FollowupResponse])
def list_followups(
    student_id: str | None = Query(None),
    status: Literal["open", "done", "dropped"] | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    if current_user.is_admin:
        ids = [student_id] if student_id else None
    elif current_user.role == "professor":
        mine = [a.student_id for a in supervision_crud.list_students_of_professor(db, current_user.id)]
        ids = [student_id] if student_id in mine else ([] if student_id else mine)
    else:
        ids = [current_user.id]
    return [to_response(f) for f in followups_crud.list_followups(db, student_ids=ids, status=status)]


@router.patch("/followups/{followup_id}", response_model=FollowupResponse)
def update_followup(followup_id: str, body: FollowupUpdate, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    f = followups_crud.get_followup(db, followup_id)
    supervisor = f is not None and (current_user.is_admin or is_supervisor(db, current_user.id, f.student_id))
    student = f is not None and f.student_id == current_user.id
    if f is None or not (supervisor or student):
        raise HTTPException(status_code=404, detail="Follow-up not found")
    if body.status == "dropped" and not supervisor:
        raise HTTPException(status_code=403, detail="Only the supervisor can drop a follow-up")
    note = body.note if student else None  # the note is the student's answer
    return to_response(followups_crud.set_status(db, followup_id, body.status, note))
