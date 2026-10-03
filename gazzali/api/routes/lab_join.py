"""Joining a lab: a student asks, the lab's PI (or a lab admin) approves or declines.

Approval makes the student an active lab member, which is what makes them one of
that professor's supervised students (pm/supervision_scope.py).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...crud.labs import add_member, get_lab
from ...crud.labs import get_member_role as get_lab_member_role
from ...db import get_db, get_db_path
from ...models import User
from ...supervision_scope import LEADER_LAB_ROLES, led_lab_ids
from ..deps import get_current_user

router = APIRouter()


class JoinRequestIn(BaseModel):
    lab_role: Literal["phd", "ms"] = "phd"
    message: str | None = Field(default=None, max_length=1000)


class JoinRequestOut(BaseModel):
    id: str
    lab_id: str
    lab_name: str
    user_id: str
    username: str
    lab_role: str
    message: str | None = None
    status: str
    created_at: str
    decided_at: str | None = None


_SELECT = """SELECT r.id, r.lab_id, l.name AS lab_name, r.user_id, u.username, r.lab_role, r.message,
                    r.status, r.created_at, r.decided_at
               FROM lab_join_requests r JOIN labs l ON l.id = r.lab_id JOIN users u ON u.id = r.user_id"""


def _get(db, request_id: str) -> JoinRequestOut | None:
    with get_db(db) as conn:
        row = conn.execute(f"{_SELECT} WHERE r.id = ?", (request_id,)).fetchone()
    return JoinRequestOut(**dict(row)) if row else None


def _leads(db, user: User, lab_id: str) -> bool:
    if user.is_admin:
        return True
    lab = get_lab(db, lab_id)
    return bool(lab) and (lab.pi_id == user.id or get_lab_member_role(db, lab_id, user.id) in LEADER_LAB_ROLES)


@router.post("/{lab_id}/join-requests", response_model=JoinRequestOut, status_code=201)
def request_to_join(lab_id: str, body: JoinRequestIn, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Students request to join a lab; professors create one")
    if not get_lab(db, lab_id):
        raise HTTPException(status_code=404, detail="Lab not found")
    if get_lab_member_role(db, lab_id, current_user.id) is not None:
        raise HTTPException(status_code=409, detail="You are already a member of this lab")
    with get_db(db) as conn:
        if conn.execute("SELECT 1 FROM lab_join_requests WHERE lab_id = ? AND user_id = ? AND status = 'pending'",
                        (lab_id, current_user.id)).fetchone():
            raise HTTPException(status_code=409, detail="You already asked to join this lab")
        rid = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO lab_join_requests (id, lab_id, user_id, lab_role, message, status, created_at) "
            "VALUES (?,?,?,?,?,'pending',?)",
            (rid, lab_id, current_user.id, body.lab_role, body.message, datetime.now(UTC).isoformat()),
        )
    return _get(db, rid)


@router.get("/join-requests/mine", response_model=list[JoinRequestOut])
def my_requests(current_user: User = Depends(get_current_user)):
    with get_db(get_db_path()) as conn:
        rows = conn.execute(f"{_SELECT} WHERE r.user_id = ? ORDER BY r.created_at DESC", (current_user.id,)).fetchall()
    return [JoinRequestOut(**dict(r)) for r in rows]


@router.get("/join-requests/pending", response_model=list[JoinRequestOut])
def pending_for_me(current_user: User = Depends(get_current_user)):
    """Pending requests to the labs the caller leads (all labs for an admin)."""
    db = get_db_path()
    with get_db(db) as conn:
        if current_user.is_admin:
            rows = conn.execute(f"{_SELECT} WHERE r.status = 'pending' ORDER BY r.created_at").fetchall()
        else:
            labs = led_lab_ids(db, current_user.id)
            if not labs:
                return []
            rows = conn.execute(
                f"{_SELECT} WHERE r.status = 'pending' AND r.lab_id IN ({','.join('?' * len(labs))}) ORDER BY r.created_at",
                labs).fetchall()
    return [JoinRequestOut(**dict(r)) for r in rows]


def _decide(lab_id: str, request_id: str, user: User, approve: bool) -> JoinRequestOut:
    db = get_db_path()
    req = _get(db, request_id)
    if req is None or req.lab_id != lab_id or not _leads(db, user, lab_id):
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=409, detail=f"Request already {req.status}")
    if approve and get_lab_member_role(db, lab_id, req.user_id) is None:
        add_member(db, lab_id, req.user_id, req.lab_role)
    with get_db(db) as conn:
        conn.execute("UPDATE lab_join_requests SET status = ?, decided_at = ?, decided_by = ? WHERE id = ?",
                     ("approved" if approve else "declined", datetime.now(UTC).isoformat(), user.id, request_id))
    return _get(db, request_id)


@router.post("/{lab_id}/join-requests/{request_id}/approve", response_model=JoinRequestOut)
def approve(lab_id: str, request_id: str, current_user: User = Depends(get_current_user)):
    return _decide(lab_id, request_id, current_user, approve=True)


@router.post("/{lab_id}/join-requests/{request_id}/decline", response_model=JoinRequestOut)
def decline(lab_id: str, request_id: str, current_user: User = Depends(get_current_user)):
    return _decide(lab_id, request_id, current_user, approve=False)
