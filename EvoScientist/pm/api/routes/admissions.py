"""Admission REST endpoints — Excel import, review workflow, project creation."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from ...crud import admissions as crud
from ...crud.users import get_user_by_id
from ...db import get_db_path
from ...models import User
from ...notifications import notify_admission_review
from ..deps import get_current_user, require_admin
from ..schemas import (
    AdmissionAcceptRequest,
    AdmissionImportResponse,
    AdmissionRejectRequest,
    AdmissionResponse,
    AdmissionUpdate,
    FinancialAidRequest,
)

router = APIRouter()


def _to_response(a) -> AdmissionResponse:
    return AdmissionResponse(
        id=a.id,
        form_submission_id=a.form_submission_id,
        applicant_name=a.applicant_name,
        supervisor=a.supervisor,
        email=a.email,
        phone=a.phone,
        university=a.university,
        department=a.department,
        service_areas=a.service_areas,
        modas_members=a.modas_members,
        grant_context=a.grant_context,
        comments=a.comments,
        status=a.status,
        reviewer_id=a.reviewer_id,
        review_notes=a.review_notes,
        reviewed_at=a.reviewed_at,
        created_project_id=a.created_project_id,
        aid_percentage=a.aid_percentage,
        aid_notes=a.aid_notes,
        aid_at=a.aid_at,
        imported_at=a.imported_at,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.get("/admissions", response_model=list[AdmissionResponse])
def list_admissions(
    status: str | None = Query(default=None, pattern="^(submitted|reviewing|accepted|rejected)$"),
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    items = crud.list_admissions(db, status=status)
    return [_to_response(a) for a in items]


@router.get("/admissions/{admission_id}", response_model=AdmissionResponse)
def get_admission(
    admission_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    admission = crud.get_admission(db, admission_id)
    if admission is None:
        raise HTTPException(status_code=404, detail="Admission not found")
    return _to_response(admission)


@router.post("/admissions/import", response_model=AdmissionImportResponse)
async def import_admissions(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are accepted")
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        result = crud.import_from_excel(get_db_path(), tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return AdmissionImportResponse(**result)


@router.patch("/admissions/{admission_id}", response_model=AdmissionResponse)
def update_admission(
    admission_id: str,
    body: AdmissionUpdate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    admission = crud.get_admission(db, admission_id)
    if admission is None:
        raise HTTPException(status_code=404, detail="Admission not found")
    if not current_user.is_admin and admission.reviewer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only admin or assigned reviewer can update")

    updates = {}
    if body.reviewer_id is not None:
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Only admin can assign reviewers")
        reviewer = get_user_by_id(db, body.reviewer_id)
        if reviewer is None:
            raise HTTPException(status_code=400, detail="Reviewer user not found")
        updates["reviewer_id"] = body.reviewer_id
        updates["status"] = "reviewing"
    if body.review_notes is not None:
        updates["review_notes"] = body.review_notes

    updated = crud.update_admission(db, admission_id, **updates)
    return _to_response(updated)


@router.post("/admissions/{admission_id}/accept", response_model=AdmissionResponse)
def accept_admission(
    admission_id: str,
    body: AdmissionAcceptRequest = AdmissionAcceptRequest(),
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    admission = crud.get_admission(db, admission_id)
    if admission is None:
        raise HTTPException(status_code=404, detail="Admission not found")
    if admission.status not in ("submitted", "reviewing"):
        raise HTTPException(status_code=400, detail=f"Cannot accept admission with status {admission.status!r}")
    if not current_user.is_admin and admission.reviewer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only admin or assigned reviewer can accept")
    updated = crud.accept_admission(db, admission_id, notes=body.notes)
    return _to_response(updated)


@router.post("/admissions/{admission_id}/reject", response_model=AdmissionResponse)
def reject_admission(
    admission_id: str,
    body: AdmissionRejectRequest,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    admission = crud.get_admission(db, admission_id)
    if admission is None:
        raise HTTPException(status_code=404, detail="Admission not found")
    if admission.status not in ("submitted", "reviewing", "accepted"):
        raise HTTPException(status_code=400, detail=f"Cannot reject admission with status {admission.status!r}")
    if not current_user.is_admin and admission.reviewer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only admin or assigned reviewer can reject")
    updated = crud.reject_admission(db, admission_id, notes=body.notes)
    return _to_response(updated)


@router.delete("/admissions/{admission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admission(
    admission_id: str,
    current_user: User = Depends(require_admin),
):
    db = get_db_path()
    if not crud.delete_admission(db, admission_id):
        raise HTTPException(status_code=404, detail="Admission not found")


@router.post("/admissions/{admission_id}/financial-aid", response_model=AdmissionResponse)
def set_financial_aid(
    admission_id: str,
    body: FinancialAidRequest,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    admission = crud.get_admission(db, admission_id)
    if admission is None:
        raise HTTPException(status_code=404, detail="Admission not found")
    if not current_user.is_admin and admission.reviewer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only admin or assigned reviewer can set financial aid")
    try:
        updated = crud.set_financial_aid(
            db, admission_id, aid_percentage=body.aid_percentage, notes=body.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _to_response(updated)
