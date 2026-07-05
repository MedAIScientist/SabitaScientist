"""Global search across projects, tasks, experiments, publications."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user

router = APIRouter()


@router.get("/search")
def global_search(q: str = Query(min_length=2), current_user: User = Depends(get_current_user)):
    db = get_db_path()
    pattern = f"%{q}%"
    results: dict = {"projects": [], "tasks": [], "experiments": [], "publications": []}

    with get_db(db) as conn:
        projects = conn.execute("SELECT id, name, description FROM projects WHERE name LIKE ? OR description LIKE ? LIMIT 10", (pattern, pattern)).fetchall()
        results["projects"] = [{"id": r["id"], "name": r["name"], "description": r["description"], "type": "project"} for r in projects]

        tasks = conn.execute("SELECT id, project_id, title FROM tasks WHERE title LIKE ? OR description LIKE ? LIMIT 10", (pattern, pattern)).fetchall()
        results["tasks"] = [{"id": r["id"], "project_id": r["project_id"], "title": r["title"], "type": "task"} for r in tasks]

        experiments = conn.execute("SELECT id, project_id, name FROM experiments WHERE name LIKE ? OR hypothesis LIKE ? LIMIT 10", (pattern, pattern)).fetchall()
        results["experiments"] = [{"id": r["id"], "project_id": r["project_id"], "name": r["name"], "type": "experiment"} for r in experiments]

        publications = conn.execute("SELECT id, title, venue FROM publications WHERE title LIKE ? OR venue LIKE ? OR abstract LIKE ? LIMIT 10", (pattern, pattern, pattern)).fetchall()
        results["publications"] = [{"id": r["id"], "title": r["title"], "venue": r["venue"], "type": "publication"} for r in publications]

    return results
