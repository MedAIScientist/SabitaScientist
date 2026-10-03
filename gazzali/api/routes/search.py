"""Global search across projects, tasks, experiments, publications."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...db import get_db, get_db_path
from ...models import User
from ..deps import get_current_user
from ..schemas import SearchResultItem, SearchResults

router = APIRouter()


@router.get("/search", response_model=SearchResults)
def global_search(
    q: str = Query(min_length=2),
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    pattern = f"%{q}%"

    with get_db(db) as conn:
        project_rows = conn.execute(
            "SELECT id, name, description FROM projects WHERE name LIKE ? OR description LIKE ? LIMIT 10",
            (pattern, pattern),
        ).fetchall()
        task_rows = conn.execute(
            "SELECT id, project_id, title FROM tasks WHERE title LIKE ? OR description LIKE ? LIMIT 10",
            (pattern, pattern),
        ).fetchall()
        experiment_rows = conn.execute(
            "SELECT id, project_id, name FROM experiments WHERE name LIKE ? OR hypothesis LIKE ? LIMIT 10",
            (pattern, pattern),
        ).fetchall()
        pub_rows = conn.execute(
            "SELECT id, title, venue FROM publications WHERE title LIKE ? OR venue LIKE ? OR abstract LIKE ? LIMIT 10",
            (pattern, pattern, pattern),
        ).fetchall()

    return SearchResults(
        projects=[
            SearchResultItem(
                id=r["id"], name=r["name"], description=r["description"], type="project"
            )
            for r in project_rows
        ],
        tasks=[
            SearchResultItem(
                id=r["id"], title=r["title"], project_id=r["project_id"], type="task"
            )
            for r in task_rows
        ],
        experiments=[
            SearchResultItem(
                id=r["id"],
                name=r["name"],
                project_id=r["project_id"],
                type="experiment",
            )
            for r in experiment_rows
        ],
        publications=[
            SearchResultItem(
                id=r["id"], title=r["title"], venue=r["venue"], type="publication"
            )
            for r in pub_rows
        ],
    )
