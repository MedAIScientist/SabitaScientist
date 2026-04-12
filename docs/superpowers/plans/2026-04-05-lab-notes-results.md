# Lab Notes & Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `Experiment` entity to the PM dashboard that groups tasks and stores freeform lab notes and lab results as named markdown entries.

**Architecture:** Three new SQLite tables (`experiments`, `experiment_tasks`, `experiment_entries`) with full CRUD backend. A single `experiment_entries` table covers both notes and results via a `type` tag. New FastAPI routes under `/api/v1/projects/{project_id}/experiments`. Frontend adds an `ExperimentsPage` (route `/projects/:id/experiments`), an `ExperimentDetail` drawer (OVERVIEW/NOTES/RESULTS tabs), and an `EntryEditor` modal.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, Pydantic v2, React 18, TanStack Query v5, React Router v6, Vitest + @testing-library/react.

---

## File Map

**New backend files:**
- `EvoScientist/pm/crud/experiments.py` — Experiment CRUD + task linking
- `EvoScientist/pm/crud/experiment_entries.py` — ExperimentEntry CRUD
- `EvoScientist/pm/api/routes/experiments.py` — All 11 HTTP routes

**Modified backend files:**
- `EvoScientist/pm/models.py` — add `Experiment`, `ExperimentEntry` dataclasses
- `EvoScientist/pm/db.py` — add 3 tables to `_SCHEMA`
- `EvoScientist/pm/api/schemas.py` — add 6 experiment schemas
- `EvoScientist/pm/api/app.py` — register experiments router

**New test files:**
- `tests/pm/test_crud_experiments.py`
- `tests/pm/test_crud_experiment_entries.py`
- `tests/pm/test_api_experiments.py`

**New frontend files:**
- `EvoScientist/pm/frontend/src/pages/ExperimentsPage.tsx`
- `EvoScientist/pm/frontend/src/components/ExperimentDetail.tsx`
- `EvoScientist/pm/frontend/src/components/EntryEditor.tsx`
- `EvoScientist/pm/frontend/src/pages/__tests__/ExperimentsPage.test.tsx`
- `EvoScientist/pm/frontend/src/components/__tests__/ExperimentDetail.test.tsx`
- `EvoScientist/pm/frontend/src/components/__tests__/EntryEditor.test.tsx`

**Modified frontend files:**
- `EvoScientist/pm/frontend/src/api.ts` — add `Experiment`, `ExperimentEntry` interfaces + 11 API functions
- `EvoScientist/pm/frontend/src/main.tsx` — add `/projects/:id/experiments` route
- `EvoScientist/pm/frontend/src/pages/Board.tsx` — add ⚗ EXPERIMENTS header button

---

## Task 1: `Experiment` + `ExperimentEntry` dataclasses, DB tables, Experiment CRUD

**Files:**
- Modify: `EvoScientist/pm/models.py`
- Modify: `EvoScientist/pm/db.py`
- Create: `EvoScientist/pm/crud/experiments.py`
- Create: `tests/pm/test_crud_experiments.py`

- [ ] **Step 1: Write failing tests**

Create `tests/pm/test_crud_experiments.py`:

```python
"""Tests for Experiment CRUD operations."""
from __future__ import annotations
from pathlib import Path
import pytest
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.crud.projects import create_project
from EvoScientist.pm.crud.tasks import create_task
from EvoScientist.pm.crud.experiments import (
    create_experiment, get_experiment, list_experiments,
    update_experiment, delete_experiment,
    link_task, unlink_task, list_linked_tasks,
)
from EvoScientist.pm.db import create_schema


@pytest.fixture
def setup(tmp_path: Path):
    db = tmp_path / "test.db"
    create_schema(db)
    user = create_user(db, username="u1", password_hash="h")
    project = create_project(db, name="CRISPR Project", created_by=user.id)
    task = create_task(db, project_id=project.id, title="Gel assay", created_by=user.id)
    return db, user, project, task


def test_create_and_get_experiment(setup):
    db, user, project, _ = setup
    exp = create_experiment(
        db, project_id=project.id, name="Western Blot #1",
        created_by=user.id, hypothesis="Protein X is expressed",
        tags=["blot", "protein"],
    )
    assert exp.id is not None
    assert exp.status == "planned"
    assert exp.tags == ["blot", "protein"]
    fetched = get_experiment(db, exp.id)
    assert fetched is not None
    assert fetched.name == "Western Blot #1"
    assert fetched.hypothesis == "Protein X is expressed"


def test_list_experiments(setup):
    db, user, project, _ = setup
    create_experiment(db, project_id=project.id, name="Exp A", created_by=user.id)
    create_experiment(db, project_id=project.id, name="Exp B", created_by=user.id)
    exps = list_experiments(db, project.id)
    assert len(exps) == 2
    assert {e.name for e in exps} == {"Exp A", "Exp B"}


def test_update_experiment(setup):
    db, user, project, _ = setup
    exp = create_experiment(db, project_id=project.id, name="Exp", created_by=user.id)
    updated = update_experiment(db, exp.id, name="Exp Renamed", status="running", tags=["x"])
    assert updated.name == "Exp Renamed"
    assert updated.status == "running"
    assert updated.tags == ["x"]


def test_delete_experiment(setup):
    db, user, project, _ = setup
    exp = create_experiment(db, project_id=project.id, name="Exp", created_by=user.id)
    assert delete_experiment(db, exp.id) is True
    assert get_experiment(db, exp.id) is None


def test_link_and_unlink_task(setup):
    db, user, project, task = setup
    exp = create_experiment(db, project_id=project.id, name="Exp", created_by=user.id)
    link_task(db, exp.id, task.id, linked_by=user.id)
    linked = list_linked_tasks(db, exp.id)
    assert len(linked) == 1
    assert linked[0].id == task.id
    unlink_task(db, exp.id, task.id)
    assert list_linked_tasks(db, exp.id) == []


def test_link_task_duplicate_raises(setup):
    db, user, project, task = setup
    exp = create_experiment(db, project_id=project.id, name="Exp", created_by=user.id)
    link_task(db, exp.id, task.id, linked_by=user.id)
    with pytest.raises(ValueError, match="already linked"):
        link_task(db, exp.id, task.id, linked_by=user.id)


def test_get_experiment_missing(setup):
    db, *_ = setup
    assert get_experiment(db, "nonexistent") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
uv run pytest tests/pm/test_crud_experiments.py -v 2>&1 | tail -15
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Add dataclasses to `EvoScientist/pm/models.py`**

Read the file. After the `Run` dataclass, add:

```python
@dataclass
class Experiment:
    id: str
    project_id: str
    name: str
    status: str           # 'planned' | 'running' | 'completed'
    tags: list[str]
    created_by: str
    created_at: str
    updated_at: str
    hypothesis: str | None = None
    protocol: str | None = None
    deadline: str | None = None


@dataclass
class ExperimentEntry:
    id: str
    experiment_id: str
    type: str             # 'note' | 'result'
    title: str
    body: str
    created_at: str
    updated_at: str
    author_id: str | None = None
```

- [ ] **Step 4: Add 3 tables to `EvoScientist/pm/db.py`**

Read the file. Inside `_SCHEMA`, after the `runs` table block (before the closing `"""`), add:

```sql
CREATE TABLE IF NOT EXISTS experiments (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    hypothesis  TEXT,
    protocol    TEXT,
    status      TEXT NOT NULL DEFAULT 'planned'
                CHECK(status IN ('planned', 'running', 'completed')),
    tags        TEXT NOT NULL DEFAULT '[]',
    deadline    TEXT,
    created_by  TEXT NOT NULL REFERENCES users(id),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_tasks (
    experiment_id  TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    task_id        TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    linked_at      TEXT NOT NULL,
    linked_by      TEXT NOT NULL REFERENCES users(id),
    PRIMARY KEY (experiment_id, task_id)
);

CREATE TABLE IF NOT EXISTS experiment_entries (
    id             TEXT PRIMARY KEY,
    experiment_id  TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    type           TEXT NOT NULL CHECK(type IN ('note', 'result')),
    title          TEXT NOT NULL,
    body           TEXT NOT NULL DEFAULT '',
    author_id      TEXT REFERENCES users(id),
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
```

- [ ] **Step 5: Create `EvoScientist/pm/crud/experiments.py`**

```python
"""CRUD operations for Experiment entities and task-linking."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Experiment, Task


