"""Academic supervision routes: assignments, weekly reports, meetings, journeys."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ...crud import supervision as supervision_crud
from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user, require_admin
from ..schemas import (
    AttendanceRequest,
    AttendanceResponse,
    ExtensionRequest,
    ExtensionResponse,
    JourneyRequest,
    JourneyResponse,
    MeetingSettingRequest,
    MeetingSettingResponse,
    ReportItemRequest,
    ReportItemResponse,
    ReportSummaryRequest,
    RequirementRequest,
    RequirementResponse,
    ReviewRequest,
    SupervisorAssignmentResponse,
    SupervisorAssignRequest,
    WeeklyReportResponse,
)

router = APIRouter()


def _week_start(d: date | None = None) -> str:
    """ISO Monday of the week containing d (default today)."""
    d = d or date.today()
    return (d - timedelta(days=d.weekday())).isoformat()


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


# ── Supervisor assignments ───────────────────────────────────────────────────


@router.post("/assignments", response_model=SupervisorAssignmentResponse, status_code=201)
def assign_supervisor(
    body: SupervisorAssignRequest,
    current_user: User = Depends(get_current_user),
):
    """Assign a supervisor to a student. Admin, the professor themselves, or an existing supervisor."""
    if not (
        current_user.is_admin
        or current_user.id == body.professor_id
        or current_user.role == "professor"
    ):
        raise HTTPException(status_code=403, detail="Not permitted to assign supervisors")
    try:
        assignment = supervision_crud.assign_supervisor(
            get_db_path(), body.student_id, body.professor_id, body.active_from
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return SupervisorAssignmentResponse(
        id=assignment.id,
        student_id=assignment.student_id,
        professor_id=assignment.professor_id,
        active_from=assignment.active_from,
        active_until=assignment.active_until,
        created_at=assignment.created_at,
    )


@router.delete("/assignments/{assignment_id}", status_code=204)
def end_assignment(assignment_id: str, _admin: User = Depends(require_admin)):
    if not supervision_crud.end_supervisor_assignment(get_db_path(), assignment_id):
        raise HTTPException(status_code=404, detail="Assignment not found or already ended")


@router.get("/assignments", response_model=list[SupervisorAssignmentResponse])
def list_assignments(
    professor_id: str | None = Query(default=None),
    _user: User = Depends(get_current_user),
):
    db = get_db_path()
    if professor_id:
        rows = supervision_crud.list_students_of_professor(db, professor_id)
    else:
        rows = supervision_crud.list_supervisor_assignments(db)
    return [
        SupervisorAssignmentResponse(
            id=a.id,
            student_id=a.student_id,
            professor_id=a.professor_id,
            active_from=a.active_from,
            active_until=a.active_until,
            created_at=a.created_at,
        )
        for a in rows
    ]


@router.get("/my-students", response_model=list[SupervisorAssignmentResponse])
def my_students(current_user: User = Depends(get_current_user)):
    rows = supervision_crud.list_students_of_professor(get_db_path(), current_user.id)
    return [
        SupervisorAssignmentResponse(
            id=a.id,
            student_id=a.student_id,
            professor_id=a.professor_id,
            active_from=a.active_from,
            active_until=a.active_until,
            created_at=a.created_at,
        )
        for a in rows
    ]


@router.get("/my-supervisor", response_model=SupervisorAssignmentResponse | None)
def my_supervisor(current_user: User = Depends(get_current_user)):
    a = supervision_crud.get_active_supervisor(get_db_path(), current_user.id)
    if not a:
        return None
    return SupervisorAssignmentResponse(
        id=a.id,
        student_id=a.student_id,
        professor_id=a.professor_id,
        active_from=a.active_from,
        active_until=a.active_until,
        created_at=a.created_at,
    )


# ── Weekly meeting settings ──────────────────────────────────────────────────


@router.post("/meeting-settings", response_model=MeetingSettingResponse, status_code=201)
def set_meeting_time(
    body: MeetingSettingRequest, current_user: User = Depends(get_current_user)
):
    if not (current_user.is_admin or current_user.role == "professor"):
        raise HTTPException(status_code=403, detail="Only professors can set meeting times")
    setting = supervision_crud.upsert_meeting_setting(
        get_db_path(),
        current_user.id,
        body.weekday,
        body.time_local,
        body.timezone,
        body.effective_from,
    )
    return MeetingSettingResponse(
        id=setting.id,
        professor_id=setting.professor_id,
        weekday=setting.weekday,
        time_local=setting.time_local,
        timezone=setting.timezone,
        effective_from=setting.effective_from,
        created_at=setting.created_at,
    )


@router.get("/meeting-settings", response_model=MeetingSettingResponse | None)
def get_meeting_setting(
    week: str | None = Query(default=None),
    professor_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    pid = professor_id or current_user.id
    week_start = week or _week_start()
    setting = supervision_crud.get_meeting_setting_for_week(get_db_path(), pid, week_start)
    if not setting:
        return None
    return MeetingSettingResponse(
        id=setting.id,
        professor_id=setting.professor_id,
        weekday=setting.weekday,
        time_local=setting.time_local,
        timezone=setting.timezone,
        effective_from=setting.effective_from,
        created_at=setting.created_at,
    )


# ── Weekly reports (student) ─────────────────────────────────────────────────


@router.get("/reports", response_model=list[WeeklyReportResponse])
def list_reports(
    student_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    review_status: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    # Students can only see their own reports
    if current_user.role == "student" and not current_user.is_admin:
        student_id = current_user.id
    elif student_id is None and current_user.role == "professor":
        student_ids = [
            a.student_id
            for a in supervision_crud.list_students_of_professor(db, current_user.id)
        ]
        rows = []
        for sid in student_ids:
            rows.extend(
                supervision_crud.list_reports(
                    db,
                    student_id=sid,
                    status=status_filter,
                    review_status=review_status,
                    risk_level=risk_level,
                    date_from=date_from,
                    date_to=date_to,
                )
            )
        return [_report_to_response(db, r) for r in rows]

    rows = supervision_crud.list_reports(
        db,
        student_id=student_id,
        status=status_filter,
        review_status=review_status,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
    )
    return [_report_to_response(db, r) for r in rows]


@router.get("/reports/{report_id}", response_model=WeeklyReportResponse)
def get_report(report_id: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    report = supervision_crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if current_user.role == "student" and not current_user.is_admin and report.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your report")
    return _report_to_response(db, report)


@router.post("/weekly/current", response_model=WeeklyReportResponse)
def get_or_create_current_week(
    week: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    student_id = current_user.id
    if current_user.role == "professor" and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Professors review reports; students submit them")
    week_start = week or _week_start()
    report = supervision_crud.get_or_create_report(get_db_path(), student_id, week_start)
    return _report_to_response(get_db_path(), report)


@router.put("/reports/{report_id}/summary", response_model=WeeklyReportResponse)
def update_summary(
    report_id: str,
    body: ReportSummaryRequest,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    report = supervision_crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.student_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only the student can edit this report")
    if report.status == "submitted":
        raise HTTPException(status_code=409, detail="Report already submitted")
    updated = supervision_crud.update_report_summary(
        db,
        report_id,
        body.accomplished,
        body.next_focus,
        body.support_requested,
    )
    return _report_to_response(db, updated)


@router.put("/reports/{report_id}/items", response_model=ReportItemResponse)
def upsert_item(
    report_id: str,
    body: ReportItemRequest,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    report = supervision_crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.student_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only the student can edit this report")
    if report.status == "submitted":
        raise HTTPException(status_code=409, detail="Report already submitted")
    item = supervision_crud.upsert_report_item(
        db,
        report_id,
        body.item_title,
        item_id=body.item_id,
        task_id=body.task_id,
        publication_id=body.publication_id,
        experiment_id=body.experiment_id,
        item_kind=body.item_kind,
        progress_pct=body.progress_pct,
        status=body.status,
        blocker=body.blocker,
        needs_help=body.needs_help,
        what_changed=body.what_changed,
        next_step=body.next_step,
        risk_level=body.risk_level,
        next_deadline=body.next_deadline,
        sort_order=body.sort_order,
    )
    return ReportItemResponse(
        id=item.id,
        report_id=item.report_id,
        task_id=item.task_id,
        publication_id=item.publication_id,
        experiment_id=item.experiment_id,
        item_title=item.item_title,
        item_kind=item.item_kind,
        progress_pct=item.progress_pct,
        status=item.status,
        blocker=item.blocker,
        needs_help=item.needs_help,
        what_changed=item.what_changed,
        next_step=item.next_step,
        risk_level=item.risk_level,
        next_deadline=item.next_deadline,
        sort_order=item.sort_order,
    )


@router.delete("/reports/{report_id}/items/{item_id}", status_code=204)
def delete_item(
    report_id: str,
    item_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    report = supervision_crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.student_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only the student can edit this report")
    if report.status == "submitted":
        raise HTTPException(status_code=409, detail="Report already submitted")
    supervision_crud.delete_report_item(db, item_id)


@router.post("/reports/{report_id}/submit", response_model=WeeklyReportResponse)
def submit(report_id: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    report = supervision_crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.student_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only the student can submit this report")
    if report.status == "submitted":
        raise HTTPException(status_code=409, detail="Report already submitted")
    updated = supervision_crud.submit_report(db, report_id)
    return _report_to_response(db, updated)


@router.post("/reports/{report_id}/review", response_model=WeeklyReportResponse)
def review(
    report_id: str,
    body: ReviewRequest,
    current_user: User = Depends(get_current_user),
):
    if not (current_user.is_admin or current_user.role == "professor"):
        raise HTTPException(status_code=403, detail="Only professors can review reports")
    db = get_db_path()
    report = supervision_crud.get_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    # Only the student's own supervisor reviews (any professor could before).
    if not current_user.is_admin:
        from .followups import is_supervisor

        if not is_supervisor(db, current_user.id, report.student_id):
            raise HTTPException(status_code=403, detail="Only this student's supervisor can review the report")
    if body.followups:
        from ...crud.followups import create_followups

        create_followups(
            db, student_id=report.student_id, professor_id=current_user.id, report_id=report_id,
            items=[(f.text, f.due_date) for f in body.followups],
        )
    updated = supervision_crud.review_report(
        db,
        report_id,
        current_user.id,
        body.review_status,
        body.feedback,
        body.risk_override,
    )
    return _report_to_response(db, updated)


# ── Meeting attendance & extensions ──────────────────────────────────────────


@router.post("/attendance", response_model=AttendanceResponse)
def record_attendance(
    body: AttendanceRequest,
    student_id: str = Query(...),
    week: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    if not (current_user.is_admin or current_user.role == "professor"):
        raise HTTPException(status_code=403, detail="Only professors record attendance")
    week_start = week or _week_start()
    att = supervision_crud.upsert_attendance(
        get_db_path(), current_user.id, student_id, week_start, body.status, body.joined_mode, body.note
    )
    return AttendanceResponse(
        id=att.id,
        professor_id=att.professor_id,
        student_id=att.student_id,
        week_start=att.week_start,
        status=att.status,
        joined_mode=att.joined_mode,
        note=att.note,
        recorded_at=att.recorded_at,
    )


@router.get("/attendance", response_model=AttendanceResponse | None)
def get_attendance(
    student_id: str = Query(...),
    week: str | None = Query(default=None),
    _user: User = Depends(get_current_user),
):
    week_start = week or _week_start()
    att = supervision_crud.get_attendance(get_db_path(), student_id, week_start)
    if not att:
        return None
    return AttendanceResponse(
        id=att.id,
        professor_id=att.professor_id,
        student_id=att.student_id,
        week_start=att.week_start,
        status=att.status,
        joined_mode=att.joined_mode,
        note=att.note,
        recorded_at=att.recorded_at,
    )


@router.post("/extensions", response_model=ExtensionResponse, status_code=201)
def grant_extension(
    body: ExtensionRequest,
    student_id: str = Query(...),
    week: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    if not (current_user.is_admin or current_user.role == "professor"):
        raise HTTPException(status_code=403, detail="Only professors grant extensions")
    week_start = week or _week_start()
    ext = supervision_crud.grant_extension(
        get_db_path(),
        student_id,
        current_user.id,
        week_start,
        body.new_deadline,
        body.reason,
    )
    return ExtensionResponse(
        id=ext.id,
        student_id=ext.student_id,
        professor_id=ext.professor_id,
        week_start=ext.week_start,
        new_deadline=ext.new_deadline,
        reason=ext.reason,
        created_at=ext.created_at,
        report_id=ext.report_id,
    )


# ── Journeys and graduation requirements ──────────────────────────────────────────


@router.post("/journeys", response_model=JourneyResponse, status_code=201)
def create_journey(
    body: JourneyRequest,
    student_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    sid = student_id or current_user.id
    if sid != current_user.id and not current_user.is_admin:
        # Only this student's own supervisor (any professor could before).
        from .followups import is_supervisor

        if not (current_user.role == "professor" and is_supervisor(get_db_path(), current_user.id, sid)):
            raise HTTPException(status_code=403, detail="Not permitted")
    j = supervision_crud.create_journey(
        get_db_path(),
        sid,
        body.level,
        body.status,
        programme=body.programme,
        university=body.university,
        department=body.department,
        start_year=body.start_year,
        start_date=body.start_date,
        expected_end=body.expected_end,
        thesis_title=body.thesis_title,
    )
    return JourneyResponse(
        id=j.id,
        student_id=j.student_id,
        level=j.level,
        status=j.status,
        programme=j.programme,
        university=j.university,
        department=j.department,
        start_year=j.start_year,
        start_date=j.start_date,
        expected_end=j.expected_end,
        thesis_title=j.thesis_title,
        created_at=j.created_at,
        updated_at=j.updated_at,
    )


@router.get("/journeys", response_model=list[JourneyResponse])
def list_journeys(
    student_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    sid = student_id or current_user.id
    if sid != current_user.id and not (current_user.is_admin or current_user.role == "professor"):
        raise HTTPException(status_code=403, detail="Not permitted")
    rows = supervision_crud.list_journeys(get_db_path(), sid)
    return [
        JourneyResponse(
            id=j.id,
            student_id=j.student_id,
            level=j.level,
            status=j.status,
            programme=j.programme,
            university=j.university,
            department=j.department,
            start_year=j.start_year,
            start_date=j.start_date,
            expected_end=j.expected_end,
            thesis_title=j.thesis_title,
            created_at=j.created_at,
            updated_at=j.updated_at,
        )
        for j in rows
    ]


@router.post("/requirements", response_model=RequirementResponse, status_code=201)
def create_requirement(
    body: RequirementRequest,
    _admin: User = Depends(require_admin),
):
    r = supervision_crud.create_requirement(
        get_db_path(),
        body.level,
        body.title,
        body.req_type,
        body.target_value,
        description=body.description,
        research_item_type=body.research_item_type,
        min_stage=body.min_stage,
        unit=body.unit,
        required=body.required,
    )
    return RequirementResponse(
        id=r.id,
        level=r.level,
        title=r.title,
        description=r.description,
        req_type=r.req_type,
        research_item_type=r.research_item_type,
        min_stage=r.min_stage,
        target_value=r.target_value,
        unit=r.unit,
        required=r.required,
        active=r.active,
        created_at=r.created_at,
    )


@router.get("/requirements", response_model=list[RequirementResponse])
def list_requirements(
    level: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    _user: User = Depends(get_current_user),
):
    rows = supervision_crud.list_requirements(get_db_path(), level, active_only)
    return [
        RequirementResponse(
            id=r.id,
            level=r.level,
            title=r.title,
            description=r.description,
            req_type=r.req_type,
            research_item_type=r.research_item_type,
            min_stage=r.min_stage,
            target_value=r.target_value,
            unit=r.unit,
            required=r.required,
            active=r.active,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.delete("/requirements/{requirement_id}", status_code=204)
def archive_requirement(requirement_id: str, _admin: User = Depends(require_admin)):
    if not supervision_crud.archive_requirement(get_db_path(), requirement_id):
        raise HTTPException(status_code=404, detail="Requirement not found")


# ── Research items (unified view) ────────────────────────────────────────────


@router.get("/research-items")
def list_research_items(
    student_id: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """Unified research pipeline: publications, experiments, and grants as one list.

    Optional ``student_id`` filters to work created by that user (or projects
    they own). Students always see only their own items.
    """
    db = get_db_path()
    if current_user.role == "student" and not current_user.is_admin:
        student_id = current_user.id

    items: list[dict] = []

    with get_db(db) as conn:
        pub_sql = """SELECT id, title, status, venue, venue_type, doi, created_by,
                            created_at, updated_at, project_id
                     FROM publications"""
        pub_params: list = []
        if student_id:
            pub_sql += " WHERE created_by = ?"
            pub_params.append(student_id)
        for r in conn.execute(pub_sql, pub_params):
            items.append(
                {
                    "id": r["id"],
                    "kind": "patent" if r["venue_type"] == "patent" else "publication",
                    "title": r["title"],
                    "status": r["status"],
                    "stage": r["status"],
                    "venue": r["venue"],
                    "owner_id": r["created_by"],
                    "project_id": r["project_id"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "link_path": f"/publications/{r['id']}",
                }
            )

        exp_sql = """SELECT e.id, e.name, e.status, e.hypothesis, e.deadline,
                            e.created_by, e.created_at, e.updated_at, e.project_id
                     FROM experiments e"""
        exp_params: list = []
        if student_id:
            exp_sql += " WHERE e.created_by = ?"
            exp_params.append(student_id)
        for r in conn.execute(exp_sql, exp_params):
            items.append(
                {
                    "id": r["id"],
                    "kind": "experiment",
                    "title": r["name"],
                    "status": r["status"],
                    "stage": r["status"],
                    "venue": None,
                    "owner_id": r["created_by"],
                    "project_id": r["project_id"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "link_path": f"/projects/{r['project_id']}/experiments",
                    "deadline": r["deadline"],
                }
            )

        grant_sql = """SELECT id, title, funder, status, created_by,
                              created_at, updated_at
                       FROM grants"""
        grant_params: list = []
        if student_id:
            grant_sql += " WHERE created_by = ?"
            grant_params.append(student_id)
        for r in conn.execute(grant_sql, grant_params):
            items.append(
                {
                    "id": r["id"],
                    "kind": "grant",
                    "title": r["title"],
                    "status": r["status"],
                    "stage": r["status"],
                    "venue": r["funder"],
                    "owner_id": r["created_by"],
                    "project_id": None,
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "link_path": f"/grants/{r['id']}",
                }
            )

    if kind:
        items = [i for i in items if i["kind"] == kind]
    items.sort(key=lambda i: i.get("updated_at") or i.get("created_at") or "", reverse=True)
    return items


# ── Student readiness ────────────────────────────────────────────────────────


@router.get("/readiness")
def graduation_readiness(
    student_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """Compute graduation readiness against active requirements for the student's level."""
    db = get_db_path()
    sid = student_id or current_user.id
    if sid != current_user.id and not current_user.is_admin:
        # Only this student's own supervisor (any professor could look before).
        from .followups import is_supervisor

        if not (current_user.role == "professor" and is_supervisor(db, current_user.id, sid)):
            raise HTTPException(status_code=403, detail="Not permitted")

    journey = supervision_crud.get_active_journey(db, sid)
    if not journey:
        journeys = supervision_crud.list_journeys(db, sid)
        journey = journeys[0] if journeys else None
    level = journey.level if journey else None

    requirements = (
        supervision_crud.list_requirements(db, level, True) if level else []
    )

    # Evidence counts — publication output only. Course credits and GPA are not
    # tracked here on purpose: this platform is for publication work, and the
    # registrar owns the transcript.
    pub_count = 0
    journal_count = 0
    conf_count = 0

    with get_db(db) as conn:
        if level:
            rows = conn.execute(
                """SELECT venue_type, status FROM publications WHERE created_by = ?""",
                (sid,),
            ).fetchall()
            for r in rows:
                if r["status"] in ("submitted", "accepted", "published", "reviewing"):
                    pub_count += 1
                    if r["venue_type"] == "journal":
                        journal_count += 1
                    elif r["venue_type"] in ("conference", "workshop"):
                        conf_count += 1

    results = []
    for req in requirements:
        met = False
        current = 0.0
        if req.req_type == "research_item":
            if req.research_item_type == "Journal Paper":
                current = float(journal_count)
            elif req.research_item_type == "Conference Paper":
                current = float(conf_count)
            else:
                current = float(pub_count)
            met = current >= req.target_value
        elif req.req_type == "milestone":
            # Milestones require human confirmation — stay incomplete until marked
            current = 0.0
            met = False
        else:
            current = 0.0
            met = False
        results.append(
            {
                "id": req.id,
                "level": req.level,
                "title": req.title,
                "req_type": req.req_type,
                "research_item_type": req.research_item_type,
                "target_value": req.target_value,
                "unit": req.unit,
                "current_value": current,
                "required": req.required,
                "met": met,
            }
        )

    required = [r for r in results if r["required"]]
    met_required = sum(1 for r in required if r["met"])
    pct = int(met_required / len(required) * 100) if required else 0

    return {
        "student_id": sid,
        "level": level,
        "journey_id": journey.id if journey else None,
        "thesis_title": journey.thesis_title if journey else None,
        "readiness_pct": pct,
        "requirements": results,
        "summary": {
            "publications": pub_count,
            "journal_papers": journal_count,
            "conference_papers": conf_count,
        },
        "publication_gap": _publication_gap(db, sid, journey, results),
    }


