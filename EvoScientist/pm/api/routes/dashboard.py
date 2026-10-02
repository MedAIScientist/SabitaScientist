"""Admin and PI dashboard endpoints for cross-lab analytics & AI system health."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...crud.labs import list_labs, list_labs_where_pi, list_members
from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user, require_admin

router = APIRouter()


@router.get("/system/health")
def system_health(current_user: User = Depends(get_current_user)):
    """AI configuration status: models in use, whether keys are set, skills count."""
    import os

    from ... import settings
    from ..._ai import pm_model_choice
    from ...runner.agent_runner import _get_model as runner_model

    skills = sum(
        1
        for base in (settings.USER_SKILLS_DIR, settings.GLOBAL_SKILLS_DIR)
        if base.is_dir()
        for e in base.iterdir()
        if e.is_dir() and (e / "SKILL.md").exists()
    )
    groq_key = os.environ.get("GROQ_API_KEY", "")
    assistant_model, assistant_provider = pm_model_choice()
    return {
        "groq": {"configured": bool(groq_key), "model": runner_model()},
        "ai": {
            "runner_model": runner_model(),
            "runner_configured": bool(groq_key),
            "assistant_model": assistant_model,
            "assistant_provider": assistant_provider,
        },
        "skills_available": skills,
    }


@router.get("/admin/stats")
def admin_stats(current_user: User = Depends(require_admin)):
    """Global system statistics for admin dashboard."""
    db = get_db_path()
    with get_db(db) as conn:
        lab_count = conn.execute("SELECT COUNT(*) FROM labs").fetchone()[0]
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        project_count = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE archived_at IS NULL"
        ).fetchone()[0]
        task_count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        experiment_count = conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[
            0
        ]
        assist_count = conn.execute(
            "SELECT COUNT(*) FROM experiment_assists"
        ).fetchone()[0]
        admission_count = conn.execute("SELECT COUNT(*) FROM admissions").fetchone()[0]

        labs = list_labs(db)
        lab_details = []
        for lab in labs:
            with get_db(db) as conn2:
                proj_count = conn2.execute(
                    "SELECT COUNT(*) FROM projects WHERE lab_id = ? AND archived_at IS NULL",
                    (lab.id,),
                ).fetchone()[0]
                member_count = conn2.execute(
                    "SELECT COUNT(*) FROM lab_members WHERE lab_id = ? AND ended_at IS NULL", (lab.id,)
                ).fetchone()[0]
            lab_details.append(
                {
                    "id": lab.id,
                    "name": lab.name,
                    "department": lab.department,
                    "university": lab.university,
                    "member_count": member_count,
                    "project_count": proj_count,
                }
            )

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
    # A platform admin sees every lab; everybody else sees only the labs they
    # actually lead — matched by labs.pi_id OR a 'pi'/'admin' lab_members row,
    # since labs created before pi_id was set on creation have pi_id NULL.
    # There is deliberately no "nothing matched -> all labs" fallback here: it
    # leaked platform-wide statistics to any authenticated user.
    labs = (
        list_labs(db) if current_user.is_admin else list_labs_where_pi(db, current_user.id)
    )

    lab_ids = [lab.id for lab in labs]
    if not lab_ids:
        # Lead nothing, see nothing — but keep the full response shape with
        # zeroed counts so the dashboard UI renders an empty state instead of
        # breaking on missing keys.
        return {
            "labs": [],
            "total_projects": 0,
            "total_tasks": 0,
            "total_experiments": 0,
            "recent_projects": [],
            "task_statuses": {},
            "experiment_statuses": {},
            "publication_statuses": {},
            "publications_over_time": [],
            "mentorship": {},
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
        lab_list.append(
            {
                "id": lab.id,
                "name": lab.name,
                "department": lab.department,
                "member_count": len(members),
                "members": [{"user_id": m.user_id, "role": m.role} for m in members],
            }
        )

    # Task status breakdown
    with get_db(db) as conn:
        task_statuses = conn.execute(
            f"""SELECT t.status, COUNT(*) as cnt
                FROM tasks t JOIN projects p ON t.project_id = p.id
                WHERE p.lab_id IN ({placeholders}) AND p.archived_at IS NULL
                GROUP BY t.status""",
            lab_ids,
        ).fetchall()
        exp_statuses = conn.execute(
            f"""SELECT e.status, COUNT(*) as cnt
                FROM experiments e JOIN projects p ON e.project_id = p.id
                WHERE p.lab_id IN ({placeholders}) AND p.archived_at IS NULL
                GROUP BY e.status""",
            lab_ids,
        ).fetchall()
        pub_counts = conn.execute(
            f"""SELECT status, COUNT(*) as cnt
                FROM publications
                WHERE project_id IN (SELECT id FROM projects WHERE lab_id IN ({placeholders}))
                GROUP BY status""",
            lab_ids,
        ).fetchall()
        pub_over_time = conn.execute(
            f"""SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as cnt
                FROM publications
                WHERE project_id IN (SELECT id FROM projects WHERE lab_id IN ({placeholders}))
                  AND status IN ('published', 'accepted')
                GROUP BY month ORDER BY month""",
            lab_ids,
        ).fetchall()

    # Mentorship stats: publication co-authorship by lab members
    mentorship = {}
    for lab in labs:
        members = list_members(db, lab.id)
        member_ids = [m.user_id for m in members]
        if member_ids:
            placeholders = ",".join("?" for _ in member_ids)
            with get_db(db) as conn:
                co_pubs = conn.execute(
                    """SELECT p.created_by, COUNT(*) as cnt
                        FROM publications p
                        WHERE p.project_id IN (
                            SELECT id FROM projects WHERE lab_id = ?
                        )
                        GROUP BY p.created_by ORDER BY cnt DESC""",
                    (lab.id,),
                ).fetchall()
            mentorship[lab.id] = {
                "lab_name": lab.name,
                "member_count": len(members),
                "publications_by_member": {r["created_by"]: r["cnt"] for r in co_pubs},
                "roles": {m.user_id: m.role for m in members},
            }

    return {
        "labs": lab_list,
        "total_tasks": task_count,
        "total_experiments": exp_count,
        "recent_projects": [
            {"id": r["id"], "name": r["name"], "created_at": r["created_at"]}
            for r in projects
        ],
        "task_statuses": {r["status"]: r["cnt"] for r in task_statuses},
        "experiment_statuses": {r["status"]: r["cnt"] for r in exp_statuses},
        "publication_statuses": {r["status"]: r["cnt"] for r in pub_counts},
        "publications_over_time": [
            {"month": r["month"], "count": r["cnt"]} for r in pub_over_time
        ],
        "mentorship": mentorship,
    }