def create_experiment(
    db_path: Path,
    project_id: str,
    name: str,
    created_by: str,
    hypothesis: str | None = None,
    protocol: str | None = None,
    status: str = "planned",
    tags: list[str] | None = None,
    deadline: str | None = None,
) -> Experiment:
    """Create an experiment record and return it."""
    exp_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    tags_json = json.dumps(tags or [])
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO experiments
               (id, project_id, name, hypothesis, protocol, status, tags,
                deadline, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (exp_id, project_id, name, hypothesis, protocol, status,
             tags_json, deadline, created_by, now, now),
        )
    return Experiment(
        id=exp_id,
        project_id=project_id,
        name=name,
        hypothesis=hypothesis,
        protocol=protocol,
        status=status,
        tags=tags or [],
        deadline=deadline,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def get_experiment(db_path: Path, exp_id: str) -> Experiment | None:
    """Return Experiment by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM experiments WHERE id = ?", (exp_id,)
        ).fetchone()
    return _row_to_experiment(row) if row else None


def list_experiments(db_path: Path, project_id: str) -> list[Experiment]:
    """Return all experiments for a project, newest first."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM experiments WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
    return [_row_to_experiment(r) for r in rows]


def update_experiment(
    db_path: Path,
    exp_id: str,
    name: str | None = None,
    hypothesis: str | None = None,
    protocol: str | None = None,
    status: str | None = None,
    tags: list[str] | None = None,
    deadline: str | None = None,
) -> Experiment:
    """Update experiment fields. Omitted kwargs are unchanged."""
    exp = get_experiment(db_path, exp_id)
    if exp is None:
        raise ValueError(f"Experiment {exp_id!r} not found")
    now = datetime.now(UTC).isoformat()
    new = Experiment(
        id=exp.id,
        project_id=exp.project_id,
        name=name if name is not None else exp.name,
        hypothesis=hypothesis if hypothesis is not None else exp.hypothesis,
        protocol=protocol if protocol is not None else exp.protocol,
        status=status if status is not None else exp.status,
        tags=tags if tags is not None else exp.tags,
        deadline=deadline if deadline is not None else exp.deadline,
        created_by=exp.created_by,
        created_at=exp.created_at,
        updated_at=now,
    )
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE experiments SET name=?, hypothesis=?, protocol=?, status=?,
               tags=?, deadline=?, updated_at=? WHERE id=?""",
            (new.name, new.hypothesis, new.protocol, new.status,
             json.dumps(new.tags), new.deadline, now, exp_id),
        )
    return new


def delete_experiment(db_path: Path, exp_id: str) -> bool:
    """Delete an experiment (cascades to entries and task links). Returns True if deleted."""
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM experiments WHERE id = ?", (exp_id,))
    return cur.rowcount > 0


def link_task(db_path: Path, exp_id: str, task_id: str, linked_by: str) -> None:
    """Link a task to an experiment. Raises ValueError if already linked."""
    now = datetime.now(UTC).isoformat()
    try:
        with get_db(db_path) as conn:
            conn.execute(
                "INSERT INTO experiment_tasks (experiment_id, task_id, linked_at, linked_by) VALUES (?, ?, ?, ?)",
                (exp_id, task_id, now, linked_by),
            )
    except Exception as exc:
        if "UNIQUE" in str(exc) or "PRIMARY KEY" in str(exc):
            raise ValueError(f"Task {task_id!r} is already linked to experiment {exp_id!r}") from exc
        raise


def unlink_task(db_path: Path, exp_id: str, task_id: str) -> bool:
    """Remove a task link. Returns True if the link existed."""
    with get_db(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM experiment_tasks WHERE experiment_id = ? AND task_id = ?",
            (exp_id, task_id),
        )
    return cur.rowcount > 0


def list_linked_tasks(db_path: Path, exp_id: str) -> list[Task]:
    """Return all tasks linked to an experiment, ordered by link time."""
    from ..crud.tasks import _row_to_task  # local import to avoid circular
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT t.* FROM tasks t
               JOIN experiment_tasks et ON et.task_id = t.id
               WHERE et.experiment_id = ?
               ORDER BY et.linked_at ASC""",
            (exp_id,),
        ).fetchall()
    return [_row_to_task(r) for r in rows]


def _row_to_experiment(row: sqlite3.Row) -> Experiment:
    try:
        tags = json.loads(row["tags"])
    except Exception:
        tags = []
    return Experiment(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        hypothesis=row["hypothesis"],
        protocol=row["protocol"],
        status=row["status"],
        tags=tags,
        deadline=row["deadline"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/pm/test_crud_experiments.py -v 2>&1 | tail -15
```

Expected: 7 tests PASS

- [ ] **Step 7: Run full PM test suite to confirm no regressions**

```bash
uv run pytest tests/pm/ -q --timeout=30 2>&1 | tail -5
```

Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git add EvoScientist/pm/models.py EvoScientist/pm/db.py \
        EvoScientist/pm/crud/experiments.py tests/pm/test_crud_experiments.py
git commit -m "feat(pm): add Experiment model, DB tables, and experiment CRUD"
```

---

## Task 2: ExperimentEntry CRUD

**Files:**
- Create: `EvoScientist/pm/crud/experiment_entries.py`
- Create: `tests/pm/test_crud_experiment_entries.py`

- [ ] **Step 1: Write failing tests**

Create `tests/pm/test_crud_experiment_entries.py`:

```python
"""Tests for ExperimentEntry CRUD operations."""
from __future__ import annotations
from pathlib import Path
import pytest
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.crud.projects import create_project
from EvoScientist.pm.crud.experiments import create_experiment
from EvoScientist.pm.crud.experiment_entries import (
    create_entry, get_entry, list_entries, update_entry, delete_entry,
)
from EvoScientist.pm.db import create_schema


@pytest.fixture
def setup(tmp_path: Path):
    db = tmp_path / "test.db"
    create_schema(db)
    user = create_user(db, username="u1", password_hash="h")
    project = create_project(db, name="P1", created_by=user.id)
    exp = create_experiment(db, project_id=project.id, name="Exp", created_by=user.id)
    return db, user, exp


def test_create_and_get_entry(setup):
    db, user, exp = setup
    entry = create_entry(
        db, experiment_id=exp.id, entry_type="note",
        title="Day 1 Observations", body="Cells looked healthy.",
        author_id=user.id,
    )
    assert entry.id is not None
    assert entry.type == "note"
    fetched = get_entry(db, entry.id)
    assert fetched is not None
    assert fetched.title == "Day 1 Observations"
    assert fetched.body == "Cells looked healthy."


def test_list_entries_all(setup):
    db, user, exp = setup
    create_entry(db, exp.id, "note", "N1", "", user.id)
    create_entry(db, exp.id, "result", "R1", "", user.id)
    entries = list_entries(db, exp.id)
    assert len(entries) == 2


def test_list_entries_by_type(setup):
    db, user, exp = setup
    create_entry(db, exp.id, "note", "N1", "", user.id)
    create_entry(db, exp.id, "result", "R1", "", user.id)
    notes = list_entries(db, exp.id, entry_type="note")
    assert len(notes) == 1
    assert notes[0].type == "note"
    results = list_entries(db, exp.id, entry_type="result")
    assert len(results) == 1
    assert results[0].type == "result"


def test_update_entry(setup):
    db, user, exp = setup
    entry = create_entry(db, exp.id, "note", "Old Title", "old", user.id)
    updated = update_entry(db, entry.id, title="New Title", body="new body")
    assert updated.title == "New Title"
    assert updated.body == "new body"


def test_delete_entry(setup):
    db, user, exp = setup
    entry = create_entry(db, exp.id, "note", "T", "", user.id)
    assert delete_entry(db, entry.id) is True
    assert get_entry(db, entry.id) is None


def test_get_entry_missing(setup):
    db, *_ = setup
    assert get_entry(db, "nonexistent") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
uv run pytest tests/pm/test_crud_experiment_entries.py -v 2>&1 | tail -10
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create `EvoScientist/pm/crud/experiment_entries.py`**

```python
"""CRUD operations for ExperimentEntry entities."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import ExperimentEntry


def create_entry(
    db_path: Path,
    experiment_id: str,
    entry_type: str,
    title: str,
    body: str = "",
    author_id: str | None = None,
) -> ExperimentEntry:
    """Create an experiment entry (note or result) and return it."""
    entry_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO experiment_entries
               (id, experiment_id, type, title, body, author_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry_id, experiment_id, entry_type, title, body, author_id, now, now),
        )
    return ExperimentEntry(
        id=entry_id,
        experiment_id=experiment_id,
        type=entry_type,
        title=title,
        body=body,
        author_id=author_id,
        created_at=now,
        updated_at=now,
    )


def get_entry(db_path: Path, entry_id: str) -> ExperimentEntry | None:
    """Return ExperimentEntry by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM experiment_entries WHERE id = ?", (entry_id,)
        ).fetchone()
    return _row_to_entry(row) if row else None


def list_entries(
    db_path: Path,
    experiment_id: str,
    entry_type: str | None = None,
) -> list[ExperimentEntry]:
    """Return entries for an experiment, newest first. Optionally filter by type."""
    query = "SELECT * FROM experiment_entries WHERE experiment_id = ?"
    params: list = [experiment_id]
    if entry_type is not None:
        query += " AND type = ?"
        params.append(entry_type)
    query += " ORDER BY created_at DESC"
    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_entry(r) for r in rows]


def update_entry(
    db_path: Path,
    entry_id: str,
    title: str | None = None,
    body: str | None = None,
) -> ExperimentEntry:
    """Update entry title and/or body. Omitted kwargs are unchanged."""
    entry = get_entry(db_path, entry_id)
    if entry is None:
        raise ValueError(f"ExperimentEntry {entry_id!r} not found")
    now = datetime.now(UTC).isoformat()
    new = ExperimentEntry(
        id=entry.id,
        experiment_id=entry.experiment_id,
        type=entry.type,
        title=title if title is not None else entry.title,
        body=body if body is not None else entry.body,
        author_id=entry.author_id,
        created_at=entry.created_at,
        updated_at=now,
    )
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE experiment_entries SET title=?, body=?, updated_at=? WHERE id=?",
            (new.title, new.body, now, entry_id),
        )
    return new


def delete_entry(db_path: Path, entry_id: str) -> bool:
    """Delete an entry. Returns True if it existed."""
    with get_db(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM experiment_entries WHERE id = ?", (entry_id,)
        )
    return cur.rowcount > 0


