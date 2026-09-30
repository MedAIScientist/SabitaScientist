"""CRUD for academic supervision: assignments, weekly reports, meetings, journeys."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import (
    AcademicJourney,
    GraduationRequirement,
    MeetingAttendance,
    ReportExtension,
    SupervisorAssignment,
    WeeklyMeetingSetting,
    WeeklyReport,
    WeeklyReportItem,
)

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex


# ── Supervisor assignments ───────────────────────────────────────────────────


def assign_supervisor(
    db_path: Path,
    student_id: str,
    professor_id: str,
    active_from: str | None = None,
) -> SupervisorAssignment:
    """Create a supervisor assignment. Ends any previous active assignment for the student."""
    now = _now()
    active_from = active_from or now
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE supervisor_assignments SET active_until = ?
               WHERE student_id = ? AND active_until IS NULL""",
            (now, student_id),
        )
        sid = _new_id()
        conn.execute(
            """INSERT INTO supervisor_assignments
               (id, student_id, professor_id, active_from, active_until, created_at)
               VALUES (?, ?, ?, ?, NULL, ?)""",
            (sid, student_id, professor_id, active_from, now),
        )
    return SupervisorAssignment(
        id=sid,
        student_id=student_id,
        professor_id=professor_id,
        active_from=active_from,
        created_at=now,
    )


def end_supervisor_assignment(db_path: Path, assignment_id: str) -> bool:
    with get_db(db_path) as conn:
        cur = conn.execute(
            "UPDATE supervisor_assignments SET active_until = ? WHERE id = ? AND active_until IS NULL",
            (_now(), assignment_id),
        )
    return cur.rowcount > 0


def get_active_supervisor(db_path: Path, student_id: str) -> SupervisorAssignment | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT * FROM supervisor_assignments
               WHERE student_id = ? AND active_until IS NULL
               ORDER BY active_from DESC LIMIT 1""",
            (student_id,),
        ).fetchone()
    return _row_assignment(row) if row else None


def list_students_of_professor(db_path: Path, professor_id: str) -> list[SupervisorAssignment]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM supervisor_assignments
               WHERE professor_id = ? AND active_until IS NULL
               ORDER BY active_from""",
            (professor_id,),
        ).fetchall()
    return [_row_assignment(r) for r in rows]


def list_supervisor_assignments(db_path: Path) -> list[SupervisorAssignment]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM supervisor_assignments ORDER BY active_from DESC"
        ).fetchall()
    return [_row_assignment(r) for r in rows]


# ── Weekly meeting settings ──────────────────────────────────────────────────


def upsert_meeting_setting(
    db_path: Path,
    professor_id: str,
    weekday: int,
    time_local: str | None = None,
    timezone: str | None = None,
    effective_from: str | None = None,
) -> WeeklyMeetingSetting:
    """Create a versioned meeting schedule. Earlier weeks keep prior settings."""
    now = _now()
    effective_from = effective_from or now[:10]
    sid = _new_id()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO weekly_meeting_settings
               (id, professor_id, weekday, time_local, timezone, effective_from, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sid, professor_id, weekday, time_local, timezone, effective_from, now),
        )
    return WeeklyMeetingSetting(
        id=sid,
        professor_id=professor_id,
        weekday=weekday,
        effective_from=effective_from,
        created_at=now,
        time_local=time_local,
        timezone=timezone,
    )


def get_meeting_setting_for_week(
    db_path: Path, professor_id: str, week_start: str
) -> WeeklyMeetingSetting | None:
    """Return the meeting setting effective on week_start (latest version on/before that date)."""
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT * FROM weekly_meeting_settings
               WHERE professor_id = ? AND effective_from <= ?
               ORDER BY effective_from DESC, created_at DESC LIMIT 1""",
            (professor_id, week_start),
        ).fetchone()
    return _row_meeting(row) if row else None


def list_meeting_settings(db_path: Path, professor_id: str) -> list[WeeklyMeetingSetting]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM weekly_meeting_settings WHERE professor_id = ? ORDER BY effective_from DESC",
            (professor_id,),
        ).fetchall()
    return [_row_meeting(r) for r in rows]


# ── Weekly reports ───────────────────────────────────────────────────────────


def get_or_create_report(
    db_path: Path, student_id: str, week_start: str
) -> WeeklyReport:
    now = _now()
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM weekly_reports WHERE student_id = ? AND week_start = ?",
            (student_id, week_start),
        ).fetchone()
        if row:
            return _row_report(row)
        rid = _new_id()
        conn.execute(
            """INSERT INTO weekly_reports
               (id, student_id, week_start, status, review_status, risk_level,
                created_at, updated_at)
               VALUES (?, ?, ?, 'draft', 'pending', 'medium', ?, ?)""",
            (rid, student_id, week_start, now, now),
        )
        row = conn.execute(
            "SELECT * FROM weekly_reports WHERE id = ?", (rid,)
        ).fetchone()
    return _row_report(row)


def update_report_summary(
    db_path: Path,
    report_id: str,
    accomplished: str | None = None,
    next_focus: str | None = None,
    support_requested: str | None = None,
) -> WeeklyReport | None:
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE weekly_reports SET
               accomplished = COALESCE(?, accomplished),
               next_focus = COALESCE(?, next_focus),
               support_requested = COALESCE(?, support_requested),
               updated_at = ?
               WHERE id = ?""",
            (accomplished, next_focus, support_requested, _now(), report_id),
        )
        row = conn.execute(
            "SELECT * FROM weekly_reports WHERE id = ?", (report_id,)
        ).fetchone()
    return _row_report(row) if row else None


