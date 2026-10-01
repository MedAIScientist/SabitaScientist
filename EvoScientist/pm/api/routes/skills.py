"""Semester skills check: the student rates themselves, the supervisor rates them,
1–4 per skill, once per term. Shown side by side and as a trend over terms.

Research skills only — course work and grades are deliberately not tracked here.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user
from .followups import is_supervisor

router = APIRouter()

SKILLS: dict[str, str] = {
    "writing": "Scientific writing",
    "methods": "Methods & statistics",
    "presenting": "Presenting",
    "independence": "Independence",
}
LEVELS = {1: "Beginning", 2: "Developing", 3: "Proficient", 4: "Independent"}


def term_of(d: date) -> str:
    """Academic term label: Fall runs September–January, Spring February–August."""
    if d.month >= 9:
        return f"{d.year} Fall"
    if d.month == 1:
        return f"{d.year - 1} Fall"
    return f"{d.year} Spring"


class AssessmentIn(BaseModel):
    student_id: str
    scores: dict[str, int]
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("scores")
    @classmethod
    def valid_scores(cls, v: dict[str, int]) -> dict[str, int]:
        unknown = set(v) - set(SKILLS)
        if unknown:
            raise ValueError(f"unknown skills: {sorted(unknown)}")
        if any(s not in LEVELS for s in v.values()):
            raise ValueError("scores are 1–4")
        return v


class AssessmentOut(BaseModel):
    student_id: str
    perspective: Literal["self", "supervisor"]
    term: str
    scores: dict[str, int]
    comment: str | None = None
    updated_at: str


class SkillsView(BaseModel):
    skills: dict[str, str]
    levels: dict[int, str]
    current_term: str
    assessments: list[AssessmentOut]  # oldest term first


def _perspective(db, user: User, student_id: str) -> Literal["self", "supervisor"] | None:
    if user.id == student_id:
        return "self"
    if user.is_admin or is_supervisor(db, user.id, student_id):
        return "supervisor"
    return None


@router.get("/skills", response_model=SkillsView)
def get_skills(student_id: str = Query(...), current_user: User = Depends(get_current_user)):
    db = get_db_path()
    if _perspective(db, current_user, student_id) is None:
        raise HTTPException(status_code=404, detail="Student not found")
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT student_id, perspective, term, scores_json, comment, updated_at FROM skill_assessments "
            "WHERE student_id = ? ORDER BY substr(term, 1, 4), term DESC, perspective",
            (student_id,),
        ).fetchall()
    return SkillsView(
        skills=SKILLS, levels=LEVELS, current_term=term_of(date.today()),
        assessments=[AssessmentOut(student_id=r["student_id"], perspective=r["perspective"], term=r["term"],
                                   scores=json.loads(r["scores_json"]), comment=r["comment"],
                                   updated_at=r["updated_at"]) for r in rows],
    )


@router.put("/skills", response_model=AssessmentOut)
def save_skills(body: AssessmentIn, current_user: User = Depends(get_current_user)):
    """Rate the current term. The caller's relation to the student decides the perspective."""
    db = get_db_path()
    perspective = _perspective(db, current_user, body.student_id)
    if perspective is None:
        raise HTTPException(status_code=404, detail="Student not found")
    term, now = term_of(date.today()), datetime.now(UTC).isoformat()
    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO skill_assessments (id, student_id, assessor_id, perspective, term, scores_json, comment, updated_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(student_id, perspective, term) DO UPDATE SET
                 assessor_id = excluded.assessor_id, scores_json = excluded.scores_json,
                 comment = excluded.comment, updated_at = excluded.updated_at""",
            (uuid.uuid4().hex, body.student_id, current_user.id, perspective, term,
             json.dumps(body.scores), body.comment, now),
        )
    return AssessmentOut(student_id=body.student_id, perspective=perspective, term=term,
                         scores=body.scores, comment=body.comment, updated_at=now)