_COUNTED = ("submitted", "reviewing", "accepted", "published")
_VENUES = {"Journal Paper": ("journal",), "Conference Paper": ("conference", "workshop")}


def _journey_start(journey) -> date | None:
    if journey is None:
        return None
    if journey.start_date:
        return _parse_date(journey.start_date)
    if journey.start_year:
        return date(int(journey.start_year), 9, 1)  # academic year start
    return None


def _publication_gap(db, sid: str, journey, results: list[dict]) -> dict:
    """How far the student is from each publication requirement, the drafts that
    could close the gap, and — only when there is a real basis — when at the
    current pace. The pace is papers submitted since the journey began divided by
    the months elapsed; with no start date or nothing submitted yet there is no
    estimate rather than a guess."""
    start = _journey_start(journey)
    with get_db(db) as conn:
        pubs = conn.execute(
            "SELECT id, title, venue_type, status, submitted_at, created_at FROM publications WHERE created_by = ?",
            (sid,),
        ).fetchall()
    months = None
    pace = None
    if start is not None:
        months = max(1, (date.today() - start).days // 30)
        submitted = [p for p in pubs if p["status"] in _COUNTED
                     and (p["submitted_at"] or p["created_at"])[:10] >= start.isoformat()]
        pace = round(len(submitted) / months, 3) if submitted else None
    items = []
    for r in results:
        if r["req_type"] != "research_item" or r["met"]:
            continue
        gap = max(0, int(r["target_value"] - r["current_value"]))
        venues = _VENUES.get(r.get("research_item_type") or "")
        drafts = [{"id": p["id"], "title": p["title"], "status": p["status"]} for p in pubs
                  if p["status"] == "draft" and (venues is None or p["venue_type"] in venues)]
        items.append({
            "requirement": r["title"], "target": r["target_value"], "current": r["current_value"], "gap": gap,
            "in_progress": drafts,
            "eta_months": round(gap / pace) if pace else None,
        })
    return {"pace_per_month": pace, "months_observed": months, "items": items}


# ── Professor analytics ──────────────────────────────────────────────────────


@router.get("/analytics/professor")
def professor_analytics(current_user: User = Depends(get_current_user)):
    """Group overview for professors: KPIs, weekly trend, workload, attention list."""
    if not (current_user.is_admin or current_user.role == "professor"):
        raise HTTPException(status_code=403, detail="Professor analytics only")
    db = get_db_path()
    assignments = supervision_crud.list_students_of_professor(db, current_user.id)
    student_ids = [a.student_id for a in assignments]
    if not student_ids:
        return _empty_analytics()

    # Usernames for display
    names: dict[str, str] = {}
    with get_db(db) as conn:
        for row in conn.execute(
            f"SELECT id, username FROM users WHERE id IN ({','.join('?' * len(student_ids))})",
            student_ids,
        ):
            names[row["id"]] = row["username"]

        # KPIs — current week + rolling 8 weeks
        week_start = _week_start()
        submitted_week = conn.execute(
            f"""SELECT COUNT(*) FROM weekly_reports
                WHERE student_id IN ({','.join('?' * len(student_ids))})
                  AND week_start = ? AND status = 'submitted'""",
            (*student_ids, week_start),
        ).fetchone()[0]
        needs_review = conn.execute(
            f"""SELECT COUNT(*) FROM weekly_reports
                WHERE student_id IN ({','.join('?' * len(student_ids))})
                  AND review_status IN ('pending', 'needs_review')""",
            student_ids,
        ).fetchone()[0]
        draft_or_missing = conn.execute(
            f"""SELECT COUNT(*) FROM weekly_reports
                WHERE student_id IN ({','.join('?' * len(student_ids))})
                  AND week_start = ? AND status = 'draft'""",
            (*student_ids, week_start),
        ).fetchone()[0]
        help_requests = conn.execute(
            f"""SELECT COUNT(*) FROM weekly_report_items i
                JOIN weekly_reports r ON r.id = i.report_id
                WHERE r.student_id IN ({','.join('?' * len(student_ids))})
                  AND i.needs_help = 1 AND r.status = 'submitted'""",
            student_ids,
        ).fetchone()[0]
        high_risk = conn.execute(
            f"""SELECT COUNT(*) FROM weekly_reports
                WHERE student_id IN ({','.join('?' * len(student_ids))})
                  AND COALESCE(risk_override, risk_level) IN ('high', 'critical')
                  AND status = 'submitted'""",
            student_ids,
        ).fetchone()[0]

        # Weekly trend — submitted reports per week, last 8 weeks
        trend_rows = conn.execute(
            f"""SELECT week_start, COUNT(*) as cnt,
                       SUM(CASE WHEN submitted_at IS NOT NULL THEN 1 ELSE 0 END) as on_time
                FROM weekly_reports
                WHERE student_id IN ({','.join('?' * len(student_ids))})
                  AND week_start >= date(?, '-56 days')
                GROUP BY week_start ORDER BY week_start""",
            (*student_ids, week_start),
        ).fetchall()
        trend = [
            {"week": r["week_start"], "submitted": r["cnt"], "on_time": r["on_time"]}
            for r in trend_rows
        ]

        # Attendance breakdown (last 8 weeks)
        att_rows = conn.execute(
            f"""SELECT status, COUNT(*) as cnt FROM meeting_attendance
                WHERE student_id IN ({','.join('?' * len(student_ids))})
                  AND week_start >= date(?, '-56 days')
                GROUP BY status""",
            (*student_ids, week_start),
        ).fetchall()
        attendance = {r["status"]: r["cnt"] for r in att_rows}

        # Per-student workload
        workload = []
        for sid in student_ids:
            open_reports = conn.execute(
                """SELECT COUNT(*) FROM weekly_reports
                   WHERE student_id = ? AND status = 'submitted'
                     AND review_status IN ('pending', 'needs_review')""",
                (sid,),
            ).fetchone()[0]
            helps = conn.execute(
                """SELECT COUNT(*) FROM weekly_report_items i
                   JOIN weekly_reports r ON r.id = i.report_id
                   WHERE r.student_id = ? AND i.needs_help = 1 AND r.status = 'submitted'""",
                (sid,),
            ).fetchone()[0]
            latest = conn.execute(
                """SELECT week_start, status FROM weekly_reports
                   WHERE student_id = ? ORDER BY week_start DESC LIMIT 1""",
                (sid,),
            ).fetchone()
            att = conn.execute(
                """SELECT status FROM meeting_attendance
                   WHERE student_id = ? ORDER BY week_start DESC LIMIT 1""",
                (sid,),
            ).fetchone()
            workload.append(
                {
                    "student_id": sid,
                    "username": names.get(sid, sid),
                    "open_reviews": open_reports,
                    "help_requests": helps,
                    "latest_week": latest["week_start"] if latest else None,
                    "latest_status": latest["status"] if latest else None,
                    "last_attendance": att["status"] if att else None,
                }
            )

        # Reports requiring attention (submitted, not closed, risk or help)
        attention_rows = conn.execute(
            f"""SELECT r.id, r.student_id, r.week_start, r.status, r.review_status,
                       COALESCE(r.risk_override, r.risk_level) as risk,
                       r.support_requested
                FROM weekly_reports r
                WHERE r.student_id IN ({','.join('?' * len(student_ids))})
                  AND r.status = 'submitted'
                  AND r.review_status IN ('pending', 'needs_review', 'changes_requested')
                ORDER BY r.week_start DESC LIMIT 20""",
            student_ids,
        ).fetchall()
        attention = [
            {
                "report_id": r["id"],
                "student_id": r["student_id"],
                "username": names.get(r["student_id"], r["student_id"]),
                "week_start": r["week_start"],
                "review_status": r["review_status"],
                "risk": r["risk"],
                "support_requested": r["support_requested"],
            }
            for r in attention_rows
        ]

        # Active deadlines — report item next_deadline still ahead or overdue
        deadline_rows = conn.execute(
            f"""SELECT i.item_title, i.next_deadline, i.progress_pct, i.status, r.student_id
                FROM weekly_report_items i
                JOIN weekly_reports r ON r.id = i.report_id
                WHERE r.student_id IN ({','.join('?' * len(student_ids))})
                  AND i.next_deadline IS NOT NULL AND i.next_deadline != ''
                  AND COALESCE(i.status, '') NOT IN ('done', 'completed')
                ORDER BY i.next_deadline ASC LIMIT 15""",
            student_ids,
        ).fetchall()
        deadlines = [
            {
                "item_title": d["item_title"],
                "next_deadline": d["next_deadline"],
                "progress_pct": d["progress_pct"],
                "status": d["status"],
                "student_id": d["student_id"],
                "username": names.get(d["student_id"], d["student_id"]),
            }
            for d in deadline_rows
        ]

        # Research mix from report items (item_kind)
        mix_rows = conn.execute(
            f"""SELECT COALESCE(i.item_kind, 'other') as kind, COUNT(*) as cnt
                FROM weekly_report_items i
                JOIN weekly_reports r ON r.id = i.report_id
                WHERE r.student_id IN ({','.join('?' * len(student_ids))})
                GROUP BY kind ORDER BY cnt DESC""",
            student_ids,
        ).fetchall()
        work_mix = [{"kind": r["kind"], "count": r["cnt"]} for r in mix_rows]

    return {
        "students": workload,
        "kpis": {
            "submitted_this_week": submitted_week,
            "needs_review": needs_review,
            "draft_or_missing": draft_or_missing,
            "help_requests": help_requests,
            "high_risk": high_risk,
            "student_count": len(student_ids),
        },
        "weekly_trend": trend,
        "attendance": attendance,
        "reports_needing_attention": attention,
        "active_deadlines": deadlines,
        "work_mix": work_mix,
    }


def _empty_analytics() -> dict:
    return {
        "students": [],
        "kpis": {
            "submitted_this_week": 0,
            "needs_review": 0,
            "draft_or_missing": 0,
            "help_requests": 0,
            "high_risk": 0,
            "student_count": 0,
        },
        "weekly_trend": [],
        "attendance": {},
        "reports_needing_attention": [],
        "active_deadlines": [],
        "work_mix": [],
    }


# ── Helpers ──────────────────────────────────────────────────────────────────


def _report_to_response(db, report) -> WeeklyReportResponse:
    items = supervision_crud.list_report_items(db, report.id)
    from ...crud.users import get_user_by_id

    student = get_user_by_id(db, report.student_id)
    return WeeklyReportResponse(
        id=report.id,
        student_id=report.student_id,
        student_name=student.username if student else None,
        week_start=report.week_start,
        status=report.status,
        review_status=report.review_status,
        risk_level=report.risk_level,
        risk_override=report.risk_override,
        accomplished=report.accomplished,
        next_focus=report.next_focus,
        support_requested=report.support_requested,
        submitted_at=report.submitted_at,
        reviewed_at=report.reviewed_at,
        reviewed_by=report.reviewed_by,
        feedback=report.feedback,
        created_at=report.created_at,
        updated_at=report.updated_at,
        items=[
            ReportItemResponse(
                id=i.id,
                report_id=i.report_id,
                task_id=i.task_id,
                publication_id=i.publication_id,
                experiment_id=i.experiment_id,
                item_title=i.item_title,
                item_kind=i.item_kind,
                progress_pct=i.progress_pct,
                status=i.status,
                blocker=i.blocker,
                needs_help=i.needs_help,
                what_changed=i.what_changed,
                next_step=i.next_step,
                risk_level=i.risk_level,
                next_deadline=i.next_deadline,
                sort_order=i.sort_order,
            )
            for i in items
        ],
    )


# ── Paper workspace: draft from research items, readiness, evidence ──────────


class DraftFromItemsRequest(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    experiment_ids: list[str] = Field(default_factory=list)
    publication_id: str | None = None
    venue_type: str = "journal"
    abstract: str | None = None
    link_sections: dict[str, str] | None = None  # experiment_id -> section


@router.post("/research-items/draft-paper", status_code=201)
def draft_paper_from_items(
    body: DraftFromItemsRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Create a paper from selected research items (use case 1).

    Pre-links the chosen experiments via ``publication_experiments`` so later
    section drafts use scoped evidence. Optionally kicks off a full AI draft.
    """
    from ...crud.publications import create_publication, link_experiment

    db = get_db_path()
    pub = create_publication(
        db,
        title=body.title,
        created_by=current_user.id,
        venue_type=body.venue_type,
        abstract=body.abstract or "Draft created from research items.",
    )
    for exp_id in body.experiment_ids:
        section = (body.link_sections or {}).get(exp_id)
        link_experiment(db, pub.id, exp_id, section)

    return {
        "publication_id": pub.id,
        "title": pub.title,
        "linked_experiments": body.experiment_ids,
        "status": "draft",
    }


@router.post("/papers/{pub_id}/link-items")
def link_items_to_paper(
    pub_id: str,
    body: DraftFromItemsRequest,
    current_user: User = Depends(get_current_user),
):
    """Attach more research items (experiments) to an existing paper."""
    from ...crud.publications import get_publication, link_experiment

    db = get_db_path()
    if not get_publication(db, pub_id):
        raise HTTPException(status_code=404, detail="Publication not found")
    for exp_id in body.experiment_ids:
        section = (body.link_sections or {}).get(exp_id)
        link_experiment(db, pub_id, exp_id, section)
    return {"publication_id": pub_id, "linked_experiments": body.experiment_ids}


@router.get("/papers/{pub_id}/readiness")
def paper_readiness(pub_id: str, current_user: User = Depends(get_current_user)):
    """Submit-readiness gate (use case 5).

    Checks linked evidence, abstract, AI provenance disclosure, and stage.
    Never blocks drafting — only informs the submit decision.
    """
    from ...crud.publications import (
        get_publication,
        list_linked_experiments,  # type: ignore
    )

    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    linked = list_linked_experiments(db, pub_id)
    exp_with_metrics = 0
    with get_db(db) as conn:
        for row in linked:
            n = conn.execute(
                "SELECT COUNT(*) FROM experiment_metrics WHERE experiment_id = ?",
                (row["experiment_id"],),
            ).fetchone()[0]
            if n:
                exp_with_metrics += 1
        ai_versions = conn.execute(
            """SELECT COUNT(*) FROM publication_versions
               WHERE publication_id = ? AND generated_by LIKE 'ai%'""",
            (pub_id,),
        ).fetchone()[0]
        human_versions = conn.execute(
            """SELECT COUNT(*) FROM publication_versions
               WHERE publication_id = ? AND (generated_by IS NULL OR generated_by NOT LIKE 'ai%')""",
            (pub_id,),
        ).fetchone()[0]
        # Ethics and funding live in their own modules; the gate reads them there
        # rather than duplicating the fact on the publication.
        irb = None
        if pub.project_id:
            irb = conn.execute(
                """SELECT protocol_number, institution, status, expiry_date
                   FROM irb_approvals
                   WHERE project_id = ? AND status = 'approved'
                   ORDER BY approval_date DESC, created_at DESC
                   LIMIT 1""",
                (pub.project_id,),
            ).fetchone()
        funded_grant = None
        if pub.project_id:
            funded_grant = conn.execute(
                """SELECT title, funder, status FROM grants
                   WHERE project_id = ? AND status IN ('awarded', 'active')
                   ORDER BY awarded_at DESC, created_at DESC
                   LIMIT 1""",
                (pub.project_id,),
            ).fetchone()

    checks = [
        {
            "id": "title",
            "label": "Title set and specific",
            "met": bool(pub.title) and not pub.title.startswith("Draft:"),
            "required": True,
            "detail": pub.title,
        },
        {
            "id": "abstract",
            "label": "Abstract written",
            "met": bool(pub.abstract) and len(pub.abstract) >= 80,
            "required": True,
            "detail": f"{len(pub.abstract or '')} chars",
        },
        {
            "id": "experiments",
            "label": "At least one linked experiment",
            "met": len(linked) >= 1,
            "required": True,
            "detail": f"{len(linked)} linked",
        },
        {
            "id": "metrics",
            "label": "Experiment evidence with metrics",
            "met": exp_with_metrics >= 1,
            "required": True,
            "detail": f"{exp_with_metrics} experiments have metrics",
        },
        {
            "id": "human_review",
            "label": "Human revision after AI draft",
            "met": human_versions >= 1,
            "required": True,
            "detail": f"{human_versions} human / {ai_versions} AI versions",
        },
        {
            "id": "provenance",
            "label": "AI provenance recorded for disclosure",
            "met": ai_versions >= 1,
            "required": False,
            "detail": f"{ai_versions} AI-generated versions with provenance",
        },
        {
            "id": "reporting_guideline",
            "label": "Reporting guideline declared",
            "met": bool((pub.reporting_guideline or "").strip()),
            "required": True,
            "detail": (pub.reporting_guideline or "").strip()
            or "state STROBE / CONSORT / PRISMA / TRIPOD (or why none applies)",
        },
        {
            "id": "data_availability",
            "label": "Data availability statement",
            "met": bool((pub.data_availability or "").strip()),
            "required": True,
            "detail": (pub.data_availability or "").strip() or "not stated",
        },
        {
            "id": "conflict_of_interest",
            "label": "Conflict of interest declared",
            "met": bool((pub.conflict_of_interest or "").strip()),
            "required": True,
            "detail": (pub.conflict_of_interest or "").strip() or "not stated",
        },
        {
            "id": "code_availability",
            "label": "Code availability statement",
            "met": bool((pub.code_availability or "").strip()),
            "required": False,
            "detail": (pub.code_availability or "").strip()
            or "not stated — expected for computational work",
        },
        {
            "id": "funding",
            "label": "Funding acknowledged",
            "met": bool((pub.funding_statement or "").strip()) or funded_grant is not None,
            "required": False,
            "detail": (pub.funding_statement or "").strip()
            or (
                f"from the project grant: {funded_grant['title']} ({funded_grant['funder']})"
                if funded_grant
                else "no statement and no awarded grant on this project"
            ),
        },
        {
            "id": "ethics",
            "label": "Ethics approval on record",
            "met": irb is not None,
            "required": False,
            "detail": (
                f"{irb['protocol_number']} ({irb['institution']})"
                + (f", expires {irb['expiry_date']}" if irb["expiry_date"] else "")
                if irb
                else "no approved IRB protocol on this project — required for human data"
            ),
        },
        {
            "id": "venue",
            "label": "Venue selected",
            "met": bool(pub.venue),
            "required": False,
            "detail": pub.venue or "not set",
        },
    ]
    required = [c for c in checks if c["required"]]
    met_required = sum(1 for c in required if c["met"])
    pct = int(met_required / len(required) * 100) if required else 0

    # Stage-aware suggested tools (use case 4)
    status = (pub.status or "draft").lower()
    if status == "draft":
        suggested = ["hypothesis", "draft-section", "draft-from-experiment", "revise"]
    elif status == "submitted":
        suggested = ["respond-to-reviewers", "revise"]
    elif status == "reviewing":
        suggested = ["respond-to-reviewers", "revise", "validate-methodology"]
    elif status in ("accepted", "published"):
        suggested = ["generate-figures", "promote"]
    else:
        suggested = ["draft-section", "revise"]

    return {
        "publication_id": pub_id,
        "status": pub.status,
        "readiness_pct": pct,
        "ready_to_submit": pct == 100,
        "checks": checks,
        "suggested_tools": suggested,
        "ai_versions": ai_versions,
        "human_versions": human_versions,
    }


@router.get("/papers/{pub_id}/evidence")
def paper_evidence(pub_id: str, current_user: User = Depends(get_current_user)):
    """Evidence pack for the paper workspace UI (use case 3)."""
    from ...crud.publications import get_publication, list_linked_experiments

    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")

    linked = list_linked_experiments(db, pub_id)
    exp_ids = [r["experiment_id"] for r in linked]

    weekly: list[dict] = []
    with get_db(db) as conn:
        clauses = ["i.publication_id = ?"]
        params: list = [pub_id]
        if exp_ids:
            clauses.append(f"i.experiment_id IN ({','.join('?' * len(exp_ids))})")
            params.extend(exp_ids)
        rows = conn.execute(
            f"""SELECT i.id, i.item_title, i.item_kind, i.progress_pct, i.status,
                       i.what_changed, i.next_step, i.needs_help, i.blocker,
                       i.risk_level, i.next_deadline, r.week_start, r.student_id
                FROM weekly_report_items i
                JOIN weekly_reports r ON r.id = i.report_id
                WHERE {' OR '.join(clauses)} AND r.status = 'submitted'
                ORDER BY r.week_start DESC LIMIT 30""",
            params,
        ).fetchall()
        for r in rows:
            weekly.append(
                {
                    "id": r["id"],
                    "week_start": r["week_start"],
                    "student_id": r["student_id"],
                    "item_title": r["item_title"],
                    "item_kind": r["item_kind"],
                    "progress_pct": r["progress_pct"],
                    "status": r["status"],
                    "what_changed": r["what_changed"],
                    "next_step": r["next_step"],
                    "needs_help": bool(r["needs_help"]),
                    "blocker": r["blocker"],
                    "risk_level": r["risk_level"],
                    "next_deadline": r["next_deadline"],
                }
            )

    return {
        "publication_id": pub_id,
        "linked_experiments": linked,
        "weekly_updates": weekly,
        "open_questions": [w for w in weekly if w["needs_help"]],
    }
