"""CRUD operations for Admission entities and Excel import."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Admission
from .projects import create_project


def _row_to_admission(row) -> Admission:
    return Admission(
        id=row["id"],
        form_submission_id=row["form_submission_id"],
        applicant_name=row["applicant_name"],
        supervisor=row["supervisor"],
        email=row["email"],
        phone=row["phone"],
        university=row["university"],
        department=row["department"],
        service_areas=row["service_areas"],
        modas_members=row["modas_members"],
        grant_context=row["grant_context"],
        comments=row["comments"],
        status=row["status"],
        reviewer_id=row["reviewer_id"],
        review_notes=row["review_notes"],
        reviewed_at=row["reviewed_at"],
        created_project_id=row["created_project_id"],
        aid_percentage=row["aid_percentage"],
        aid_notes=row["aid_notes"],
        aid_at=row["aid_at"],
        imported_at=row["imported_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_admission(
    db_path: Path,
    applicant_name: str,
    email: str,
    service_areas: str,
    modas_members: str,
    form_submission_id: int | None = None,
    supervisor: str | None = None,
    phone: str | None = None,
    university: str | None = None,
    department: str | None = None,
    grant_context: str | None = None,
    comments: str | None = None,
) -> Admission:
    admission_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO admissions
               (id, form_submission_id, applicant_name, supervisor, email, phone,
                university, department, service_areas, modas_members,
                grant_context, comments, status, imported_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?)""",
            (
                admission_id, form_submission_id, applicant_name, supervisor, email, phone,
                university, department, service_areas, modas_members,
                grant_context, comments, now, now, now,
            ),
        )
    return get_admission(db_path, admission_id)


def get_admission(db_path: Path, admission_id: str) -> Admission | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM admissions WHERE id = ?", (admission_id,)
        ).fetchone()
    return _row_to_admission(row) if row else None


def list_admissions(
    db_path: Path, status: str | None = None
) -> list[Admission]:
    with get_db(db_path) as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM admissions WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM admissions ORDER BY created_at DESC"
            ).fetchall()
    return [_row_to_admission(r) for r in rows]


def update_admission(
    db_path: Path,
    admission_id: str,
    reviewer_id: str | None = None,
    review_notes: str | None = None,
    status: str | None = None,
) -> Admission:
    existing = get_admission(db_path, admission_id)
    if existing is None:
        raise ValueError(f"Admission {admission_id!r} not found")
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        parts = ["updated_at = ?"]
        params = [now]
        if reviewer_id is not None:
            parts.append("reviewer_id = ?")
            params.append(reviewer_id)
        if review_notes is not None:
            parts.append("review_notes = ?")
            params.append(review_notes)
        if status is not None:
            parts.append("status = ?")
            params.append(status)
        params.append(admission_id)
        conn.execute(
            f"UPDATE admissions SET {', '.join(parts)} WHERE id = ?", params
        )
    return get_admission(db_path, admission_id)


def set_reviewer(db_path: Path, admission_id: str, reviewer_id: str) -> Admission:
    return update_admission(
        db_path, admission_id, reviewer_id=reviewer_id, status="reviewing"
    )


def accept_admission(db_path: Path, admission_id: str, notes: str | None = None) -> Admission:
    admission = get_admission(db_path, admission_id)
    if admission is None:
        raise ValueError(f"Admission {admission_id!r} not found")
    reviewer_id = admission.reviewer_id
    now = datetime.now(UTC).isoformat()

    project = create_project(
        db_path,
        name=f"{admission.applicant_name}",
        created_by=reviewer_id,
        description=admission.comments,
    )

    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE admissions
               SET status = 'accepted', review_notes = ?,
                   reviewed_at = ?, created_project_id = ?, updated_at = ?
               WHERE id = ?""",
            (notes, now, project.id, now, admission_id),
        )
    return get_admission(db_path, admission_id)


def reject_admission(db_path: Path, admission_id: str, notes: str) -> Admission:
    admission = get_admission(db_path, admission_id)
    if admission is None:
        raise ValueError(f"Admission {admission_id!r} not found")
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE admissions
               SET status = 'rejected', review_notes = ?, reviewed_at = ?, updated_at = ?
               WHERE id = ?""",
            (notes, now, now, admission_id),
        )
    return get_admission(db_path, admission_id)


def delete_admission(db_path: Path, admission_id: str) -> bool:
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM admissions WHERE id = ?", (admission_id,))
    return cur.rowcount > 0


def admission_exists_by_form_id(db_path: Path, form_submission_id: int) -> bool:
    if form_submission_id is None:
        return False
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM admissions WHERE form_submission_id = ?",
            (form_submission_id,),
        ).fetchone()
    return row is not None


def _cell_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def import_from_excel(db_path: Path, file_path: Path) -> dict:
    """Parse an Excel file and create admission records. Returns import stats."""
    import openpyxl

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(min_row=2, values_only=True))
    now = datetime.now(UTC).isoformat()
    imported = 0
    skipped = 0
    created_ids = []

    with get_db(db_path) as conn:
        for row in rows:
            if not row or not any(row):
                continue

            form_id = row[0] if len(row) > 0 else None
            if isinstance(form_id, (int, float)):
                form_id = int(form_id)
            else:
                form_id = None

            if form_id is not None and admission_exists_by_form_id(db_path, form_id):
                skipped += 1
                continue

            applicant_name = _cell_str(row[5]) if len(row) > 5 else ""
            supervisor = _cell_str(row[6]) if len(row) > 6 else ""
            email = _cell_str(row[7]) if len(row) > 7 else ""
            phone = _cell_str(row[8]) if len(row) > 8 else ""
            university = _cell_str(row[9]) if len(row) > 9 else ""
            department = _cell_str(row[10]) if len(row) > 10 else ""
            service_areas = _cell_str(row[11]) if len(row) > 11 else ""
            modas_members = _cell_str(row[12]) if len(row) > 12 else ""
            grant_context = _cell_str(row[13]) if len(row) > 13 else ""
            comments = _cell_str(row[14]) if len(row) > 14 else ""

            if not applicant_name:
                skipped += 1
                continue

            admission_id = uuid.uuid4().hex
            conn.execute(
                """INSERT INTO admissions
                   (id, form_submission_id, applicant_name, supervisor, email, phone,
                    university, department, service_areas, modas_members,
                    grant_context, comments, status, imported_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?)""",
                (
                    admission_id, form_id, applicant_name, supervisor, email, phone,
                    university, department, service_areas, modas_members,
                    grant_context, comments, now, now, now,
                ),
            )
            created_ids.append(admission_id)
            imported += 1

        conn.commit()

    wb.close()
    return {
        "imported": imported,
        "skipped": skipped,
        "admission_ids": created_ids,
    }


def set_financial_aid(
    db_path: Path,
    admission_id: str,
    aid_percentage: float,
    notes: str | None = None,
) -> Admission:
    admission = get_admission(db_path, admission_id)
    if admission is None:
        raise ValueError(f"Admission {admission_id!r} not found")
    if admission.status != "accepted":
        raise ValueError(
            f"Cannot set financial aid for admission with status {admission.status!r}"
        )
    if aid_percentage < 0 or aid_percentage > 100:
        raise ValueError("aid_percentage must be between 0 and 100")
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE admissions SET aid_percentage = ?, aid_notes = ?, aid_at = ?, updated_at = ? WHERE id = ?",
            (aid_percentage, notes, now, now, admission_id),
        )
    return get_admission(db_path, admission_id)