def submit_report(db_path: Path, report_id: str) -> WeeklyReport | None:
    now = _now()
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE weekly_reports SET status = 'submitted', submitted_at = ?,
               review_status = 'needs_review', updated_at = ? WHERE id = ?""",
            (now, now, report_id),
        )
        row = conn.execute(
            "SELECT * FROM weekly_reports WHERE id = ?", (report_id,)
        ).fetchone()
    return _row_report(row) if row else None


def review_report(
    db_path: Path,
    report_id: str,
    reviewer_id: str,
    review_status: str,
    feedback: str | None = None,
    risk_override: str | None = None,
) -> WeeklyReport | None:
    now = _now()
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE weekly_reports SET
               review_status = ?, feedback = COALESCE(?, feedback),
               risk_override = COALESCE(?, risk_override),
               reviewed_at = ?, reviewed_by = ?, updated_at = ?
               WHERE id = ?""",
            (review_status, feedback, risk_override, now, reviewer_id, now, report_id),
        )
        row = conn.execute(
            "SELECT * FROM weekly_reports WHERE id = ?", (report_id,)
        ).fetchone()
    return _row_report(row) if row else None


def list_reports(
    db_path: Path,
    student_id: str | None = None,
    status: str | None = None,
    review_status: str | None = None,
    risk_level: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 200,
) -> list[WeeklyReport]:
    sql = "SELECT * FROM weekly_reports WHERE 1=1"
    params: list = []
    if student_id:
        sql += " AND student_id = ?"
        params.append(student_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if review_status:
        sql += " AND review_status = ?"
        params.append(review_status)
    if risk_level:
        sql += " AND risk_level = COALESCE(risk_override, risk_level)"
        sql += " AND COALESCE(risk_override, risk_level) = ?"
        params.append(risk_level)
    if date_from:
        sql += " AND week_start >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND week_start <= ?"
        params.append(date_to)
    sql += " ORDER BY week_start DESC, student_id LIMIT ?"
    params.append(limit)
    with get_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_report(r) for r in rows]


def get_report(db_path: Path, report_id: str) -> WeeklyReport | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM weekly_reports WHERE id = ?", (report_id,)
        ).fetchone()
    return _row_report(row) if row else None


# ── Weekly report items ──────────────────────────────────────────────────────


def upsert_report_item(
    db_path: Path,
    report_id: str,
    item_title: str,
    *,
    item_id: str | None = None,
    task_id: str | None = None,
    publication_id: str | None = None,
    experiment_id: str | None = None,
    item_kind: str | None = None,
    progress_pct: int = 0,
    status: str | None = None,
    blocker: str | None = None,
    needs_help: bool = False,
    what_changed: str | None = None,
    next_step: str | None = None,
    risk_level: str = "low",
    next_deadline: str | None = None,
    sort_order: int = 0,
) -> WeeklyReportItem:
    now_id = item_id or _new_id()
    with get_db(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM weekly_report_items WHERE id = ?", (now_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE weekly_report_items SET
                   item_title=?, task_id=?, publication_id=?, experiment_id=?,
                   item_kind=?, progress_pct=?, status=?, blocker=?, needs_help=?,
                   what_changed=?, next_step=?, risk_level=?, next_deadline=?, sort_order=?
                   WHERE id=?""",
                (
                    item_title, task_id, publication_id, experiment_id,
                    item_kind, progress_pct, status, blocker, int(needs_help),
                    what_changed, next_step, risk_level, next_deadline, sort_order,
                    now_id,
                ),
            )
        else:
            conn.execute(
                """INSERT INTO weekly_report_items
                   (id, report_id, task_id, publication_id, experiment_id,
                    item_title, item_kind, progress_pct, status, blocker, needs_help,
                    what_changed, next_step, risk_level, next_deadline, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    now_id, report_id, task_id, publication_id, experiment_id,
                    item_title, item_kind, progress_pct, status, blocker, int(needs_help),
                    what_changed, next_step, risk_level, next_deadline, sort_order,
                ),
            )
        row = conn.execute(
            "SELECT * FROM weekly_report_items WHERE id = ?", (now_id,)
        ).fetchone()
    return _row_item(row)


