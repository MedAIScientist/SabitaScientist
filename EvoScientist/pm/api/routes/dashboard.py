"""Admin and PI dashboard endpoints for cross-lab analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...crud.labs import list_labs, list_members
from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user, require_admin

router = APIRouter()


@router.get("/admin/stats")
def admin_stats(current_user: User = Depends(require_admin)):
    """Global system statistics for admin dashboard."""
    db = get_db_path()
    with get_db(db) as conn:
        lab_count = conn.execute("SELECT COUNT(*) FROM labs").fetchone()[0]
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        project_count = conn.execute("SELECT COUNT(*) FROM projects WHERE archived_at IS NULL").fetchone()[0]
        task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        experiment_count = conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
        assist_count = conn.execute("SELECT COUNT(*) FROM experiment_assists").fetchone()[0]
        admission_count = conn.execute("SELECT COUNT(*) FROM admissions").fetchone()[0]

        labs = list_labs(db)
        lab_details = []
        for lab in labs:
            with get_db(db) as conn2:
                proj_count = conn2.execute(
                    "SELECT COUNT(*) FROM projects WHERE lab_id = ? AND archived_at IS NULL", (lab.id,)
                ).fetchone()[0]
                member_count = conn2.execute(
                    "SELECT COUNT(*) FROM lab_members WHERE lab_id = ?", (lab.id,)
                ).fetchone()[0]
            lab_details.append({
                "id": lab.id,
                "name": lab.name,
                "department": lab.department,
                "university": lab.university,
                "member_count": member_count,
                "project_count": proj_count,
            })

    return {
        "labs": lab_count,
        "users": user_count,
        "projects": project_count,
        "tasks": task_count,
        "experiments": experiment_count,
        "assists": assist_count,
        "admissions": admission_count,
        "lab_details": lab_details,
    }


@router.get("/pi/stats")
def pi_stats(current_user: User = Depends(get_current_user)):
    """Dashboard statistics for a PI — labs they lead, projects, recent activity."""
    db = get_db_path()
    labs = [lab for lab in list_labs(db) if lab.pi_id == current_user.id or current_user.is_admin]
    if not labs:
        labs = list_labs(db)

    lab_ids = [lab.id for lab in labs]
    if not lab_ids:
        return {
            "labs": [],
            "total_projects": 0,
            "total_tasks": 0,
            "total_experiments": 0,
            "recent_projects": [],
        }

    placeholders = ",".join("?" for _ in lab_ids)
    with get_db(db) as conn:
        projects = conn.execute(
            f"SELECT id, name, created_at FROM projects WHERE lab_id IN ({placeholders}) AND archived_at IS NULL ORDER BY created_at DESC LIMIT 10",
            lab_ids,
        ).fetchall()
        task_count = conn.execute(
            f"SELECT COUNT(*) FROM tasks t JOIN projects p ON t.project_id = p.id WHERE p.lab_id IN ({placeholders})",
            lab_ids,
        ).fetchone()[0]
        exp_count = conn.execute(
            f"SELECT COUNT(*) FROM experiments e JOIN projects p ON e.project_id = p.id WHERE p.lab_id IN ({placeholders})",
            lab_ids,
        ).fetchone()[0]

    lab_list = []
    for lab in labs:
        members = list_members(db, lab.id)
        lab_list.append({
            "id": lab.id,
            "name": lab.name,
            "department": lab.department,
            "member_count": len(members),
            "members": [
                {"user_id": m.user_id, "role": m.role} for m in members
            ],
        })

    return {
        "labs": lab_list,
        "total_tasks": task_count,
        "total_experiments": exp_count,
        "recent_projects": [
            {"id": r["id"], "name": r["name"], "created_at": r["created_at"]}
            for r in projects
        ],
    }