def _row_to_entry(row: sqlite3.Row) -> ExperimentEntry:
    return ExperimentEntry(
        id=row["id"],
        experiment_id=row["experiment_id"],
        type=row["type"],
        title=row["title"],
        body=row["body"],
        author_id=row["author_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/pm/test_crud_experiment_entries.py -v 2>&1 | tail -10
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/crud/experiment_entries.py \
        tests/pm/test_crud_experiment_entries.py
git commit -m "feat(pm): add ExperimentEntry CRUD"
```

---

## Task 3: API schemas + routes + register router

**Files:**
- Modify: `EvoScientist/pm/api/schemas.py`
- Create: `EvoScientist/pm/api/routes/experiments.py`
- Modify: `EvoScientist/pm/api/app.py`
- Create: `tests/pm/test_api_experiments.py`

- [ ] **Step 1: Write failing tests**

Create `tests/pm/test_api_experiments.py`:

```python
"""Tests for Experiment API routes."""
from __future__ import annotations
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.crud.projects import create_project
from EvoScientist.pm.crud.tasks import create_task
from EvoScientist.pm.db import create_schema


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    db = tmp_path / "test.db"
    create_schema(db)
    return db


@pytest.fixture
def app(tmp_db: Path):
    import EvoScientist.pm.api.deps as deps_mod
    import EvoScientist.pm.crud.users as users_mod
    import EvoScientist.pm.crud.projects as proj_mod
    import EvoScientist.pm.crud.tasks as tasks_mod
    import EvoScientist.pm.crud.experiments as exps_mod
    import EvoScientist.pm.crud.experiment_entries as entries_mod
    import EvoScientist.pm.api.routes.auth as auth_r
    import EvoScientist.pm.api.routes.users as users_r
    import EvoScientist.pm.api.routes.projects as proj_r
    import EvoScientist.pm.api.routes.tasks as tasks_r
    import EvoScientist.pm.api.routes.runs as runs_r
    import EvoScientist.pm.api.routes.experiments as exps_r
    for mod in [deps_mod, users_mod, proj_mod, tasks_mod, exps_mod, entries_mod,
                auth_r, users_r, proj_r, tasks_r, runs_r, exps_r]:
        if hasattr(mod, "get_db_path"):
            mod.get_db_path = lambda: tmp_db
    return create_app(tmp_db)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def owner_token(tmp_db, client):
    create_user(tmp_db, username="owner", password_hash=hash_password("pass"))
    resp = client.post("/api/v1/auth/login", json={"username": "owner", "password": "pass"})
    return resp.json()["token"]


@pytest.fixture
def project_and_task(tmp_db, owner_token, client):
    headers = {"Authorization": f"Bearer {owner_token}"}
    proj = client.post("/api/v1/projects", json={"name": "CRISPR"}, headers=headers).json()
    task = client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Gel assay"}, headers=headers,
    ).json()
    return proj["id"], task["id"]


def test_create_experiment_returns_201(client, owner_token, project_and_task):
    project_id, _ = project_and_task
    resp = client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Western Blot #1", "tags": ["blot"], "status": "planned"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Western Blot #1"
    assert data["tags"] == ["blot"]
    assert data["status"] == "planned"


def test_list_experiments_empty(client, owner_token, project_and_task):
    project_id, _ = project_and_task
    resp = client.get(
        f"/api/v1/projects/{project_id}/experiments",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_experiments_returns_created(client, owner_token, project_and_task):
    project_id, _ = project_and_task
    headers = {"Authorization": f"Bearer {owner_token}"}
    client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Exp A"}, headers=headers,
    )
    resp = client.get(f"/api/v1/projects/{project_id}/experiments", headers=headers)
    assert len(resp.json()) == 1


def test_create_entry(client, owner_token, project_and_task):
    project_id, _ = project_and_task
    headers = {"Authorization": f"Bearer {owner_token}"}
    exp = client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Exp"}, headers=headers,
    ).json()
    resp = client.post(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}/entries",
        json={"type": "note", "title": "Day 1", "body": "All good"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Day 1"
    assert resp.json()["type"] == "note"


def test_list_entries_with_type_filter(client, owner_token, project_and_task):
    project_id, _ = project_and_task
    headers = {"Authorization": f"Bearer {owner_token}"}
    exp = client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Exp"}, headers=headers,
    ).json()
    client.post(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}/entries",
        json={"type": "note", "title": "N1"}, headers=headers,
    )
    client.post(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}/entries",
        json={"type": "result", "title": "R1"}, headers=headers,
    )
    resp = client.get(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}/entries?type=note",
        headers=headers,
    )
    assert len(resp.json()) == 1
    assert resp.json()[0]["type"] == "note"


def test_link_task(client, owner_token, project_and_task):
    project_id, task_id = project_and_task
    headers = {"Authorization": f"Bearer {owner_token}"}
    exp = client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Exp"}, headers=headers,
    ).json()
    resp = client.post(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}/tasks",
        json={"task_id": task_id}, headers=headers,
    )
    assert resp.status_code == 201
    linked = client.get(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}/tasks",
        headers=headers,
    ).json()
    assert len(linked) == 1
    assert linked[0]["id"] == task_id


def test_requires_auth(client, project_and_task):
    project_id, _ = project_and_task
    resp = client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={"name": "Exp"},
    )
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
uv run pytest tests/pm/test_api_experiments.py -v 2>&1 | tail -10
```

Expected: FAIL with `ImportError` or `404`

- [ ] **Step 3: Add schemas to `EvoScientist/pm/api/schemas.py`**

Read the file. At the end (after `RunResponse`), add:

```python
# ── Experiments ───────────────────────────────────────────────────────────────


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hypothesis: str | None = None
    protocol: str | None = None
    status: str = Field(default="planned", pattern="^(planned|running|completed)$")
    tags: list[str] = []
    deadline: str | None = None


class ExperimentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    hypothesis: str | None = None
    protocol: str | None = None
    status: str | None = Field(default=None, pattern="^(planned|running|completed)$")
    tags: list[str] | None = None
    deadline: str | None = None


class ExperimentResponse(BaseModel):
    id: str
    project_id: str
    name: str
    hypothesis: str | None
    protocol: str | None
    status: str
    tags: list[str]
    deadline: str | None
    created_by: str
    created_at: str
    updated_at: str


class ExperimentEntryCreate(BaseModel):
    type: str = Field(pattern="^(note|result)$")
    title: str = Field(min_length=1, max_length=200)
    body: str = ""


class ExperimentEntryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None


class ExperimentEntryResponse(BaseModel):
    id: str
    experiment_id: str
    type: str
    title: str
    body: str
    author_id: str | None
    created_at: str
    updated_at: str
```

- [ ] **Step 4: Create `EvoScientist/pm/api/routes/experiments.py`**

```python
"""Experiment endpoints — CRUD, task linking, and entry management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...crud.experiment_entries import (
    create_entry,
    delete_entry,
    get_entry,
    list_entries,
    update_entry,
)
from ...crud.experiments import (
    create_experiment,
    delete_experiment,
    get_experiment,
    link_task,
    list_experiments,
    list_linked_tasks,
    unlink_task,
    update_experiment,
)
from ...crud.tasks import get_task
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role
from ..schemas import (
    ExperimentCreate,
    ExperimentEntryCreate,
    ExperimentEntryResponse,
    ExperimentEntryUpdate,
    ExperimentResponse,
    ExperimentUpdate,
    TaskResponse,
)

router = APIRouter()


def _exp_to_response(e) -> ExperimentResponse:
    return ExperimentResponse(
        id=e.id, project_id=e.project_id, name=e.name,
        hypothesis=e.hypothesis, protocol=e.protocol, status=e.status,
        tags=e.tags, deadline=e.deadline, created_by=e.created_by,
        created_at=e.created_at, updated_at=e.updated_at,
    )


def _entry_to_response(e) -> ExperimentEntryResponse:
    return ExperimentEntryResponse(
        id=e.id, experiment_id=e.experiment_id, type=e.type,
        title=e.title, body=e.body, author_id=e.author_id,
        created_at=e.created_at, updated_at=e.updated_at,
    )


def _task_to_response(t) -> TaskResponse:
    return TaskResponse(
        id=t.id, project_id=t.project_id, title=t.title,
        description=t.description, assignee_id=t.assignee_id,
        status=t.status, priority=t.priority, deadline=t.deadline,
        session_id=t.session_id, created_by=t.created_by,
        created_at=t.created_at, updated_at=t.updated_at,
    )


def _get_exp_or_404(project_id: str, exp_id: str):
    """Return experiment or raise 404 if missing or wrong project."""
    exp = get_experiment(get_db_path(), exp_id)
    if not exp or exp.project_id != project_id:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


# ── Experiment CRUD ──────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/experiments",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_new_experiment(
    project_id: str,
    body: ExperimentCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Create a new experiment in the project."""
    exp = create_experiment(
        get_db_path(),
        project_id=project_id,
        name=body.name,
        created_by=current_user.id,
        hypothesis=body.hypothesis,
        protocol=body.protocol,
        status=body.status,
        tags=body.tags,
        deadline=body.deadline,
    )
    return _exp_to_response(exp)


