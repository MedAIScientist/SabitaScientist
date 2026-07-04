from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...crud.labs import (
    add_member,
    create_lab,
    delete_lab,
    get_lab,
    list_labs,
    list_members,
    remove_member,
    update_lab,
)
from ...crud.users import get_user_by_id
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_admin
from ..schemas import (
    AddLabMemberRequest,
    LabCreate,
    LabMemberResponse,
    LabResponse,
    LabUpdate,
)

router = APIRouter()


def _lab_to_response(lab, db_path) -> LabResponse:
    members = list_members(db_path, lab.id)
    member_responses = []
    for m in members:
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
    )


@router.get("", response_model=list[LabResponse])
def list_all_labs(current_user: User = Depends(get_current_user)):
    db = get_db_path()
    return [_lab_to_response(lab, db) for lab in list_labs(db)]


@router.post("", response_model=LabResponse, status_code=status.HTTP_201_CREATED)
def create_new_lab(
    body: LabCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    lab = create_lab(
        db, name=body.name, department=body.department, university=body.university
    )
    if lab.pi_id is None:
        add_member(db, lab.id, current_user.id, "pi")
        lab = get_lab(db, lab.id)
    return _lab_to_response(lab, db)


@router.get("/{lab_id}", response_model=LabResponse)
def get_lab_detail(
    lab_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    lab = get_lab(db, lab_id)
    if not lab:
        raise HTTPException(status_code=404, detail="Lab not found")
    return _lab_to_response(lab, db)


@router.put("/{lab_id}", response_model=LabResponse)
def update_existing_lab(
    lab_id: str,
    body: LabUpdate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    lab = update_lab(
        db,
        lab_id,
        name=body.name,
        pi_id=body.pi_id,
        department=body.department,
        university=body.university,
    )
    return _lab_to_response(lab, db)


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
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    user = get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    member = add_member(db, lab_id, user_id=body.user_id, role=body.role)
    return LabMemberResponse(
        user_id=member.user_id,
        username=user.username,
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
    current_user: User = Depends(get_current_user),
):
    remove_member(get_db_path(), lab_id, user_id)