def delete_report_item(db_path: Path, item_id: str) -> bool:
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM weekly_report_items WHERE id = ?", (item_id,))
    return cur.rowcount > 0


def list_report_items(db_path: Path, report_id: str) -> list[WeeklyReportItem]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM weekly_report_items WHERE report_id = ? ORDER BY sort_order, item_title",
            (report_id,),
        ).fetchall()
    return [_row_item(r) for r in rows]


# ── Meeting attendance ───────────────────────────────────────────────────────


def upsert_attendance(
    db_path: Path,
    professor_id: str,
    student_id: str,
    week_start: str,
    status: str,
    joined_mode: str | None = None,
    note: str | None = None,
) -> MeetingAttendance:
    now = _now()
    with get_db(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM meeting_attendance WHERE student_id = ? AND week_start = ?",
            (student_id, week_start),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE meeting_attendance SET status=?, joined_mode=?, note=?,
                   recorded_at=?, professor_id=? WHERE id=?""",
                (status, joined_mode, note, now, professor_id, existing["id"]),
            )
            aid = existing["id"]
        else:
            aid = _new_id()
            conn.execute(
                """INSERT INTO meeting_attendance
                   (id, professor_id, student_id, week_start, status, joined_mode, note, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (aid, professor_id, student_id, week_start, status, joined_mode, note, now),
            )
        row = conn.execute(
            "SELECT * FROM meeting_attendance WHERE id = ?", (aid,)
        ).fetchone()
    return _row_attendance(row)


def get_attendance(
    db_path: Path, student_id: str, week_start: str
) -> MeetingAttendance | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM meeting_attendance WHERE student_id = ? AND week_start = ?",
            (student_id, week_start),
        ).fetchone()
    return _row_attendance(row) if row else None


# ── Report extensions ────────────────────────────────────────────────────────


def grant_extension(
    db_path: Path,
    student_id: str,
    professor_id: str,
    week_start: str,
    new_deadline: str,
    reason: str | None = None,
    report_id: str | None = None,
) -> ReportExtension:
    now = _now()
    eid = _new_id()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO report_extensions
               (id, report_id, student_id, professor_id, week_start, new_deadline, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (eid, report_id, student_id, professor_id, week_start, new_deadline, reason, now),
        )
    return ReportExtension(
        id=eid,
        student_id=student_id,
        professor_id=professor_id,
        week_start=week_start,
        new_deadline=new_deadline,
        created_at=now,
        report_id=report_id,
        reason=reason,
    )


def get_extension(
    db_path: Path, student_id: str, week_start: str
) -> ReportExtension | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT * FROM report_extensions
               WHERE student_id = ? AND week_start = ?
               ORDER BY created_at DESC LIMIT 1""",
            (student_id, week_start),
        ).fetchone()
    return _row_extension(row) if row else None


# ── Academic journeys ────────────────────────────────────────────────────────


def create_journey(
    db_path: Path,
    student_id: str,
    level: str,
    status: str = "planned",
    **fields,
) -> AcademicJourney:
    now = _now()
    jid = _new_id()
    with get_db(db_path) as conn:
        if status == "active":
            conn.execute(
                """UPDATE academic_journeys SET status = 'archived', updated_at = ?
                   WHERE student_id = ? AND status = 'active'""",
                (now, student_id),
            )
        conn.execute(
            """INSERT INTO academic_journeys
               (id, student_id, level, status, programme, university, department,
                start_year, start_date, expected_end, thesis_title, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                jid, student_id, level, status,
                fields.get("programme"), fields.get("university"), fields.get("department"),
                fields.get("start_year"), fields.get("start_date"), fields.get("expected_end"),
                fields.get("thesis_title"), now, now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM academic_journeys WHERE id = ?", (jid,)
        ).fetchone()
    return _row_journey(row)


def list_journeys(db_path: Path, student_id: str) -> list[AcademicJourney]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM academic_journeys WHERE student_id = ? ORDER BY created_at DESC",
            (student_id,),
        ).fetchall()
    return [_row_journey(r) for r in rows]


def get_active_journey(db_path: Path, student_id: str) -> AcademicJourney | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM academic_journeys WHERE student_id = ? AND status = 'active' LIMIT 1",
            (student_id,),
        ).fetchone()
    return _row_journey(row) if row else None


# ── Graduation requirements ──────────────────────────────────────────────────