@router.get("/{project_id}/experiments", response_model=list[ExperimentResponse])
def list_project_experiments(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List all experiments for a project."""
    return [_exp_to_response(e) for e in list_experiments(get_db_path(), project_id)]


@router.get("/{project_id}/experiments/{exp_id}", response_model=ExperimentResponse)
def get_experiment_detail(
    project_id: str,
    exp_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """Get a single experiment."""
    return _exp_to_response(_get_exp_or_404(project_id, exp_id))


@router.patch("/{project_id}/experiments/{exp_id}", response_model=ExperimentResponse)
def patch_experiment(
    project_id: str,
    exp_id: str,
    body: ExperimentUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Update experiment fields."""
    _get_exp_or_404(project_id, exp_id)
    updated = update_experiment(
        get_db_path(), exp_id,
        name=body.name,
        hypothesis=body.hypothesis,
        protocol=body.protocol,
        status=body.status,
        tags=body.tags,
        deadline=body.deadline,
    )
    return _exp_to_response(updated)


@router.delete(
    "/{project_id}/experiments/{exp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_experiment_endpoint(
    project_id: str,
    exp_id: str,
    current_user: User = Depends(require_project_role("owner")),
):
    """Delete an experiment (cascades to entries and task links)."""
    _get_exp_or_404(project_id, exp_id)
    delete_experiment(get_db_path(), exp_id)


# ── Task linking ─────────────────────────────────────────────────────────────

class _LinkTaskBody(BaseModel := __import__("pydantic").BaseModel):
    task_id: str


@router.post(
    "/{project_id}/experiments/{exp_id}/tasks",
    status_code=status.HTTP_201_CREATED,
)
def link_task_to_experiment(
    project_id: str,
    exp_id: str,
    body: _LinkTaskBody,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Link a task to an experiment."""
    _get_exp_or_404(project_id, exp_id)
    task = get_task(get_db_path(), body.task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=422, detail="Task does not belong to this project")
    try:
        link_task(get_db_path(), exp_id, body.task_id, linked_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"experiment_id": exp_id, "task_id": body.task_id}


@router.delete(
    "/{project_id}/experiments/{exp_id}/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_task_from_experiment(
    project_id: str,
    exp_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Unlink a task from an experiment."""
    _get_exp_or_404(project_id, exp_id)
    unlink_task(get_db_path(), exp_id, task_id)


@router.get(
    "/{project_id}/experiments/{exp_id}/tasks",
    response_model=list[TaskResponse],
)
def get_linked_tasks(
    project_id: str,
    exp_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List all tasks linked to an experiment."""
    _get_exp_or_404(project_id, exp_id)
    return [_task_to_response(t) for t in list_linked_tasks(get_db_path(), exp_id)]


# ── Entries ───────────────────────────────────────────────────────────────────

@router.get(
    "/{project_id}/experiments/{exp_id}/entries",
    response_model=list[ExperimentEntryResponse],
)
def list_experiment_entries(
    project_id: str,
    exp_id: str,
    type: str | None = Query(default=None, pattern="^(note|result)$"),
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List entries for an experiment. Optionally filter by ?type=note|result."""
    _get_exp_or_404(project_id, exp_id)
    return [_entry_to_response(e) for e in list_entries(get_db_path(), exp_id, type)]


@router.post(
    "/{project_id}/experiments/{exp_id}/entries",
    response_model=ExperimentEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_experiment_entry(
    project_id: str,
    exp_id: str,
    body: ExperimentEntryCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Create a note or result entry on an experiment."""
    _get_exp_or_404(project_id, exp_id)
    entry = create_entry(
        get_db_path(),
        experiment_id=exp_id,
        entry_type=body.type,
        title=body.title,
        body=body.body,
        author_id=current_user.id,
    )
    return _entry_to_response(entry)


@router.patch(
    "/{project_id}/experiments/{exp_id}/entries/{entry_id}",
    response_model=ExperimentEntryResponse,
)
def patch_experiment_entry(
    project_id: str,
    exp_id: str,
    entry_id: str,
    body: ExperimentEntryUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Update an entry's title and/or body."""
    _get_exp_or_404(project_id, exp_id)
    entry = get_entry(get_db_path(), entry_id)
    if not entry or entry.experiment_id != exp_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    updated = update_entry(get_db_path(), entry_id, title=body.title, body=body.body)
    return _entry_to_response(updated)


@router.delete(
    "/{project_id}/experiments/{exp_id}/entries/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_experiment_entry(
    project_id: str,
    exp_id: str,
    entry_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Delete an entry."""
    _get_exp_or_404(project_id, exp_id)
    entry = get_entry(get_db_path(), entry_id)
    if not entry or entry.experiment_id != exp_id:
        raise HTTPException(status_code=404, detail="Entry not found")
    delete_entry(get_db_path(), entry_id)
```

**NOTE:** The `_LinkTaskBody` class uses an inline BaseModel import trick that is fragile. Replace it with a proper top-level class. After writing the file, edit it to add this at the top level (after the schema imports):

```python
from pydantic import BaseModel as _BaseModel

class _LinkTaskBody(_BaseModel):
    task_id: str
```

And remove the inline `class _LinkTaskBody(BaseModel := __import__("pydantic").BaseModel):` line.

- [ ] **Step 5: Register router in `EvoScientist/pm/api/app.py`**

Read the file. Change the import line:
```python
from .routes import auth, projects, runs, tasks, users
```
to:
```python
from .routes import auth, experiments, projects, runs, tasks, users
```

After `app.include_router(runs.router, ...)`, add:
```python
    app.include_router(experiments.router, prefix="/api/v1/projects", tags=["experiments"])
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/pm/test_api_experiments.py -v 2>&1 | tail -15
```

Expected: 7 tests PASS

- [ ] **Step 7: Run full PM test suite**

```bash
uv run pytest tests/pm/ -q --timeout=30 2>&1 | tail -5
```

- [ ] **Step 8: Commit**

```bash
git add EvoScientist/pm/api/schemas.py \
        EvoScientist/pm/api/routes/experiments.py \
        EvoScientist/pm/api/app.py \
        tests/pm/test_api_experiments.py
git commit -m "feat(pm): add experiment API routes (CRUD, task linking, entries)"
```

---

## Task 4: Frontend `api.ts` — Experiment interfaces + API functions

**Files:**
- Modify: `EvoScientist/pm/frontend/src/api.ts`

- [ ] **Step 1: Add `Experiment` and `ExperimentEntry` interfaces**

Read `EvoScientist/pm/frontend/src/api.ts`. After the `Run` interface at the bottom, add:

```typescript
export interface Experiment {
  id: string
  project_id: string
  name: string
  hypothesis: string | null
  protocol: string | null
  status: 'planned' | 'running' | 'completed'
  tags: string[]
  deadline: string | null
  created_by: string
  created_at: string
  updated_at: string
}

export interface ExperimentEntry {
  id: string
  experiment_id: string
  type: 'note' | 'result'
  title: string
  body: string
  author_id: string | null
  created_at: string
  updated_at: string
}
```

- [ ] **Step 2: Add 11 API functions to the `api` object**

Read the file. At the end of the `api` object (after `streamRunUrl`), before the closing `}`, add:

```typescript
  // ── Experiments ──────────────────────────────────────────────────────────
  listExperiments: (projectId: string) =>
    request<Experiment[]>('GET', `/projects/${projectId}/experiments`),
  createExperiment: (projectId: string, data: {
    name: string; hypothesis?: string | null; protocol?: string | null;
    status?: string; tags?: string[]; deadline?: string | null
  }) => request<Experiment>('POST', `/projects/${projectId}/experiments`, data),
  getExperiment: (projectId: string, expId: string) =>
    request<Experiment>('GET', `/projects/${projectId}/experiments/${expId}`),
  updateExperiment: (projectId: string, expId: string, data: {
    name?: string; hypothesis?: string | null; protocol?: string | null;
    status?: string; tags?: string[]; deadline?: string | null
  }) => request<Experiment>('PATCH', `/projects/${projectId}/experiments/${expId}`, data),
  deleteExperiment: (projectId: string, expId: string) =>
    request<void>('DELETE', `/projects/${projectId}/experiments/${expId}`),
  linkTask: (projectId: string, expId: string, taskId: string) =>
    request<{ experiment_id: string; task_id: string }>(
      'POST', `/projects/${projectId}/experiments/${expId}/tasks`, { task_id: taskId }
    ),
  unlinkTask: (projectId: string, expId: string, taskId: string) =>
    request<void>('DELETE', `/projects/${projectId}/experiments/${expId}/tasks/${taskId}`),
  listLinkedTasks: (projectId: string, expId: string) =>
    request<Task[]>('GET', `/projects/${projectId}/experiments/${expId}/tasks`),
  listEntries: (projectId: string, expId: string, type?: 'note' | 'result') =>
    request<ExperimentEntry[]>(
      'GET', `/projects/${projectId}/experiments/${expId}/entries${type ? `?type=${type}` : ''}`
    ),
  createEntry: (projectId: string, expId: string, data: { type: 'note' | 'result'; title: string; body?: string }) =>
    request<ExperimentEntry>('POST', `/projects/${projectId}/experiments/${expId}/entries`, data),
  updateEntry: (projectId: string, expId: string, entryId: string, data: { title?: string; body?: string }) =>
    request<ExperimentEntry>('PATCH', `/projects/${projectId}/experiments/${expId}/entries/${entryId}`, data),
  deleteEntry: (projectId: string, expId: string, entryId: string) =>
    request<void>('DELETE', `/projects/${projectId}/experiments/${expId}/entries/${entryId}`),
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist/EvoScientist/pm/frontend
npx tsc --noEmit 2>&1
```

Expected: no output (zero errors)

- [ ] **Step 4: Commit**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
git add EvoScientist/pm/frontend/src/api.ts
git commit -m "feat(pm/frontend): add Experiment/ExperimentEntry interfaces and API functions"
```

---

## Task 5: `EntryEditor` component

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/EntryEditor.tsx`
- Create: `EvoScientist/pm/frontend/src/components/__tests__/EntryEditor.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `EvoScientist/pm/frontend/src/components/__tests__/EntryEditor.test.tsx`:

```typescript
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { EntryEditor } from '../EntryEditor'

describe('EntryEditor', () => {
  it('renders title input and body textarea', () => {
    render(<EntryEditor type="note" onSave={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByPlaceholderText(/title/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/markdown/i)).toBeInTheDocument()
  })

  it('SAVE button is disabled when title is empty', () => {
    render(<EntryEditor type="note" onSave={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('button', { name: /save/i })).toBeDisabled()
  })

  it('SAVE button is enabled when title is non-empty', () => {
    render(<EntryEditor type="result" onSave={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(/title/i), { target: { value: 'My result' } })
    expect(screen.getByRole('button', { name: /save/i })).not.toBeDisabled()
  })

  it('calls onSave with title and body when submitted', () => {
    const onSave = vi.fn()
    render(<EntryEditor type="note" onSave={onSave} onCancel={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(/title/i), { target: { value: 'My Note' } })
    fireEvent.change(screen.getByPlaceholderText(/markdown/i), { target: { value: 'Content here' } })
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(onSave).toHaveBeenCalledWith({ title: 'My Note', body: 'Content here' })
  })

  it('calls onCancel when CANCEL is clicked', () => {
    const onCancel = vi.fn()
    render(<EntryEditor type="note" onSave={vi.fn()} onCancel={onCancel} />)
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onCancel).toHaveBeenCalled()
  })

  it('pre-fills title and body when editing', () => {
    render(
      <EntryEditor type="note" onSave={vi.fn()} onCancel={vi.fn()}
        initialTitle="Existing Title" initialBody="Existing body" />
    )
    expect((screen.getByPlaceholderText(/title/i) as HTMLInputElement).value).toBe('Existing Title')
    expect((screen.getByPlaceholderText(/markdown/i) as HTMLTextAreaElement).value).toBe('Existing body')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist/EvoScientist/pm/frontend
npx vitest run src/components/__tests__/EntryEditor.test.tsx --reporter=verbose 2>&1 | tail -10
```

Expected: FAIL with `Cannot find module`

- [ ] **Step 3: Create `EvoScientist/pm/frontend/src/components/EntryEditor.tsx`**

```tsx
import { useState } from 'react'

interface Props {
  type: 'note' | 'result'
  onSave: (data: { title: string; body: string }) => void
  onCancel: () => void
  initialTitle?: string
  initialBody?: string
}

export function EntryEditor({ type, onSave, onCancel, initialTitle = '', initialBody = '' }: Props) {
  const [title, setTitle] = useState(initialTitle)
  const [body, setBody] = useState(initialBody)

  const label = type === 'note' ? 'NOTE' : 'RESULT'
  const accent = type === 'note' ? '#22d3ee' : '#10b981'

  return (
    <div style={{
      background: '#0a1220',
      border: `1px solid ${accent}33`,
      borderRadius: 6,
      padding: '12px 14px',
    }}>
      <div style={{ fontSize: 8, color: accent, fontWeight: 700, fontFamily: 'var(--font-mono)', letterSpacing: '0.1em', marginBottom: 8 }}>
        {initialTitle ? `EDIT ${label}` : `NEW ${label}`}
      </div>

      <input
        value={title}
        onChange={e => setTitle(e.target.value)}
        placeholder="Title…"
        style={{
          width: '100%', boxSizing: 'border-box',
          background: '#070b12', border: '1px solid rgba(100,140,200,0.18)',
          borderRadius: 4, color: '#e2e8f0', fontSize: 11, padding: '6px 8px',
          fontFamily: 'inherit', marginBottom: 6, outline: 'none',
        }}
      />

      <textarea
        value={body}
        onChange={e => setBody(e.target.value)}
        rows={5}
        placeholder="Markdown content…"
        style={{
          width: '100%', boxSizing: 'border-box',
          background: '#070b12', border: '1px solid rgba(100,140,200,0.18)',
          borderRadius: 4, color: '#94a3b8', fontSize: 10, padding: '6px 8px',
          fontFamily: 'var(--font-mono)', resize: 'vertical', outline: 'none',
          marginBottom: 8,
        }}
      />

      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
        <button
          onClick={onCancel}
          style={{
            background: 'rgba(100,140,200,0.06)', border: '1px solid rgba(100,140,200,0.14)',
            borderRadius: 3, padding: '4px 10px', color: '#64748b',
            fontSize: 9, fontFamily: 'var(--font-mono)', cursor: 'pointer',
          }}
        >
          CANCEL
        </button>
        <button
          onClick={() => onSave({ title: title.trim(), body })}
          disabled={!title.trim()}
          style={{
            background: `${accent}18`, border: `1px solid ${accent}40`,
            borderRadius: 3, padding: '4px 10px', color: accent,
            fontSize: 9, fontFamily: 'var(--font-mono)', cursor: 'pointer',
            opacity: !title.trim() ? 0.4 : 1,
          }}
        >
          SAVE
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run src/components/__tests__/EntryEditor.test.tsx --reporter=verbose 2>&1 | tail -10
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
git add EvoScientist/pm/frontend/src/components/EntryEditor.tsx \
        EvoScientist/pm/frontend/src/components/__tests__/EntryEditor.test.tsx
git commit -m "feat(pm/frontend): add EntryEditor component for lab notes and results"
```

---

## Task 6: `ExperimentDetail` drawer

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/ExperimentDetail.tsx`
- Create: `EvoScientist/pm/frontend/src/components/__tests__/ExperimentDetail.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `EvoScientist/pm/frontend/src/components/__tests__/ExperimentDetail.test.tsx`:

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ExperimentDetail } from '../ExperimentDetail'
import type { Experiment } from '../../api'

vi.mock('../../api', () => ({
  api: {
    getExperiment: vi.fn().mockResolvedValue(null),
    updateExperiment: vi.fn().mockResolvedValue({}),
    deleteExperiment: vi.fn().mockResolvedValue(undefined),
    listLinkedTasks: vi.fn().mockResolvedValue([]),
    listTasks: vi.fn().mockResolvedValue([]),
    linkTask: vi.fn().mockResolvedValue({}),
    unlinkTask: vi.fn().mockResolvedValue(undefined),
    listEntries: vi.fn().mockResolvedValue([]),
    createEntry: vi.fn().mockResolvedValue({ id: 'e1', type: 'note', title: 'T', body: '', experiment_id: 'exp1', author_id: null, created_at: '', updated_at: '' }),
    updateEntry: vi.fn().mockResolvedValue({}),
    deleteEntry: vi.fn().mockResolvedValue(undefined),
  },
}))

vi.mock('../EntryEditor', () => ({
  EntryEditor: ({ onCancel }: { onCancel: () => void }) => (
    <div data-testid="entry-editor"><button onClick={onCancel}>CANCEL</button></div>
  ),
}))

const MOCK_EXP: Experiment = {
  id: 'exp1', project_id: 'p1', name: 'Western Blot #1',
  hypothesis: 'Protein is expressed', protocol: null,
  status: 'planned', tags: ['blot', 'protein'], deadline: null,
  created_by: 'u1', created_at: '2026-01-01', updated_at: '2026-01-01',
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

describe('ExperimentDetail', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders experiment name and status', () => {
    render(wrap(<ExperimentDetail experiment={MOCK_EXP} projectId="p1" onClose={vi.fn()} />))
    expect(screen.getByText('Western Blot #1')).toBeInTheDocument()
    expect(screen.getByText('PLANNED')).toBeInTheDocument()
  })

  it('renders OVERVIEW, NOTES, RESULTS tabs', () => {
    render(wrap(<ExperimentDetail experiment={MOCK_EXP} projectId="p1" onClose={vi.fn()} />))
    expect(screen.getByRole('button', { name: /OVERVIEW/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /NOTES/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /RESULTS/i })).toBeInTheDocument()
  })

  it('shows hypothesis in OVERVIEW tab', () => {
    render(wrap(<ExperimentDetail experiment={MOCK_EXP} projectId="p1" onClose={vi.fn()} />))
    expect(screen.getByText('Protein is expressed')).toBeInTheDocument()
  })

  it('switches to NOTES tab and shows Add Note button', async () => {
    render(wrap(<ExperimentDetail experiment={MOCK_EXP} projectId="p1" onClose={vi.fn()} />))
    fireEvent.click(screen.getByRole('button', { name: /NOTES/i }))
    await waitFor(() => expect(screen.getByText(/ADD NOTE/i)).toBeInTheDocument())
  })

  it('switches to RESULTS tab and shows Add Result button', async () => {
    render(wrap(<ExperimentDetail experiment={MOCK_EXP} projectId="p1" onClose={vi.fn()} />))
    fireEvent.click(screen.getByRole('button', { name: /RESULTS/i }))
    await waitFor(() => expect(screen.getByText(/ADD RESULT/i)).toBeInTheDocument())
  })

  it('calls onClose when ✕ is clicked', () => {
    const onClose = vi.fn()
    render(wrap(<ExperimentDetail experiment={MOCK_EXP} projectId="p1" onClose={onClose} />))
    fireEvent.click(screen.getByRole('button', { name: /✕/ }))
    expect(onClose).toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist/EvoScientist/pm/frontend
npx vitest run src/components/__tests__/ExperimentDetail.test.tsx --reporter=verbose 2>&1 | tail -10
```

Expected: FAIL with `Cannot find module`

- [ ] **Step 3: Create `EvoScientist/pm/frontend/src/components/ExperimentDetail.tsx`**

```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Experiment, ExperimentEntry, Task } from '../api'
import { EntryEditor } from './EntryEditor'

const STATUS_META: Record<string, { color: string; label: string }> = {
  planned:   { color: '#f59e0b', label: 'PLANNED' },
  running:   { color: '#22d3ee', label: 'RUNNING' },
  completed: { color: '#10b981', label: 'COMPLETED' },
}

interface Props {
  experiment: Experiment
  projectId: string
  onClose: () => void
}

type Tab = 'overview' | 'notes' | 'results'

export function ExperimentDetail({ experiment, projectId, onClose }: Props) {
  const qc = useQueryClient()
  const [tab, setTab] = useState<Tab>('overview')
  const [showEditor, setShowEditor] = useState(false)
  const [editingEntry, setEditingEntry] = useState<ExperimentEntry | null>(null)
  const [taskSearch, setTaskSearch] = useState('')

  const status = STATUS_META[experiment.status] ?? STATUS_META.planned

  // Entries query — filtered by tab
  const entryType = tab === 'notes' ? 'note' : tab === 'results' ? 'result' : undefined
  const { data: entries = [] } = useQuery({
    queryKey: ['entries', experiment.id, entryType],
    queryFn: () => api.listEntries(projectId, experiment.id, entryType),
    enabled: tab !== 'overview',
  })

  const { data: linkedTasks = [] } = useQuery({
    queryKey: ['linked-tasks', experiment.id],
    queryFn: () => api.listLinkedTasks(projectId, experiment.id),
    enabled: tab === 'overview',
  })

  const { data: allTasks = [] } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.listTasks(projectId),
    enabled: tab === 'overview' && taskSearch.length > 0,
  })

  const createEntryMutation = useMutation({
    mutationFn: (data: { title: string; body: string }) =>
      api.createEntry(projectId, experiment.id, { type: entryType as 'note' | 'result', ...data }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entries', experiment.id] })
      setShowEditor(false)
    },
  })

  const updateEntryMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { title: string; body: string } }) =>
      api.updateEntry(projectId, experiment.id, id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['entries', experiment.id] })
      setEditingEntry(null)
    },
  })

  const deleteEntryMutation = useMutation({
    mutationFn: (entryId: string) => api.deleteEntry(projectId, experiment.id, entryId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['entries', experiment.id] }),
  })

  const linkTaskMutation = useMutation({
    mutationFn: (taskId: string) => api.linkTask(projectId, experiment.id, taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['linked-tasks', experiment.id] })
      setTaskSearch('')
    },
  })

  const unlinkTaskMutation = useMutation({
    mutationFn: (taskId: string) => api.unlinkTask(projectId, experiment.id, taskId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['linked-tasks', experiment.id] }),
  })

  const searchResults = taskSearch.length > 0
    ? allTasks.filter(t =>
        t.title.toLowerCase().includes(taskSearch.toLowerCase()) &&
        !linkedTasks.some(lt => lt.id === t.id)
      )
    : []

  const tabStyle = (t: Tab): React.CSSProperties => ({
    padding: '5px 12px', fontSize: 9, fontFamily: 'var(--font-mono)',
    color: tab === t ? '#22d3ee' : '#475569',
    background: 'none', border: 'none', borderBottomStyle: 'solid',
    borderBottomWidth: 2, borderBottomColor: tab === t ? '#22d3ee' : 'transparent',
    cursor: 'pointer', fontWeight: tab === t ? 700 : 400,
  })

  return (
    <div style={{
      position: 'fixed', right: 0, top: 0, bottom: 0, width: 420,
      background: '#070b12', borderLeft: '1px solid rgba(100,140,200,0.14)',
      zIndex: 30, display: 'flex', flexDirection: 'column', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 16px 10px', borderBottom: '1px solid rgba(100,140,200,0.1)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 8 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#f1f5f9', marginBottom: 4 }}>
              {experiment.name}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{
                fontSize: 8, fontWeight: 700, fontFamily: 'var(--font-mono)',
                color: status.color, background: `${status.color}18`,
                border: `1px solid ${status.color}33`,
                borderRadius: 2, padding: '1px 5px',
              }}>
                {status.label}
              </span>
              {experiment.tags.map(tag => (
                <span key={tag} style={{
                  fontSize: 7, color: '#475569', background: 'rgba(100,140,200,0.06)',
                  border: '1px solid rgba(100,140,200,0.1)', borderRadius: 2, padding: '1px 4px',
                }}>
                  {tag}
                </span>
              ))}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#475569', fontSize: 16, cursor: 'pointer', padding: 4 }}
          >
            ✕
          </button>
        </div>

        {/* Tab bar */}
        <div style={{ display: 'flex', borderBottom: '1px solid rgba(100,140,200,0.08)', marginTop: 4 }}>
          <button style={tabStyle('overview')} onClick={() => setTab('overview')}>OVERVIEW</button>
          <button style={tabStyle('notes')} onClick={() => { setTab('notes'); setShowEditor(false) }}>NOTES</button>
          <button style={tabStyle('results')} onClick={() => { setTab('results'); setShowEditor(false) }}>RESULTS</button>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px' }}>
        {tab === 'overview' && (
          <OverviewTab
            experiment={experiment}
            linkedTasks={linkedTasks}
            taskSearch={taskSearch}
            setTaskSearch={setTaskSearch}
            searchResults={searchResults}
            onLink={id => linkTaskMutation.mutate(id)}
            onUnlink={id => unlinkTaskMutation.mutate(id)}
          />
        )}

        {(tab === 'notes' || tab === 'results') && (
          <EntriesTab
            entries={entries}
            type={tab === 'notes' ? 'note' : 'result'}
            editingEntry={editingEntry}
            showEditor={showEditor}
            onAdd={() => { setShowEditor(true); setEditingEntry(null) }}
            onEdit={entry => { setEditingEntry(entry); setShowEditor(false) }}
            onDelete={id => deleteEntryMutation.mutate(id)}
            onSaveNew={data => createEntryMutation.mutate(data)}
            onSaveEdit={data => editingEntry && updateEntryMutation.mutate({ id: editingEntry.id, data })}
            onCancelEditor={() => { setShowEditor(false); setEditingEntry(null) }}
          />
        )}
      </div>
    </div>
  )
}

function OverviewTab({
  experiment, linkedTasks, taskSearch, setTaskSearch,
  searchResults, onLink, onUnlink,
}: {
  experiment: Experiment
  linkedTasks: Task[]
  taskSearch: string
  setTaskSearch: (s: string) => void
  searchResults: Task[]
  onLink: (id: string) => void
  onUnlink: (id: string) => void
}) {
  const fieldLabel: React.CSSProperties = {
    fontSize: 8, fontWeight: 700, color: '#334155',
    letterSpacing: '0.1em', fontFamily: 'var(--font-mono)',
    marginBottom: 4, marginTop: 10, display: 'block',
  }
  return (
    <div>
      {experiment.hypothesis && (
        <>
          <span style={fieldLabel}>HYPOTHESIS</span>
          <p style={{ fontSize: 11, color: '#94a3b8', margin: '0 0 8px', lineHeight: 1.6 }}>
            {experiment.hypothesis}
          </p>
        </>
      )}
      {experiment.protocol && (
        <>
          <span style={fieldLabel}>PROTOCOL</span>
          <pre style={{ fontSize: 10, color: '#64748b', fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap', margin: '0 0 8px' }}>
            {experiment.protocol}
          </pre>
        </>
      )}
      {experiment.deadline && (
        <>
          <span style={fieldLabel}>DEADLINE</span>
          <p style={{ fontSize: 11, color: '#94a3b8', margin: '0 0 8px' }}>{experiment.deadline}</p>
        </>
      )}

      <span style={fieldLabel}>LINKED TASKS</span>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
        {linkedTasks.map(t => (
          <span key={t.id} style={{
            fontSize: 9, color: '#22d3ee', background: 'rgba(34,211,238,0.06)',
            border: '1px solid rgba(34,211,238,0.18)', borderRadius: 3, padding: '2px 7px',
            display: 'flex', alignItems: 'center', gap: 4,
          }}>
            {t.title}
            <button
              onClick={() => onUnlink(t.id)}
              style={{ background: 'none', border: 'none', color: '#475569', cursor: 'pointer', fontSize: 10, padding: 0 }}
            >
              ✕
            </button>
          </span>
        ))}
        {linkedTasks.length === 0 && (
          <span style={{ fontSize: 9, color: '#1e2d3d', fontFamily: 'var(--font-mono)' }}>NO LINKED TASKS</span>
        )}
      </div>
      <input
        value={taskSearch}
        onChange={e => setTaskSearch(e.target.value)}
        placeholder="Search tasks to link…"
        style={{
          width: '100%', boxSizing: 'border-box',
          background: '#0a1220', border: '1px solid rgba(100,140,200,0.14)',
          borderRadius: 4, color: '#94a3b8', fontSize: 10, padding: '5px 8px',
          fontFamily: 'inherit', outline: 'none',
        }}
      />
      {searchResults.map(t => (
        <button
          key={t.id}
          onClick={() => onLink(t.id)}
          style={{
            display: 'block', width: '100%', textAlign: 'left',
            background: 'rgba(34,211,238,0.04)', border: '1px solid rgba(34,211,238,0.1)',
            borderRadius: 3, padding: '4px 8px', color: '#94a3b8', fontSize: 10,
            cursor: 'pointer', marginTop: 2,
          }}
        >
          + {t.title}
        </button>
      ))}
    </div>
  )
}

function EntriesTab({
  entries, type, editingEntry, showEditor,
  onAdd, onEdit, onDelete, onSaveNew, onSaveEdit, onCancelEditor,
}: {
  entries: ExperimentEntry[]
  type: 'note' | 'result'
  editingEntry: ExperimentEntry | null
  showEditor: boolean
  onAdd: () => void
  onEdit: (e: ExperimentEntry) => void
  onDelete: (id: string) => void
  onSaveNew: (data: { title: string; body: string }) => void
  onSaveEdit: (data: { title: string; body: string }) => void
  onCancelEditor: () => void
}) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const label = type === 'note' ? 'NOTE' : 'RESULT'
  const accent = type === 'note' ? '#22d3ee' : '#10b981'

  return (
    <div>
      <button
        onClick={onAdd}
        style={{
          width: '100%', background: `${accent}10`, border: `1px solid ${accent}33`,
          borderRadius: 4, padding: '6px', color: accent, fontSize: 9, fontWeight: 700,
          fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', cursor: 'pointer', marginBottom: 10,
        }}
      >
        + ADD {label}
      </button>

      {showEditor && (
        <div style={{ marginBottom: 10 }}>
          <EntryEditor type={type} onSave={onSaveNew} onCancel={onCancelEditor} />
        </div>
      )}

      {entries.length === 0 && !showEditor && (
        <div style={{ fontSize: 8, color: '#1e2d3d', textAlign: 'center', fontFamily: 'var(--font-mono)', marginTop: 12 }}>
          NO {label}S YET
        </div>
      )}

      {entries.map(entry => (
        <div key={entry.id} style={{ marginBottom: 6 }}>
          {editingEntry?.id === entry.id ? (
            <EntryEditor
              type={type}
              initialTitle={entry.title}
              initialBody={entry.body}
              onSave={onSaveEdit}
              onCancel={onCancelEditor}
            />
          ) : (
            <div style={{ border: `1px solid ${accent}22`, borderRadius: 4, overflow: 'hidden' }}>
              <button
                onClick={() => setExpanded(expanded === entry.id ? null : entry.id)}
                style={{
                  width: '100%', background: `${accent}08`, padding: '6px 8px',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  border: 'none', cursor: 'pointer',
                }}
              >
                <span style={{ fontSize: 10, color: '#cbd5e1', fontWeight: 600 }}>{entry.title}</span>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span style={{ fontSize: 7, color: '#334155' }}>{entry.created_at.slice(0, 10)}</span>
                  <span style={{ fontSize: 9, color: '#475569' }}>{expanded === entry.id ? '▲' : '▼'}</span>
                </div>
              </button>
              {expanded === entry.id && (
                <div style={{ padding: '8px 10px', background: '#070b12' }}>
                  {entry.body ? (
                    <pre style={{ fontSize: 9, color: '#94a3b8', fontFamily: 'var(--font-mono)', whiteSpace: 'pre-wrap', margin: '0 0 8px', lineHeight: 1.6 }}>
                      {entry.body}
                    </pre>
                  ) : (
                    <p style={{ fontSize: 9, color: '#334155', margin: '0 0 8px' }}>No content.</p>
                  )}
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button onClick={() => onEdit(entry)} style={{ fontSize: 8, color: '#22d3ee', background: 'rgba(34,211,238,0.06)', border: '1px solid rgba(34,211,238,0.15)', borderRadius: 2, padding: '2px 6px', cursor: 'pointer', fontFamily: 'var(--font-mono)' }}>✏ Edit</button>
                    <button onClick={() => onDelete(entry.id)} style={{ fontSize: 8, color: '#f43f5e', background: 'rgba(244,63,94,0.06)', border: '1px solid rgba(244,63,94,0.15)', borderRadius: 2, padding: '2px 6px', cursor: 'pointer', fontFamily: 'var(--font-mono)' }}>✕ Delete</button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run src/components/__tests__/ExperimentDetail.test.tsx --reporter=verbose 2>&1 | tail -10
```

Expected: 6 tests PASS

- [ ] **Step 5: Run full frontend suite**

```bash
npx vitest run --reporter=verbose 2>&1 | tail -8
```

Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
git add EvoScientist/pm/frontend/src/components/ExperimentDetail.tsx \
        EvoScientist/pm/frontend/src/components/__tests__/ExperimentDetail.test.tsx
git commit -m "feat(pm/frontend): add ExperimentDetail drawer with OVERVIEW/NOTES/RESULTS tabs"
```

---

## Task 7: `ExperimentsPage`

**Files:**
- Create: `EvoScientist/pm/frontend/src/pages/ExperimentsPage.tsx`
- Create: `EvoScientist/pm/frontend/src/pages/__tests__/ExperimentsPage.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `EvoScientist/pm/frontend/src/pages/__tests__/ExperimentsPage.test.tsx`:

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ExperimentsPage } from '../ExperimentsPage'
import type { Experiment } from '../../api'

vi.mock('../../api', () => ({
  api: {
    getProject: vi.fn().mockResolvedValue({
      id: 'p1', name: 'CRISPR', members: [{ user_id: 'u1', username: 'owner', role: 'owner', added_at: '' }],
      description: null, created_by: 'u1', created_at: '', archived_at: null,
    }),
    listExperiments: vi.fn().mockResolvedValue([]),
    createExperiment: vi.fn().mockResolvedValue({
      id: 'exp1', project_id: 'p1', name: 'Western Blot', hypothesis: null,
      protocol: null, status: 'planned', tags: [], deadline: null,
      created_by: 'u1', created_at: '2026-01-01', updated_at: '2026-01-01',
    }),
  },
}))

vi.mock('../../auth', () => ({
  useAuth: vi.fn(() => ({ username: 'owner', token: 'tok' })),
}))

vi.mock('../components/ExperimentDetail', () => ({
  ExperimentDetail: () => <div data-testid="experiment-detail" />,
}))

const MOCK_EXP: Experiment = {
  id: 'exp1', project_id: 'p1', name: 'Western Blot #1',
  hypothesis: 'Protein expressed', protocol: null, status: 'planned',
  tags: ['blot'], deadline: null, created_by: 'u1',
  created_at: '2026-01-01', updated_at: '2026-01-01',
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/projects/p1/experiments']}>
        <Routes>
          <Route path="/projects/:id/experiments" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ExperimentsPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders project name in header', async () => {
    render(wrap(<ExperimentsPage />))
    await waitFor(() => expect(screen.getByText(/CRISPR/i)).toBeInTheDocument())
  })

  it('shows empty state when no experiments', async () => {
    render(wrap(<ExperimentsPage />))
    await waitFor(() => expect(screen.getByText(/NO EXPERIMENTS/i)).toBeInTheDocument())
  })

  it('shows experiment cards when experiments exist', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listExperiments).mockResolvedValue([MOCK_EXP])
    render(wrap(<ExperimentsPage />))
    await waitFor(() => expect(screen.getByText('Western Blot #1')).toBeInTheDocument())
  })

  it('shows NEW EXPERIMENT button', async () => {
    render(wrap(<ExperimentsPage />))
    await waitFor(() => expect(screen.getByRole('button', { name: /NEW EXPERIMENT/i })).toBeInTheDocument())
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist/EvoScientist/pm/frontend
npx vitest run src/pages/__tests__/ExperimentsPage.test.tsx --reporter=verbose 2>&1 | tail -10
```

Expected: FAIL with `Cannot find module`

- [ ] **Step 3: Create `EvoScientist/pm/frontend/src/pages/ExperimentsPage.tsx`**

```tsx
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Experiment } from '../api'
import { ExperimentDetail } from '../components/ExperimentDetail'

const STATUS_COLORS: Record<string, string> = {
  planned: '#f59e0b', running: '#22d3ee', completed: '#10b981',
}

export function ExperimentsPage() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const [selectedExp, setSelectedExp] = useState<Experiment | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
    enabled: Boolean(projectId),
  })

  const { data: experiments = [] } = useQuery({
    queryKey: ['experiments', projectId],
    queryFn: () => api.listExperiments(projectId!),
    enabled: Boolean(projectId),
  })

  const createMutation = useMutation({
    mutationFn: () => api.createExperiment(projectId!, { name: newName.trim() }),
    onSuccess: (exp) => {
      qc.invalidateQueries({ queryKey: ['experiments', projectId] })
      setShowCreate(false)
      setNewName('')
      setSelectedExp(exp)
    },
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#070b12', color: '#f1f5f9' }}>
      {/* Header */}
      <div style={{
        padding: '0 24px', height: 52,
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 14,
        background: 'rgba(13,21,38,0.85)',
        backdropFilter: 'blur(12px)',
        position: 'sticky', top: 0, zIndex: 10, flexShrink: 0,
      }}>
        <button
          onClick={() => navigate(`/projects/${projectId}`)}
          style={{
            cursor: 'pointer', background: 'rgba(100,140,200,0.07)',
            border: '1px solid rgba(100,140,200,0.14)', borderRadius: 6,
            color: '#64748b', padding: '3px 9px', fontSize: 15, lineHeight: 1,
          }}
        >←</button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', boxShadow: '0 0 6px #10b981', flexShrink: 0 }} />
          <h1 style={{ margin: 0, fontSize: 14, fontWeight: 600, letterSpacing: '0.03em', color: '#f1f5f9', fontFamily: 'var(--font-mono)' }}>
            {project?.name ?? '…'} — Experiments
          </h1>
        </div>

        <div style={{ marginLeft: 'auto' }}>
          <button
            onClick={() => setShowCreate(true)}
            style={{
              background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.28)',
              borderRadius: 4, padding: '4px 12px', color: '#10b981',
              fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)',
              letterSpacing: '0.08em', cursor: 'pointer',
            }}
          >
            + NEW EXPERIMENT
          </button>
        </div>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
        }}>
          <div style={{ background: '#0d1526', border: '1px solid rgba(100,140,200,0.2)', borderRadius: 8, padding: 24, width: 360 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#22d3ee', fontFamily: 'var(--font-mono)', marginBottom: 12 }}>
              NEW EXPERIMENT
            </div>
            <input
              value={newName}
              onChange={e => setNewName(e.target.value)}
              placeholder="Experiment name…"
              autoFocus
              onKeyDown={e => e.key === 'Enter' && newName.trim() && createMutation.mutate()}
              style={{
                width: '100%', boxSizing: 'border-box',
                background: '#070b12', border: '1px solid rgba(100,140,200,0.18)',
                borderRadius: 4, color: '#e2e8f0', fontSize: 13, padding: '8px 10px',
                fontFamily: 'inherit', outline: 'none', marginBottom: 12,
              }}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={() => { setShowCreate(false); setNewName('') }} style={{ background: 'rgba(100,140,200,0.06)', border: '1px solid rgba(100,140,200,0.14)', borderRadius: 4, padding: '5px 12px', color: '#64748b', fontSize: 10, cursor: 'pointer', fontFamily: 'var(--font-mono)' }}>CANCEL</button>
              <button
                onClick={() => createMutation.mutate()}
                disabled={!newName.trim()}
                style={{ background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.28)', borderRadius: 4, padding: '5px 12px', color: '#10b981', fontSize: 10, fontWeight: 700, cursor: 'pointer', fontFamily: 'var(--font-mono)', opacity: !newName.trim() ? 0.4 : 1 }}
              >
                CREATE
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Experiment grid */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        {experiments.length === 0 ? (
          <div style={{ textAlign: 'center', color: '#1e2d3d', fontFamily: 'var(--font-mono)', fontSize: 11, marginTop: 60 }}>
            NO EXPERIMENTS YET
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
            {experiments.map(exp => (
              <ExperimentCard key={exp.id} exp={exp} onClick={() => setSelectedExp(exp)} />
            ))}
          </div>
        )}
      </div>

      {selectedExp && (
        <ExperimentDetail
          key={selectedExp.id}
          experiment={selectedExp}
          projectId={projectId!}
          onClose={() => setSelectedExp(null)}
        />
      )}
    </div>
  )
}

function ExperimentCard({ exp, onClick }: { exp: Experiment; onClick: () => void }) {
  const color = STATUS_COLORS[exp.status] ?? '#64748b'
  return (
    <div
      onClick={onClick}
      style={{
        background: 'rgba(17,30,53,0.75)', border: '1px solid rgba(100,140,200,0.09)',
        borderRadius: 8, padding: '14px 16px', cursor: 'pointer',
        transition: 'border-color 0.15s',
      }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(100,140,200,0.25)')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(100,140,200,0.09)')}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#f1f5f9', lineHeight: 1.3 }}>{exp.name}</div>
        <span style={{
          fontSize: 7, fontWeight: 700, fontFamily: 'var(--font-mono)',
          color, background: `${color}18`, border: `1px solid ${color}33`,
          borderRadius: 2, padding: '1px 5px', flexShrink: 0, marginLeft: 8,
        }}>
          {exp.status.toUpperCase()}
        </span>
      </div>
      {exp.hypothesis && (
        <p style={{ fontSize: 10, color: '#64748b', margin: '0 0 8px', lineHeight: 1.5, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
          {exp.hypothesis}
        </p>
      )}
      {exp.tags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
          {exp.tags.map(tag => (
            <span key={tag} style={{ fontSize: 7, color: '#475569', background: 'rgba(100,140,200,0.06)', border: '1px solid rgba(100,140,200,0.1)', borderRadius: 2, padding: '1px 4px' }}>
              {tag}
            </span>
          ))}
        </div>
      )}
      {exp.deadline && (
        <div style={{ fontSize: 9, color: '#475569', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
          DEADLINE: {exp.deadline}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npx vitest run src/pages/__tests__/ExperimentsPage.test.tsx --reporter=verbose 2>&1 | tail -10
```

Expected: 4 tests PASS

- [ ] **Step 5: Run full frontend suite**

```bash
npx vitest run 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
git add EvoScientist/pm/frontend/src/pages/ExperimentsPage.tsx \
        EvoScientist/pm/frontend/src/pages/__tests__/ExperimentsPage.test.tsx
git commit -m "feat(pm/frontend): add ExperimentsPage with grid layout and create modal"
```

---

## Task 8: Routing — Board.tsx header button + main.tsx route

**Files:**
- Modify: `EvoScientist/pm/frontend/src/main.tsx`
- Modify: `EvoScientist/pm/frontend/src/pages/Board.tsx`

- [ ] **Step 1: Add route to `main.tsx`**

Read `EvoScientist/pm/frontend/src/main.tsx`. After the line:
```typescript
import { Board } from './pages/Board'
```
add:
```typescript
import { ExperimentsPage } from './pages/ExperimentsPage'
```

After:
```tsx
<Route path="/projects/:id" element={<PrivateRoute><Board /></PrivateRoute>} />
```
add:
```tsx
<Route path="/projects/:id/experiments" element={<PrivateRoute><ExperimentsPage /></PrivateRoute>} />
```

- [ ] **Step 2: Add ⚗ EXPERIMENTS button to `Board.tsx` header**

Read `EvoScientist/pm/frontend/src/pages/Board.tsx`. Find the header section with the `⚙ SETTINGS` button (around line 453). Inside the same `div` that contains the SETTINGS button, add the EXPERIMENTS button immediately before the SETTINGS button:

```tsx
<button
  onClick={() => navigate(`/projects/${projectId}/experiments`)}
  style={{
    background: 'rgba(16,185,129,0.08)',
    border: '1px solid rgba(16,185,129,0.18)',
    color: '#64748b',
    fontFamily: 'var(--font-mono)',
    fontSize: 11,
    padding: '4px 10px',
    borderRadius: 4,
    cursor: 'pointer',
    letterSpacing: '0.08em',
  }}
  onMouseEnter={e => { e.currentTarget.style.color = '#10b981'; e.currentTarget.style.borderColor = 'rgba(16,185,129,0.35)' }}
  onMouseLeave={e => { e.currentTarget.style.color = '#64748b'; e.currentTarget.style.borderColor = 'rgba(16,185,129,0.18)' }}
>
  ⚗ EXPERIMENTS
</button>
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist/EvoScientist/pm/frontend
npx tsc --noEmit 2>&1
```

Expected: zero errors

- [ ] **Step 4: Run full test suite + build**

```bash
npx vitest run 2>&1 | tail -5 && npx vite build 2>&1 | tail -5
```

Expected: all tests pass, build succeeds

- [ ] **Step 5: Run full backend test suite**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
uv run pytest tests/pm/ -q --timeout=30 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add EvoScientist/pm/frontend/src/main.tsx \
        EvoScientist/pm/frontend/src/pages/Board.tsx
git commit -m "feat(pm/frontend): add experiments route and ⚗ EXPERIMENTS button to board header"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|-----------------|------|
| `experiments` table with status CHECK, tags JSON, deadline | Task 1 |
| `experiment_tasks` join table | Task 1 |
| `experiment_entries` table with type CHECK | Task 1 |
| `Experiment`, `ExperimentEntry` dataclasses | Task 1 |
| CRUD: create/get/list/update/delete experiment | Task 1 |
| link_task / unlink_task / list_linked_tasks | Task 1 |
| 409 on duplicate task link | Task 1 |
| ExperimentEntry CRUD with type filter | Task 2 |
| API schemas: ExperimentCreate, ExperimentUpdate, ExperimentResponse | Task 3 |
| API schemas: ExperimentEntryCreate, ExperimentEntryUpdate, ExperimentEntryResponse | Task 3 |
| All 11 API routes | Task 3 |
| 422 when task belongs to different project | Task 3 |
| Viewer cannot create/edit/delete | Task 3 (require_project_role) |
| Frontend Experiment + ExperimentEntry interfaces | Task 4 |
| 11 API functions in api.ts | Task 4 |
| EntryEditor component | Task 5 |
| ExperimentDetail drawer (OVERVIEW/NOTES/RESULTS) | Task 6 |
| Task linking UI in OVERVIEW tab | Task 6 |
| ExperimentsPage with grid + create modal | Task 7 |
| ⚗ EXPERIMENTS button in Board header | Task 8 |
| `/projects/:id/experiments` route | Task 8 |

All spec requirements covered.

**Placeholder scan:** No TBD or incomplete steps. All code blocks are complete.

**Type consistency:**
- `create_entry(db, experiment_id, entry_type, ...)` in Task 2 matches calls in Task 3 routes ✅
- `api.createEntry(projectId, expId, { type, title, body })` in Task 4 matches `ExperimentDetail` usage in Task 6 ✅
- `api.listEntries(projectId, expId, type?)` signature consistent across Task 4 and Task 6 ✅
- `_LinkTaskBody` inline trick in Task 3 explicitly called out with fix instruction ✅
