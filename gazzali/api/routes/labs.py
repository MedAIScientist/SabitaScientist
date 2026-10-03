from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from ...crud.labs import (
    add_member,
    create_lab,
    delete_lab,
    get_lab,
    get_member_role,
    list_labs,
    list_members,
    remove_member,
    update_lab,
    update_member_role,
)
from ...crud.users import get_user_by_id
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_admin, require_lab_role
from ..schemas import (
    AddLabMemberRequest,
    LabCreate,
    LabMemberResponse,
    LabResponse,
    LabUpdate,
    UpdateLabMemberRoleRequest,
)

router = APIRouter()


def _lab_to_response(lab, db_path, viewer: User) -> LabResponse:
    """Serialise a lab for one particular caller.

    Labs themselves are not secret, but their roster is: only a member (any role)
    or a platform admin gets the names. Everyone else gets an empty members list
    plus member_count, which is enough to show the lab's size without publishing
    who works there. can_manage mirrors require_lab_role("pi", "admin") exactly,
    so the UI and the routes cannot disagree about who may edit.
    """
    members = list_members(db_path, lab.id)
    viewer_role = next((m.role for m in members if m.user_id == viewer.id), None)
    may_see_roster = viewer.is_admin or viewer_role is not None
    member_responses = []
    for m in members if may_see_roster else []:
        user = get_user_by_id(db_path, m.user_id)
        member_responses.append(
            LabMemberResponse(
                user_id=m.user_id,
                username=user.username if user else m.user_id,
                role=m.role,
                joined_at=m.joined_at,
            )
        )
    return LabResponse(
        id=lab.id,
        name=lab.name,
        pi_id=lab.pi_id,
        department=lab.department,
        university=lab.university,
        created_at=lab.created_at,
        updated_at=lab.updated_at,
        members=member_responses,
        member_count=len(members),
        can_manage=viewer.is_admin or viewer_role in ("pi", "admin"),
    )


@router.get("", response_model=list[LabResponse])
def list_all_labs(current_user: User = Depends(get_current_user)):
    db = get_db_path()
    return [_lab_to_response(lab, db, current_user) for lab in list_labs(db)]


@router.post("", response_model=LabResponse, status_code=status.HTTP_201_CREATED)
def create_new_lab(
    body: LabCreate,
    current_user: User = Depends(get_current_user),
):
    # Professors create labs and lead them; students join a professor's lab.
    if not (current_user.is_admin or current_user.role in ("professor", "admin")):
        raise HTTPException(status_code=403, detail="Only professors can create a lab")
    db = get_db_path()
    # Set labs.pi_id at creation as well as writing the lab_members 'pi' row, so
    # the two records of "who leads this lab" can never disagree.
    lab = create_lab(
        db,
        name=body.name,
        pi_id=current_user.id,
        department=body.department,
        university=body.university,
    )
    add_member(db, lab.id, current_user.id, "pi")
    lab = get_lab(db, lab.id)
    return _lab_to_response(lab, db, current_user)


@router.get("/{lab_id}", response_model=LabResponse)
def get_lab_detail(
    lab_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    lab = get_lab(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    return _lab_to_response(lab, db, current_user)


@router.put("/{lab_id}", response_model=LabResponse)
def update_existing_lab(
    lab_id: str,
    body: LabUpdate,
    current_user: User = Depends(require_lab_role("pi", "admin")),
):
    """Update a lab (lab 'pi'/'admin' member, or a platform admin)."""
    db = get_db_path()
    lab = get_lab(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    if body.pi_id is not None and body.pi_id != lab.pi_id:
        # pi_id is special: handing the lab to somebody else is not an ordinary
        # edit. A 'pi'/'admin' member who is not *this* lab's PI may rename the
        # lab but may not transfer it, so only the current PI or a platform
        # admin gets past here. Legacy labs whose pi_id was never set count
        # their lab_members 'pi' row as "current PI", otherwise the real PI of
        # such a lab could never repair pi_id without an admin.
        is_current_pi = current_user.id == lab.pi_id or (
            lab.pi_id is None and get_member_role(db, lab_id, current_user.id) == "pi"
        )
        if not current_user.is_admin and not is_current_pi:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="only the lab PI or a platform admin can reassign pi_id",
            )
        if get_member_role(db, lab_id, body.pi_id) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="new pi_id must already be a member of this lab",
            )
    lab = update_lab(
        db,
        lab_id,
        name=body.name,
        pi_id=body.pi_id,
        department=body.department,
        university=body.university,
    )
    return _lab_to_response(lab, db, current_user)


@router.delete("/{lab_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_lab(
    lab_id: str,
    current_user: User = Depends(require_admin),
):
    delete_lab(get_db_path(), lab_id)


@router.post(
    "/{lab_id}/members",
    response_model=LabMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_lab_member(
    lab_id: str,
    body: AddLabMemberRequest,
    current_user: User = Depends(require_lab_role("pi", "admin")),
):
    """Add a member to the lab (lab 'pi'/'admin' member, or a platform admin)."""
    db = get_db_path()
    lab = get_lab(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    user = get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        member = add_member(db, lab_id, user_id=body.user_id, role=body.role)
    except sqlite3.IntegrityError as exc:
        # (lab_id, user_id) is the primary key, and both rows referenced by the
        # foreign keys were just checked above — so the only integrity error
        # left is a repeat add, which is a conflict and not a server error.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="user is already a member of this lab",
        ) from exc
    return LabMemberResponse(
        user_id=member.user_id,
        username=user.username,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.put("/{lab_id}/members/{user_id}", response_model=LabMemberResponse)
def change_lab_member_role(
    lab_id: str,
    user_id: str,
    body: UpdateLabMemberRoleRequest,
    current_user: User = Depends(require_lab_role("pi", "admin")),
):
    """Change a member's lab role (lab 'pi'/'admin' member, or a platform admin)."""
    db = get_db_path()
    member = update_member_role(db, lab_id, user_id=user_id, role=body.role)
    if member is None:
        raise HTTPException(status_code=404, detail="Lab member not found")
    user = get_user_by_id(db, user_id)
    return LabMemberResponse(
        user_id=member.user_id,
        username=user.username if user else member.user_id,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete(
    "/{lab_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_lab_member(
    lab_id: str,
    user_id: str,
    current_user: User = Depends(require_lab_role("pi", "admin")),
):
    """Remove a member from the lab (lab 'pi'/'admin' member, or a platform admin)."""
    remove_member(get_db_path(), lab_id, user_id)