def create_requirement(
    db_path: Path,
    level: str,
    title: str,
    req_type: str,
    target_value: float = 1,
    **fields,
) -> GraduationRequirement:
    now = _now()
    rid = _new_id()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO graduation_requirements
               (id, level, title, description, req_type, research_item_type, min_stage,
                target_value, unit, required, active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                rid, level, title, fields.get("description"), req_type,
                fields.get("research_item_type"), fields.get("min_stage"),
                target_value, fields.get("unit"), int(fields.get("required", True)), now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM graduation_requirements WHERE id = ?", (rid,)
        ).fetchone()
    return _row_requirement(row)


def list_requirements(
    db_path: Path, level: str | None = None, active_only: bool = True
) -> list[GraduationRequirement]:
    sql = "SELECT * FROM graduation_requirements WHERE 1=1"
    params: list = []
    if level and level != "All":
        sql += " AND level = ?"
        params.append(level)
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY level, title"
    with get_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_requirement(r) for r in rows]


def archive_requirement(db_path: Path, requirement_id: str) -> bool:
    with get_db(db_path) as conn:
        cur = conn.execute(
            "UPDATE graduation_requirements SET active = 0 WHERE id = ?", (requirement_id,)
        )
    return cur.rowcount > 0


# ── Row mappers ──────────────────────────────────────────────────────────────


def _row_assignment(row) -> SupervisorAssignment:
    return SupervisorAssignment(
        id=row["id"],
        student_id=row["student_id"],
        professor_id=row["professor_id"],
        active_from=row["active_from"],
        active_until=row["active_until"],
        created_at=row["created_at"],
    )


def _row_meeting(row) -> WeeklyMeetingSetting:
    return WeeklyMeetingSetting(
        id=row["id"],
        professor_id=row["professor_id"],
        weekday=row["weekday"],
        time_local=row["time_local"],
        timezone=row["timezone"],
        effective_from=row["effective_from"],
        created_at=row["created_at"],
    )


def _row_report(row) -> WeeklyReport:
    return WeeklyReport(
        id=row["id"],
        student_id=row["student_id"],
        week_start=row["week_start"],
        status=row["status"],
        review_status=row["review_status"],
        risk_level=row["risk_level"],
        risk_override=row["risk_override"],
        accomplished=row["accomplished"],
        next_focus=row["next_focus"],
        support_requested=row["support_requested"],
        submitted_at=row["submitted_at"],
        reviewed_at=row["reviewed_at"],
        reviewed_by=row["reviewed_by"],
        feedback=row["feedback"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_item(row) -> WeeklyReportItem:
    return WeeklyReportItem(
        id=row["id"],
        report_id=row["report_id"],
        task_id=row["task_id"],
        publication_id=row["publication_id"],
        experiment_id=row["experiment_id"],
        item_title=row["item_title"],
        item_kind=row["item_kind"],
        progress_pct=row["progress_pct"],
        status=row["status"],
        blocker=row["blocker"],
        needs_help=bool(row["needs_help"]),
        what_changed=row["what_changed"],
        next_step=row["next_step"],
        risk_level=row["risk_level"],
        next_deadline=row["next_deadline"],
        sort_order=row["sort_order"],
    )


def _row_attendance(row) -> MeetingAttendance:
    return MeetingAttendance(
        id=row["id"],
        professor_id=row["professor_id"],
        student_id=row["student_id"],
        week_start=row["week_start"],
        status=row["status"],
        joined_mode=row["joined_mode"],
        note=row["note"],
        recorded_at=row["recorded_at"],
    )


def _row_extension(row) -> ReportExtension:
    return ReportExtension(
        id=row["id"],
        report_id=row["report_id"],
        student_id=row["student_id"],
        professor_id=row["professor_id"],
        week_start=row["week_start"],
        new_deadline=row["new_deadline"],
        reason=row["reason"],
        created_at=row["created_at"],
    )


def _row_journey(row) -> AcademicJourney:
    return AcademicJourney(
        id=row["id"],
        student_id=row["student_id"],
        level=row["level"],
        status=row["status"],
        programme=row["programme"],
        university=row["university"],
        department=row["department"],
        start_year=row["start_year"],
        start_date=row["start_date"],
        expected_end=row["expected_end"],
        thesis_title=row["thesis_title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )




def _row_requirement(row) -> GraduationRequirement:
    return GraduationRequirement(
        id=row["id"],
        level=row["level"],
        title=row["title"],
        description=row["description"],
        req_type=row["req_type"],
        research_item_type=row["research_item_type"],
        min_stage=row["min_stage"],
        target_value=row["target_value"],
        unit=row["unit"],
        required=bool(row["required"]),
        active=bool(row["active"]),
        created_at=row["created_at"],
    )
