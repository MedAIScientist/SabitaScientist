# Workflow Coordination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project phases (named swimlane groups) and task dependency tracking (hard blocks + soft links with BFS cycle detection) to the PM system.

**Architecture:** Two independent subsystems — Phases (project_phases table + phase_id FK on tasks/experiments) and Dependencies (task_dependencies table with BFS cycle detection) — with no shared logic but unified UI integration in Board and TaskDetail.

**Tech Stack:** FastAPI, SQLite (via existing `get_db` context manager), Pydantic v2, React + TypeScript, @dnd-kit/core, TanStack Query v5

---

## File Map

| Action | File |
|--------|------|
| Modify | `EvoScientist/pm/db.py` |
| Modify | `EvoScientist/pm/models.py` |
| Modify | `EvoScientist/pm/crud/tasks.py` |
| Create | `EvoScientist/pm/crud/phases.py` |
| Create | `EvoScientist/pm/crud/dependencies.py` |
| Modify | `EvoScientist/pm/api/schemas.py` |
| Create | `EvoScientist/pm/api/routes/phases.py` |
| Create | `EvoScientist/pm/api/routes/dependencies.py` |
| Modify | `EvoScientist/pm/api/routes/tasks.py` |
| Modify | `EvoScientist/pm/api/app.py` |
| Modify | `EvoScientist/pm/frontend/src/api.ts` |
| Create | `EvoScientist/pm/frontend/src/components/PhaseManager.tsx` |
| Create | `EvoScientist/pm/frontend/src/components/DependencyPicker.tsx` |
| Modify | `EvoScientist/pm/frontend/src/components/ProjectSettingsPanel.tsx` |
| Modify | `EvoScientist/pm/frontend/src/pages/Board.tsx` |
| Modify | `EvoScientist/pm/frontend/src/pages/TaskDetail.tsx` |
| Modify | `EvoScientist/pm/frontend/src/pages/ExperimentsPage.tsx` |
| Create | `tests/pm/test_phase_crud.py` |
| Create | `tests/pm/test_dependency_crud.py` |
| Create | `tests/pm/test_phase_routes.py` |
| Create | `tests/pm/test_dependency_routes.py` |

---

### Task 1: DB Schema + Dataclasses

**Files:**
- Modify: `EvoScientist/pm/db.py`
- Modify: `EvoScientist/pm/models.py`
- Modify: `EvoScientist/pm/crud/tasks.py`
- Test: `tests/pm/test_db.py` (extend)

- [ ] **Step 1: Write the failing test**

Add to `tests/pm/test_db.py`:

```python
def test_project_phases_table_exists(tmp_path):
    from EvoScientist.pm.db import create_schema
    db = tmp_path / "t.db"
    create_schema(db)
    import sqlite3
    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "project_phases" in tables
    assert "task_dependencies" in tables
    conn.close()

def test_tasks_has_phase_id_column(tmp_path):
    from EvoScientist.pm.db import create_schema
    db = tmp_path / "t.db"
    create_schema(db)
    import sqlite3
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    assert "phase_id" in cols
    conn.close()

def test_experiments_has_phase_id_column(tmp_path):
    from EvoScientist.pm.db import create_schema
    db = tmp_path / "t.db"
    create_schema(db)
    import sqlite3
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(experiments)").fetchall()}
    assert "phase_id" in cols
    conn.close()

def test_create_schema_idempotent_with_migrations(tmp_path):
    """Running create_schema twice must not fail (migration columns already exist)."""
    from EvoScientist.pm.db import create_schema
    db = tmp_path / "t.db"
    create_schema(db)
    create_schema(db)  # second call must not raise
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
uv run pytest tests/pm/test_db.py::test_project_phases_table_exists \
    tests/pm/test_db.py::test_tasks_has_phase_id_column \
    tests/pm/test_db.py::test_experiments_has_phase_id_column \
    tests/pm/test_db.py::test_create_schema_idempotent_with_migrations -v
```

Expected: FAIL (tables/columns not yet added)

- [ ] **Step 3: Add tables and migration to `db.py`**

Append to `_SCHEMA` (inside the triple-quoted string, before the closing `"""`):

```sql
CREATE TABLE IF NOT EXISTS project_phases (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    color       TEXT NOT NULL DEFAULT '#6366f1',
    position    INTEGER NOT NULL DEFAULT 0,
    target_date TEXT,
    created_by  TEXT NOT NULL REFERENCES users(id),
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_phases_project ON project_phases(project_id);

CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id       TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    depends_on_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    dep_type      TEXT NOT NULL DEFAULT 'hard'
                  CHECK(dep_type IN ('hard', 'soft')),
    created_by    TEXT NOT NULL REFERENCES users(id),
    created_at    TEXT NOT NULL,
    PRIMARY KEY (task_id, depends_on_id)
);
```

Add `_MIGRATIONS` list and update `create_schema` in `db.py`:

```python
_MIGRATIONS = [
    "ALTER TABLE tasks ADD COLUMN phase_id TEXT REFERENCES project_phases(id) ON DELETE SET NULL",
    "ALTER TABLE experiments ADD COLUMN phase_id TEXT REFERENCES project_phases(id) ON DELETE SET NULL",
]


def create_schema(db_path: Path | None = None) -> None:
    """Create all PM tables if they don't already exist (idempotent)."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA)
        for migration in _MIGRATIONS:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError:
                pass  # column already exists
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 4: Add dataclasses to `models.py`**

Append to the end of `EvoScientist/pm/models.py`:

```python
@dataclass
class ProjectPhase:
    id: str
    project_id: str
    name: str
    color: str
    position: int
    created_by: str
    created_at: str
    target_date: str | None = None


@dataclass
class TaskDependency:
    task_id: str
    depends_on_id: str
    dep_type: str
    created_by: str
    created_at: str
```

- [ ] **Step 5: Add `phase_id` to `Task` dataclass and update `_row_to_task`**

In `models.py`, add to `Task` dataclass (after `session_id` field):

```python
    phase_id: str | None = None
```

In `EvoScientist/pm/crud/tasks.py`, update `_row_to_task` to include phase_id:

```python
def _row_to_task(row) -> Task:
    return Task(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        description=row["description"],
        assignee_id=row["assignee_id"],
        status=row["status"],
        priority=row["priority"],
        deadline=row["deadline"],
        session_id=row["session_id"],
        phase_id=row["phase_id"] if "phase_id" in row.keys() else None,
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
```

Also update `update_task` to preserve `phase_id` in the new Task object (find the `new = Task(...)` block and add `phase_id=task.phase_id,`):

```python
    new = Task(
        id=task.id,
        project_id=task.project_id,
        title=title if title is not None else task.title,
        description=description if description is not None else task.description,
        assignee_id=assignee_id if assignee_id is not None else task.assignee_id,
        status=status if status is not None else task.status,
        priority=priority if priority is not None else task.priority,
        deadline=deadline if deadline is not None else task.deadline,
        session_id=session_id if session_id is not None else task.session_id,
        phase_id=task.phase_id,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=now,
    )
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
uv run pytest tests/pm/test_db.py::test_project_phases_table_exists \
    tests/pm/test_db.py::test_tasks_has_phase_id_column \
    tests/pm/test_db.py::test_experiments_has_phase_id_column \
    tests/pm/test_db.py::test_create_schema_idempotent_with_migrations -v
```

Expected: all PASS

- [ ] **Step 7: Run full suite to check no regressions**

```bash
uv run pytest tests/pm/ -v --timeout=30
```

Expected: all existing tests PASS

- [ ] **Step 8: Commit**

```bash
git add EvoScientist/pm/db.py EvoScientist/pm/models.py EvoScientist/pm/crud/tasks.py tests/pm/test_db.py
git commit -m "feat(pm): add project_phases and task_dependencies schema + dataclasses"
```

---

### Task 2: Phase CRUD

**Files:**
- Create: `EvoScientist/pm/crud/phases.py`
- Create: `tests/pm/test_phase_crud.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/pm/test_phase_crud.py`:

```python
"""Tests for ProjectPhase CRUD operations."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from EvoScientist.pm.crud.phases import (
    assign_experiment_phase,
    assign_task_phase,
    create_phase,
    delete_phase,
    get_phase,
    list_phases,
    update_phase,
)
from EvoScientist.pm.db import create_schema


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    create_schema(path)
    now = "2024-01-01T00:00:00"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES (?,?,?,?,?)",
        ("u1", "alice", "hash", 0, now),
    )
    conn.execute(
        "INSERT INTO projects (id, name, created_by, created_at) VALUES (?,?,?,?)",
        ("p1", "Proj", "u1", now),
    )
    conn.execute(
        "INSERT INTO project_members (project_id, user_id, role, added_at) VALUES (?,?,?,?)",
        ("p1", "u1", "owner", now),
    )
    conn.execute(
        """INSERT INTO tasks
           (id, project_id, title, status, priority, created_by, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        ("t1", "p1", "Task 1", "todo", "medium", "u1", now, now),
    )
    conn.execute(
        """INSERT INTO experiments (id, project_id, name, status, tags,
           created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
        ("e1", "p1", "Exp 1", "planned", "[]", "u1", now, now),
    )
    conn.commit()
    conn.close()
    return path


def test_create_phase(db_path):
    p = create_phase(db_path, project_id="p1", name="Data Collection",
                     color="#6366f1", position=0, target_date=None, created_by="u1")
    assert p.id
    assert p.project_id == "p1"
    assert p.name == "Data Collection"
    assert p.color == "#6366f1"
    assert p.position == 0
    assert p.target_date is None


def test_list_phases_ordered_by_position(db_path):
    create_phase(db_path, "p1", "Phase B", "#ff0000", 2, None, "u1")
    create_phase(db_path, "p1", "Phase A", "#00ff00", 0, None, "u1")
    create_phase(db_path, "p1", "Phase C", "#0000ff", 1, None, "u1")
    phases = list_phases(db_path, "p1")
    assert [p.position for p in phases] == [0, 1, 2]


def test_get_phase(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    fetched = get_phase(db_path, p.id)
    assert fetched is not None
    assert fetched.id == p.id
    assert fetched.name == "P"


def test_get_phase_not_found(db_path):
    assert get_phase(db_path, "nonexistent") is None


def test_update_phase_name(db_path):
    p = create_phase(db_path, "p1", "Old Name", "#6366f1", 0, None, "u1")
    updated = update_phase(db_path, p.id, name="New Name")
    assert updated.name == "New Name"
    assert updated.color == "#6366f1"


def test_update_phase_target_date(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    updated = update_phase(db_path, p.id, target_date="2024-06-01")
    assert updated.target_date == "2024-06-01"


def test_delete_phase_tasks_become_unphased(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    assign_task_phase(db_path, "t1", p.id)
    delete_phase(db_path, p.id)
    # Phase is gone
    assert get_phase(db_path, p.id) is None
    # Task's phase_id is NULL
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT phase_id FROM tasks WHERE id='t1'").fetchone()
    conn.close()
    assert row[0] is None


def test_assign_task_phase(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    assign_task_phase(db_path, "t1", p.id)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT phase_id FROM tasks WHERE id='t1'").fetchone()
    conn.close()
    assert row[0] == p.id


def test_assign_task_phase_unassign(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    assign_task_phase(db_path, "t1", p.id)
    assign_task_phase(db_path, "t1", None)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT phase_id FROM tasks WHERE id='t1'").fetchone()
    conn.close()
    assert row[0] is None


def test_assign_experiment_phase(db_path):
    p = create_phase(db_path, "p1", "P", "#6366f1", 0, None, "u1")
    assign_experiment_phase(db_path, "e1", p.id)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT phase_id FROM experiments WHERE id='e1'").fetchone()
    conn.close()
    assert row[0] == p.id
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/pm/test_phase_crud.py -v
```

Expected: FAIL (`No module named 'EvoScientist.pm.crud.phases'`)

- [ ] **Step 3: Implement `crud/phases.py`**

Create `EvoScientist/pm/crud/phases.py`:

```python
"""CRUD operations for ProjectPhase entities."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import ProjectPhase


def _row_to_phase(row) -> ProjectPhase:
    return ProjectPhase(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        color=row["color"],
        position=row["position"],
        target_date=row["target_date"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def create_phase(
    db_path: Path,
    project_id: str,
    name: str,
    color: str,
    position: int,
    target_date: str | None,
    created_by: str,
) -> ProjectPhase:
    """Insert a new phase and return it."""
    phase_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO project_phases
               (id, project_id, name, color, position, target_date, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (phase_id, project_id, name, color, position, target_date, created_by, now),
        )
    return ProjectPhase(
        id=phase_id, project_id=project_id, name=name, color=color,
        position=position, target_date=target_date, created_by=created_by, created_at=now,
    )


def list_phases(db_path: Path, project_id: str) -> list[ProjectPhase]:
    """Return phases for a project ordered by position."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM project_phases WHERE project_id = ? ORDER BY position ASC",
            (project_id,),
        ).fetchall()
    return [_row_to_phase(r) for r in rows]


def get_phase(db_path: Path, phase_id: str) -> ProjectPhase | None:
    """Return a phase by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM project_phases WHERE id = ?", (phase_id,)
        ).fetchone()
    return _row_to_phase(row) if row else None


def update_phase(db_path: Path, phase_id: str, **kwargs) -> ProjectPhase:
    """Update phase fields. Only keys in kwargs are modified."""
    allowed = {"name", "color", "position", "target_date"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [phase_id]
        with get_db(db_path) as conn:
            conn.execute(
                f"UPDATE project_phases SET {set_clause} WHERE id = ?", values
            )
    phase = get_phase(db_path, phase_id)
    if phase is None:
        raise ValueError(f"Phase {phase_id!r} not found")
    return phase


def delete_phase(db_path: Path, phase_id: str) -> None:
    """Delete a phase; owned tasks/experiments have phase_id set to NULL by FK."""
    with get_db(db_path) as conn:
        conn.execute("DELETE FROM project_phases WHERE id = ?", (phase_id,))


def assign_task_phase(db_path: Path, task_id: str, phase_id: str | None) -> None:
    """Assign or unassign a task to a phase."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE tasks SET phase_id = ? WHERE id = ?", (phase_id, task_id)
        )


def assign_experiment_phase(db_path: Path, experiment_id: str, phase_id: str | None) -> None:
    """Assign or unassign an experiment to a phase."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE experiments SET phase_id = ? WHERE id = ?", (phase_id, experiment_id)
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/pm/test_phase_crud.py -v
```

Expected: all PASS

- [ ] **Step 5: Run full suite**

```bash
uv run pytest tests/pm/ -v --timeout=30
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add EvoScientist/pm/crud/phases.py tests/pm/test_phase_crud.py
git commit -m "feat(pm): add phase CRUD layer"
```

---

### Task 3: Dependency CRUD + Cycle Detection

**Files:**
- Create: `EvoScientist/pm/crud/dependencies.py`
- Create: `tests/pm/test_dependency_crud.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/pm/test_dependency_crud.py`:

```python
"""Tests for TaskDependency CRUD + cycle detection."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from EvoScientist.pm.crud.dependencies import (
    add_dependency,
    get_blocked_by,
    list_dependencies,
    list_dependents,
    remove_dependency,
)
from EvoScientist.pm.db import create_schema


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    create_schema(path)
    now = "2024-01-01T00:00:00"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES (?,?,?,?,?)",
        ("u1", "alice", "hash", 0, now),
    )
    conn.execute(
        "INSERT INTO projects (id, name, created_by, created_at) VALUES (?,?,?,?)",
        ("p1", "Proj", "u1", now),
    )
    conn.execute(
        "INSERT INTO projects (id, name, created_by, created_at) VALUES (?,?,?,?)",
        ("p2", "Other", "u1", now),
    )
    for tid in ["t1", "t2", "t3"]:
        conn.execute(
            """INSERT INTO tasks
               (id, project_id, title, status, priority, created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (tid, "p1", f"Task {tid}", "todo", "medium", "u1", now, now),
        )
    # t4 belongs to p2 (cross-project)
    conn.execute(
        """INSERT INTO tasks
           (id, project_id, title, status, priority, created_by, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        ("t4", "p2", "Cross Project Task", "todo", "medium", "u1", now, now),
    )
    conn.commit()
    conn.close()
    return path


def test_add_hard_dependency(db_path):
    dep = add_dependency(db_path, "t2", "t1", "hard", "u1")
    assert dep.task_id == "t2"
    assert dep.depends_on_id == "t1"
    assert dep.dep_type == "hard"


def test_add_soft_dependency(db_path):
    dep = add_dependency(db_path, "t2", "t1", "soft", "u1")
    assert dep.dep_type == "soft"


def test_self_dependency_raises(db_path):
    with pytest.raises(ValueError, match="cannot depend on itself"):
        add_dependency(db_path, "t1", "t1", "hard", "u1")


def test_cross_project_dependency_raises(db_path):
    with pytest.raises(ValueError, match="same project"):
        add_dependency(db_path, "t1", "t4", "hard", "u1")


def test_cycle_detection_simple(db_path):
    add_dependency(db_path, "t2", "t1", "hard", "u1")
    # t1 → t2 already (t2 depends on t1); adding t1 depends on t2 creates cycle
    with pytest.raises(ValueError, match="cycle"):
        add_dependency(db_path, "t1", "t2", "hard", "u1")


def test_cycle_detection_transitive(db_path):
    add_dependency(db_path, "t2", "t1", "hard", "u1")
    add_dependency(db_path, "t3", "t2", "hard", "u1")
    # t3 → t2 → t1; adding t1 depends on t3 creates cycle
    with pytest.raises(ValueError, match="cycle"):
        add_dependency(db_path, "t1", "t3", "hard", "u1")


def test_remove_dependency(db_path):
    add_dependency(db_path, "t2", "t1", "hard", "u1")
    remove_dependency(db_path, "t2", "t1")
    assert list_dependencies(db_path, "t2") == []


def test_list_dependencies(db_path):
    add_dependency(db_path, "t2", "t1", "hard", "u1")
    add_dependency(db_path, "t2", "t3", "soft", "u1")
    deps = list_dependencies(db_path, "t2")
    assert len(deps) == 2
    dep_ids = {d.depends_on_id for d in deps}
    assert dep_ids == {"t1", "t3"}


def test_list_dependents(db_path):
    add_dependency(db_path, "t2", "t1", "hard", "u1")
    add_dependency(db_path, "t3", "t1", "soft", "u1")
    dependents = list_dependents(db_path, "t1")
    assert len(dependents) == 2
    assert {d.task_id for d in dependents} == {"t2", "t3"}


def test_get_blocked_by_only_hard_incomplete(db_path):
    # t1 is todo (not done), hard blocker of t2
    add_dependency(db_path, "t2", "t1", "hard", "u1")
    blocked = get_blocked_by(db_path, "t2")
    assert "t1" in blocked


def test_get_blocked_by_excludes_done_blockers(db_path):
    add_dependency(db_path, "t2", "t1", "hard", "u1")
    # Mark t1 as done
    import sqlite3 as _sq
    conn = _sq.connect(db_path)
    conn.execute("UPDATE tasks SET status='done' WHERE id='t1'")
    conn.commit()
    conn.close()
    blocked = get_blocked_by(db_path, "t2")
    assert blocked == []


def test_get_blocked_by_excludes_soft_deps(db_path):
    add_dependency(db_path, "t2", "t1", "soft", "u1")
    blocked = get_blocked_by(db_path, "t2")
    assert blocked == []


def test_cascade_delete_removes_deps(db_path):
    add_dependency(db_path, "t2", "t1", "hard", "u1")
    import sqlite3 as _sq
    conn = _sq.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM tasks WHERE id='t1'")
    conn.commit()
    conn.close()
    assert list_dependencies(db_path, "t2") == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/pm/test_dependency_crud.py -v
```

Expected: FAIL (`No module named 'EvoScientist.pm.crud.dependencies'`)

- [ ] **Step 3: Implement `crud/dependencies.py`**

Create `EvoScientist/pm/crud/dependencies.py`:

```python
"""CRUD operations for TaskDependency entities, including BFS cycle detection."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import TaskDependency


def _row_to_dep(row: sqlite3.Row) -> TaskDependency:
    return TaskDependency(
        task_id=row["task_id"],
        depends_on_id=row["depends_on_id"],
        dep_type=row["dep_type"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )


def _has_cycle(conn: sqlite3.Connection, project_id: str) -> bool:
    """DFS cycle detection across all dep edges in the project."""
    rows = conn.execute(
        """SELECT td.task_id, td.depends_on_id
           FROM task_dependencies td
           JOIN tasks t ON t.id = td.task_id
           WHERE t.project_id = ?""",
        (project_id,),
    ).fetchall()

    graph: dict[str, list[str]] = {}
    for row in rows:
        graph.setdefault(row[0], []).append(row[1])

    visited: set[str] = set()
    in_stack: set[str] = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        in_stack.add(node)
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in in_stack:
                return True
        in_stack.discard(node)
        return False

    for node in list(graph.keys()):
        if node not in visited:
            if dfs(node):
                return True
    return False


def add_dependency(
    db_path: Path,
    task_id: str,
    depends_on_id: str,
    dep_type: str,
    created_by: str,
) -> TaskDependency:
    """Add a dependency edge. Raises ValueError on self-dep, cross-project, or cycle."""
    if task_id == depends_on_id:
        raise ValueError("task cannot depend on itself")

    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        t1 = conn.execute(
            "SELECT project_id FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        t2 = conn.execute(
            "SELECT project_id FROM tasks WHERE id = ?", (depends_on_id,)
        ).fetchone()
        if not t1 or not t2:
            raise ValueError("task not found")
        if t1["project_id"] != t2["project_id"]:
            raise ValueError("tasks must belong to the same project")
        project_id = t1["project_id"]

        conn.execute(
            """INSERT INTO task_dependencies
               (task_id, depends_on_id, dep_type, created_by, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, depends_on_id, dep_type, created_by, now),
        )

        if _has_cycle(conn, project_id):
            raise ValueError("cycle detected")

    return TaskDependency(
        task_id=task_id,
        depends_on_id=depends_on_id,
        dep_type=dep_type,
        created_by=created_by,
        created_at=now,
    )


def remove_dependency(db_path: Path, task_id: str, depends_on_id: str) -> None:
    """Remove a dependency edge."""
    with get_db(db_path) as conn:
        conn.execute(
            "DELETE FROM task_dependencies WHERE task_id = ? AND depends_on_id = ?",
            (task_id, depends_on_id),
        )


def list_dependencies(db_path: Path, task_id: str) -> list[TaskDependency]:
    """Return dependencies for a task (what this task waits on)."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM task_dependencies WHERE task_id = ?", (task_id,)
        ).fetchall()
    return [_row_to_dep(r) for r in rows]


def list_dependents(db_path: Path, task_id: str) -> list[TaskDependency]:
    """Return dependents (tasks that wait on this task)."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM task_dependencies WHERE depends_on_id = ?", (task_id,)
        ).fetchall()
    return [_row_to_dep(r) for r in rows]


def get_blocked_by(db_path: Path, task_id: str) -> list[str]:
    """Return IDs of hard-blocking tasks not yet done."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT td.depends_on_id
               FROM task_dependencies td
               JOIN tasks t ON t.id = td.depends_on_id
               WHERE td.task_id = ? AND td.dep_type = 'hard' AND t.status != 'done'""",
            (task_id,),
        ).fetchall()
    return [r["depends_on_id"] for r in rows]
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/pm/test_dependency_crud.py -v
```

Expected: all PASS

- [ ] **Step 5: Run full suite**

```bash
uv run pytest tests/pm/ -v --timeout=30
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add EvoScientist/pm/crud/dependencies.py tests/pm/test_dependency_crud.py
git commit -m "feat(pm): add dependency CRUD with DFS cycle detection"
```

---

### Task 4: Pydantic Schemas + Phase Routes + App Registration

**Files:**
- Modify: `EvoScientist/pm/api/schemas.py`
- Create: `EvoScientist/pm/api/routes/phases.py`
- Modify: `EvoScientist/pm/api/app.py`
- Create: `tests/pm/test_phase_routes.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/pm/test_phase_routes.py`:

```python
"""Tests for phase API endpoints."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import pytest
from fastapi.testclient import TestClient

from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.db import create_schema


@pytest.fixture
def auth_client(tmp_path: Path):
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    import EvoScientist.pm.api.deps as deps_mod
    import EvoScientist.pm.api.routes.auth as auth_r
    import EvoScientist.pm.api.routes.experiments as exp_r
    import EvoScientist.pm.api.routes.phases as phases_r
    import EvoScientist.pm.api.routes.projects as proj_r
    import EvoScientist.pm.api.routes.runs as runs_r
    import EvoScientist.pm.api.routes.tasks as tasks_r
    import EvoScientist.pm.api.routes.users as users_r
    import EvoScientist.pm.crud.phases as phases_crud
    import EvoScientist.pm.crud.projects as proj_crud
    import EvoScientist.pm.crud.tasks as tasks_crud
    import EvoScientist.pm.crud.users as users_crud

    for mod in [
        deps_mod, auth_r, exp_r, phases_r, proj_r, runs_r, tasks_r, users_r,
        phases_crud, proj_crud, tasks_crud, users_crud,
    ]:
        if hasattr(mod, "get_db_path"):
            mod.get_db_path = lambda: db_path

    app = create_app(db_path)

    now = datetime.now(timezone.utc).isoformat()
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    pw = bcrypt.hashpw(b"pass123", bcrypt.gensalt()).decode()
    pw2 = bcrypt.hashpw(b"pass123", bcrypt.gensalt()).decode()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES (?,?,?,?,?)",
        ("u1", "alice", pw, 1, now),
    )
    conn.execute(
        "INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES (?,?,?,?,?)",
        ("u2", "bob", pw2, 0, now),
    )
    conn.execute(
        "INSERT INTO projects (id, name, created_by, created_at) VALUES (?,?,?,?)",
        ("p1", "P", "u1", now),
    )
    conn.execute(
        "INSERT INTO project_members (project_id, user_id, role, added_at) VALUES (?,?,?,?)",
        ("p1", "u1", "owner", now),
    )
    conn.execute(
        "INSERT INTO project_members (project_id, user_id, role, added_at) VALUES (?,?,?,?)",
        ("p1", "u2", "viewer", now),
    )
    conn.execute(
        """INSERT INTO tasks
           (id, project_id, title, status, priority, created_by, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        ("t1", "p1", "T", "todo", "medium", "u1", now, now),
    )
    conn.execute(
        """INSERT INTO experiments (id, project_id, name, status, tags,
           created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
        ("e1", "p1", "E", "planned", "[]", "u1", now, now),
    )
    conn.execute(
        "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?,?,?)",
        ("tok_owner", "u1", expires),
    )
    conn.execute(
        "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?,?,?)",
        ("tok_viewer", "u2", expires),
    )
    conn.commit()
    conn.close()

    tc = TestClient(app, raise_server_exceptions=True)
    return tc, db_path


def test_create_phase_201(auth_client):
    tc, _ = auth_client
    tc.headers.update({"Authorization": "Bearer tok_owner"})
    resp = tc.post("/api/v1/projects/p1/phases", json={
        "name": "Data Collection", "color": "#6366f1", "position": 0
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Data Collection"
    assert data["project_id"] == "p1"


def test_list_phases_200(auth_client):
    tc, _ = auth_client
    tc.headers.update({"Authorization": "Bearer tok_owner"})
    tc.post("/api/v1/projects/p1/phases", json={"name": "P1", "color": "#6366f1", "position": 0})
    tc.post("/api/v1/projects/p1/phases", json={"name": "P2", "color": "#ff0000", "position": 1})
    resp = tc.get("/api/v1/projects/p1/phases")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_phase_200(auth_client):
    tc, _ = auth_client
    tc.headers.update({"Authorization": "Bearer tok_owner"})
    r = tc.post("/api/v1/projects/p1/phases", json={"name": "Old", "color": "#6366f1", "position": 0})
    phase_id = r.json()["id"]
    resp = tc.patch(f"/api/v1/projects/p1/phases/{phase_id}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


def test_delete_phase_204(auth_client):
    tc, _ = auth_client
    tc.headers.update({"Authorization": "Bearer tok_owner"})
    r = tc.post("/api/v1/projects/p1/phases", json={"name": "P", "color": "#6366f1", "position": 0})
    phase_id = r.json()["id"]
    resp = tc.delete(f"/api/v1/projects/p1/phases/{phase_id}")
    assert resp.status_code == 204


def test_get_unknown_phase_returns_404(auth_client):
    tc, _ = auth_client
    tc.headers.update({"Authorization": "Bearer tok_owner"})
    resp = tc.patch("/api/v1/projects/p1/phases/nonexistent", json={"name": "X"})
    assert resp.status_code == 404


def test_viewer_cannot_create_phase(auth_client):
    tc, _ = auth_client
    tc.headers.update({"Authorization": "Bearer tok_viewer"})
    resp = tc.post("/api/v1/projects/p1/phases", json={"name": "P", "color": "#6366f1", "position": 0})
    assert resp.status_code == 403


def test_assign_task_phase(auth_client):
    tc, _ = auth_client
    tc.headers.update({"Authorization": "Bearer tok_owner"})
    r = tc.post("/api/v1/projects/p1/phases", json={"name": "P", "color": "#6366f1", "position": 0})
    phase_id = r.json()["id"]
    resp = tc.patch("/api/v1/projects/p1/tasks/t1/phase", json={"phase_id": phase_id})
    assert resp.status_code == 200


def test_assign_task_cross_project_phase_400(auth_client):
    tc, db_path = auth_client
    tc.headers.update({"Authorization": "Bearer tok_owner"})
    # Create a phase in a different project via direct DB insert
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO projects (id, name, created_by, created_at) VALUES (?,?,?,?)",
        ("p2", "Other", "u1", now),
    )
    conn.execute(
        """INSERT INTO project_phases (id, project_id, name, color, position, created_by, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        ("ph_other", "p2", "Cross", "#ff0000", 0, "u1", now),
    )
    conn.commit()
    conn.close()
    resp = tc.patch("/api/v1/projects/p1/tasks/t1/phase", json={"phase_id": "ph_other"})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/pm/test_phase_routes.py -v
```

Expected: FAIL (`No module named 'EvoScientist.pm.api.routes.phases'`)

- [ ] **Step 3: Add schemas to `schemas.py`**

Append to `EvoScientist/pm/api/schemas.py` (before the `# ── Errors` section):

```python
# ── Phases ────────────────────────────────────────────────────────────────────


class PhaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default='#6366f1', pattern=r'^#[0-9a-fA-F]{6}$')
    position: int = Field(default=0, ge=0)
    target_date: str | None = None


class PhaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    color: str | None = Field(default=None, pattern=r'^#[0-9a-fA-F]{6}$')
    position: int | None = Field(default=None, ge=0)
    target_date: str | None = None


class PhaseResponse(BaseModel):
    id: str
    project_id: str
    name: str
    color: str
    position: int
    target_date: str | None
    created_by: str
    created_at: str


class AssignPhaseRequest(BaseModel):
    phase_id: str | None = None


# ── Dependencies ──────────────────────────────────────────────────────────────


class DependencyCreate(BaseModel):
    depends_on_id: str
    dep_type: str = Field(default='hard', pattern='^(hard|soft)$')


class DependencyResponse(BaseModel):
    task_id: str
    depends_on_id: str
    dep_type: str
    created_by: str
    created_at: str


class DependenciesListResponse(BaseModel):
    dependencies: list[DependencyResponse]
    dependents: list[DependencyResponse]
```

- [ ] **Step 4: Create `api/routes/phases.py`**

Create `EvoScientist/pm/api/routes/phases.py`:

```python
"""Phase management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...crud.phases import (
    assign_experiment_phase,
    assign_task_phase,
    create_phase,
    delete_phase,
    get_phase,
    list_phases,
    update_phase,
)
from ...db import get_db_path
from ...models import User
from ..deps import require_project_role
from ..schemas import AssignPhaseRequest, PhaseCreate, PhaseResponse, PhaseUpdate

router = APIRouter()


def _phase_to_response(p) -> PhaseResponse:
    return PhaseResponse(
        id=p.id,
        project_id=p.project_id,
        name=p.name,
        color=p.color,
        position=p.position,
        target_date=p.target_date,
        created_by=p.created_by,
        created_at=p.created_at,
    )


@router.post(
    "/{project_id}/phases",
    response_model=PhaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a phase",
)
def create_project_phase(
    project_id: str,
    body: PhaseCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    phase = create_phase(
        get_db_path(),
        project_id=project_id,
        name=body.name,
        color=body.color,
        position=body.position,
        target_date=body.target_date,
        created_by=current_user.id,
    )
    return _phase_to_response(phase)


@router.get(
    "/{project_id}/phases",
    response_model=list[PhaseResponse],
    summary="List phases ordered by position",
)
def list_project_phases(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    return [_phase_to_response(p) for p in list_phases(get_db_path(), project_id)]


@router.patch(
    "/{project_id}/phases/{phase_id}",
    response_model=PhaseResponse,
    summary="Update phase name/color/position/target_date",
)
def update_project_phase(
    project_id: str,
    phase_id: str,
    body: PhaseUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    phase = get_phase(get_db_path(), phase_id)
    if not phase or phase.project_id != project_id:
        raise HTTPException(status_code=404, detail="Phase not found")
    updated = update_phase(get_db_path(), phase_id, **body.model_dump(exclude_unset=True))
    return _phase_to_response(updated)


@router.delete(
    "/{project_id}/phases/{phase_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete phase; tasks/experiments become unphased",
)
def delete_project_phase(
    project_id: str,
    phase_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    phase = get_phase(get_db_path(), phase_id)
    if not phase or phase.project_id != project_id:
        raise HTTPException(status_code=404, detail="Phase not found")
    delete_phase(get_db_path(), phase_id)


@router.patch(
    "/{project_id}/tasks/{task_id}/phase",
    summary="Assign or unassign a task to a phase",
)
def assign_task_to_phase(
    project_id: str,
    task_id: str,
    body: AssignPhaseRequest,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    if body.phase_id is not None:
        phase = get_phase(get_db_path(), body.phase_id)
        if not phase or phase.project_id != project_id:
            raise HTTPException(
                status_code=400, detail="Phase does not belong to this project"
            )
    assign_task_phase(get_db_path(), task_id, body.phase_id)
    return {"task_id": task_id, "phase_id": body.phase_id}


@router.patch(
    "/{project_id}/experiments/{exp_id}/phase",
    summary="Assign or unassign an experiment to a phase",
)
def assign_experiment_to_phase(
    project_id: str,
    exp_id: str,
    body: AssignPhaseRequest,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    if body.phase_id is not None:
        phase = get_phase(get_db_path(), body.phase_id)
        if not phase or phase.project_id != project_id:
            raise HTTPException(
                status_code=400, detail="Phase does not belong to this project"
            )
    assign_experiment_phase(get_db_path(), exp_id, body.phase_id)
    return {"experiment_id": exp_id, "phase_id": body.phase_id}
```

- [ ] **Step 5: Register phases router in `app.py`**

In `EvoScientist/pm/api/app.py`, update the imports line:

```python
from .routes import assists, auth, experiments, phases, projects, runs, tasks, users
```

And add after the existing `app.include_router(experiments.router, ...)` call:

```python
    app.include_router(phases.router, prefix="/api/v1/projects", tags=["phases"])
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
uv run pytest tests/pm/test_phase_routes.py -v
```

Expected: all PASS

- [ ] **Step 7: Run full suite**

```bash
uv run pytest tests/pm/ -v --timeout=30
```

Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add EvoScientist/pm/api/schemas.py EvoScientist/pm/api/routes/phases.py \
    EvoScientist/pm/api/app.py tests/pm/test_phase_routes.py
git commit -m "feat(pm): add phase API routes and schemas"
```

---

### Task 5: Dependency Routes + Modified Task Routes

**Files:**
- Create: `EvoScientist/pm/api/routes/dependencies.py`
- Modify: `EvoScientist/pm/api/schemas.py` (TaskResponse + blocked_by)
- Modify: `EvoScientist/pm/api/routes/tasks.py`
- Modify: `EvoScientist/pm/api/app.py`
- Create: `tests/pm/test_dependency_routes.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/pm/test_dependency_routes.py`:

```python
"""Tests for dependency API endpoints."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import pytest
from fastapi.testclient import TestClient

from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.db import create_schema


@pytest.fixture
def auth_client(tmp_path: Path):
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    import EvoScientist.pm.api.deps as deps_mod
    import EvoScientist.pm.api.routes.auth as auth_r
    import EvoScientist.pm.api.routes.dependencies as deps_r
    import EvoScientist.pm.api.routes.phases as phases_r
    import EvoScientist.pm.api.routes.projects as proj_r
    import EvoScientist.pm.api.routes.runs as runs_r
    import EvoScientist.pm.api.routes.tasks as tasks_r
    import EvoScientist.pm.api.routes.users as users_r
    import EvoScientist.pm.crud.dependencies as dep_crud
    import EvoScientist.pm.crud.phases as phases_crud
    import EvoScientist.pm.crud.projects as proj_crud
    import EvoScientist.pm.crud.tasks as tasks_crud
    import EvoScientist.pm.crud.users as users_crud

    for mod in [
        deps_mod, auth_r, deps_r, phases_r, proj_r, runs_r, tasks_r, users_r,
        dep_crud, phases_crud, proj_crud, tasks_crud, users_crud,
    ]:
        if hasattr(mod, "get_db_path"):
            mod.get_db_path = lambda: db_path

    app = create_app(db_path)

    now = datetime.now(timezone.utc).isoformat()
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    pw = bcrypt.hashpw(b"pass123", bcrypt.gensalt()).decode()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES (?,?,?,?,?)",
        ("u1", "alice", pw, 1, now),
    )
    conn.execute(
        "INSERT INTO projects (id, name, created_by, created_at) VALUES (?,?,?,?)",
        ("p1", "P", "u1", now),
    )
    conn.execute(
        "INSERT INTO project_members (project_id, user_id, role, added_at) VALUES (?,?,?,?)",
        ("p1", "u1", "owner", now),
    )
    for tid in ["t1", "t2", "t3"]:
        conn.execute(
            """INSERT INTO tasks
               (id, project_id, title, status, priority, created_by, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (tid, "p1", f"Task {tid}", "todo", "medium", "u1", now, now),
        )
    conn.execute(
        "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?,?,?)",
        ("tok1", "u1", expires),
    )
    conn.commit()
    conn.close()

    tc = TestClient(app, raise_server_exceptions=True)
    tc.headers.update({"Authorization": "Bearer tok1"})
    return tc, db_path


def test_add_dependency_201(auth_client):
    tc, _ = auth_client
    resp = tc.post(
        "/api/v1/projects/p1/tasks/t2/dependencies",
        json={"depends_on_id": "t1", "dep_type": "hard"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["task_id"] == "t2"
    assert data["depends_on_id"] == "t1"


def test_remove_dependency_204(auth_client):
    tc, _ = auth_client
    tc.post(
        "/api/v1/projects/p1/tasks/t2/dependencies",
        json={"depends_on_id": "t1"},
    )
    resp = tc.delete("/api/v1/projects/p1/tasks/t2/dependencies/t1")
    assert resp.status_code == 204


def test_list_dependencies_200(auth_client):
    tc, _ = auth_client
    tc.post("/api/v1/projects/p1/tasks/t2/dependencies", json={"depends_on_id": "t1"})
    tc.post("/api/v1/projects/p1/tasks/t3/dependencies", json={"depends_on_id": "t2"})
    resp = tc.get("/api/v1/projects/p1/tasks/t2/dependencies")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["dependencies"]) == 1  # t2 depends on t1
    assert len(body["dependents"]) == 1    # t3 depends on t2


def test_cycle_returns_409(auth_client):
    tc, _ = auth_client
    tc.post("/api/v1/projects/p1/tasks/t2/dependencies", json={"depends_on_id": "t1"})
    resp = tc.post(
        "/api/v1/projects/p1/tasks/t1/dependencies",
        json={"depends_on_id": "t2"},
    )
    assert resp.status_code == 409


def test_self_dep_returns_400(auth_client):
    tc, _ = auth_client
    resp = tc.post(
        "/api/v1/projects/p1/tasks/t1/dependencies",
        json={"depends_on_id": "t1"},
    )
    assert resp.status_code == 400


def test_task_detail_includes_blocked_by(auth_client):
    tc, _ = auth_client
    # t2 depends hard on t1 (t1 is todo, so it blocks t2)
    tc.post("/api/v1/projects/p1/tasks/t2/dependencies", json={"depends_on_id": "t1"})
    resp = tc.get("/api/v1/projects/p1/tasks/t2")
    assert resp.status_code == 200
    data = resp.json()
    assert "blocked_by" in data
    assert "t1" in data["blocked_by"]


def test_task_list_includes_blocked_by(auth_client):
    tc, _ = auth_client
    tc.post("/api/v1/projects/p1/tasks/t2/dependencies", json={"depends_on_id": "t1"})
    resp = tc.get("/api/v1/projects/p1/tasks")
    assert resp.status_code == 200
    tasks = {t["id"]: t for t in resp.json()}
    assert "t1" in tasks["t2"]["blocked_by"]
    assert tasks["t1"]["blocked_by"] == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/pm/test_dependency_routes.py -v
```

Expected: FAIL

- [ ] **Step 3: Update `TaskResponse` in `schemas.py`**

Find `class TaskResponse(BaseModel):` in `EvoScientist/pm/api/schemas.py` and add two fields:

```python
class TaskResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: str | None
    assignee_id: str | None
    status: str
    priority: str
    deadline: str | None
    session_id: str | None
    phase_id: str | None
    blocked_by: list[str]
    created_by: str
    created_at: str
    updated_at: str
```

- [ ] **Step 4: Create `api/routes/dependencies.py`**

Create `EvoScientist/pm/api/routes/dependencies.py`:

```python
"""Task dependency endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...crud.dependencies import (
    add_dependency,
    list_dependencies,
    list_dependents,
    remove_dependency,
)
from ...crud.tasks import get_task
from ...db import get_db_path
from ...models import User
from ..deps import require_project_role
from ..schemas import DependenciesListResponse, DependencyCreate, DependencyResponse

router = APIRouter()


def _dep_to_response(d) -> DependencyResponse:
    return DependencyResponse(
        task_id=d.task_id,
        depends_on_id=d.depends_on_id,
        dep_type=d.dep_type,
        created_by=d.created_by,
        created_at=d.created_at,
    )


@router.post(
    "/{project_id}/tasks/{task_id}/dependencies",
    response_model=DependencyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add dependency; 409 on cycle, 400 on self/cross-project",
)
def add_task_dependency(
    project_id: str,
    task_id: str,
    body: DependencyCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        dep = add_dependency(
            get_db_path(),
            task_id=task_id,
            depends_on_id=body.depends_on_id,
            dep_type=body.dep_type,
            created_by=current_user.id,
        )
    except ValueError as exc:
        msg = str(exc)
        if "cycle" in msg:
            raise HTTPException(status_code=409, detail="cycle detected")
        raise HTTPException(status_code=400, detail=msg)
    return _dep_to_response(dep)


@router.delete(
    "/{project_id}/tasks/{task_id}/dependencies/{dep_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove dependency",
)
def remove_task_dependency(
    project_id: str,
    task_id: str,
    dep_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    remove_dependency(get_db_path(), task_id=task_id, depends_on_id=dep_id)


@router.get(
    "/{project_id}/tasks/{task_id}/dependencies",
    response_model=DependenciesListResponse,
    summary="List deps + dependents for a task",
)
def list_task_dependencies(
    project_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    deps = list_dependencies(get_db_path(), task_id)
    dependents = list_dependents(get_db_path(), task_id)
    return DependenciesListResponse(
        dependencies=[_dep_to_response(d) for d in deps],
        dependents=[_dep_to_response(d) for d in dependents],
    )
```

- [ ] **Step 5: Update `api/routes/tasks.py`** to include `phase_id` and `blocked_by`

Add import at the top of `EvoScientist/pm/api/routes/tasks.py`:

```python
from ...crud.dependencies import get_blocked_by
```

Replace `_task_to_response` with:

```python
def _task_to_response(t, db_path=None) -> TaskResponse:
    from ...db import get_db_path as _get_db_path
    _db = db_path or _get_db_path()
    return TaskResponse(
        id=t.id,
        project_id=t.project_id,
        title=t.title,
        description=t.description,
        assignee_id=t.assignee_id,
        status=t.status,
        priority=t.priority,
        deadline=t.deadline,
        session_id=t.session_id,
        phase_id=t.phase_id,
        blocked_by=get_blocked_by(_db, t.id),
        created_by=t.created_by,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )
```

- [ ] **Step 6: Register dependencies router in `app.py`**

In `EvoScientist/pm/api/app.py`, update the import:

```python
from .routes import assists, auth, dependencies, experiments, phases, projects, runs, tasks, users
```

Add after the phases router registration:

```python
    app.include_router(dependencies.router, prefix="/api/v1/projects", tags=["dependencies"])
```

- [ ] **Step 7: Run tests to confirm they pass**

```bash
uv run pytest tests/pm/test_dependency_routes.py tests/pm/test_phase_routes.py -v
```

Expected: all PASS

- [ ] **Step 8: Run full suite**

```bash
uv run pytest tests/pm/ -v --timeout=30
```

Expected: all PASS

- [ ] **Step 9: Commit**

```bash
git add EvoScientist/pm/api/routes/dependencies.py EvoScientist/pm/api/routes/tasks.py \
    EvoScientist/pm/api/schemas.py EvoScientist/pm/api/app.py \
    tests/pm/test_dependency_routes.py
git commit -m "feat(pm): add dependency routes + phase_id/blocked_by in task responses"
```

---

### Task 6: Frontend `api.ts` — Types + API Methods

**Files:**
- Modify: `EvoScientist/pm/frontend/src/api.ts`

- [ ] **Step 1: Update `Task` interface and add new interfaces**

In `EvoScientist/pm/frontend/src/api.ts`, update the `Task` interface:

```typescript
export interface Task {
  id: string; project_id: string; title: string; description: string | null
  assignee_id: string | null; status: 'todo' | 'in_progress' | 'done'
  priority: 'high' | 'medium' | 'low'; deadline: string | null
  session_id: string | null; phase_id: string | null; blocked_by: string[]
  created_by: string; created_at: string; updated_at: string
}
```

Add new interfaces after the `Assist` interface:

```typescript
export interface ProjectPhase {
  id: string
  project_id: string
  name: string
  color: string
  position: number
  target_date: string | null
  created_by: string
  created_at: string
}

export interface TaskDependency {
  task_id: string
  depends_on_id: string
  dep_type: 'hard' | 'soft'
  created_by: string
  created_at: string
}

export interface DependenciesListResponse {
  dependencies: TaskDependency[]
  dependents: TaskDependency[]
}
```

- [ ] **Step 2: Add API methods to the `api` object**

Inside the `api` object in `api.ts`, add after the `assistStreamUrl` method:

```typescript
  // ── Phases ───────────────────────────────────────────────────────────────
  listPhases: (projectId: string) =>
    request<ProjectPhase[]>('GET', `/projects/${projectId}/phases`),
  createPhase: (projectId: string, data: { name: string; color?: string; position?: number; target_date?: string | null }) =>
    request<ProjectPhase>('POST', `/projects/${projectId}/phases`, data),
  updatePhase: (projectId: string, phaseId: string, data: { name?: string; color?: string; position?: number; target_date?: string | null }) =>
    request<ProjectPhase>('PATCH', `/projects/${projectId}/phases/${phaseId}`, data),
  deletePhase: (projectId: string, phaseId: string) =>
    request<void>('DELETE', `/projects/${projectId}/phases/${phaseId}`),
  assignTaskPhase: (projectId: string, taskId: string, phaseId: string | null) =>
    request<{ task_id: string; phase_id: string | null }>('PATCH', `/projects/${projectId}/tasks/${taskId}/phase`, { phase_id: phaseId }),
  assignExperimentPhase: (projectId: string, expId: string, phaseId: string | null) =>
    request<{ experiment_id: string; phase_id: string | null }>('PATCH', `/projects/${projectId}/experiments/${expId}/phase`, { phase_id: phaseId }),
  // ── Dependencies ─────────────────────────────────────────────────────────
  addDependency: (projectId: string, taskId: string, data: { depends_on_id: string; dep_type?: 'hard' | 'soft' }) =>
    request<TaskDependency>('POST', `/projects/${projectId}/tasks/${taskId}/dependencies`, data),
  removeDependency: (projectId: string, taskId: string, depId: string) =>
    request<void>('DELETE', `/projects/${projectId}/tasks/${taskId}/dependencies/${depId}`),
  listDependencies: (projectId: string, taskId: string) =>
    request<DependenciesListResponse>('GET', `/projects/${projectId}/tasks/${taskId}/dependencies`),
```

- [ ] **Step 3: Build the frontend to check for TypeScript errors**

```bash
cd EvoScientist/pm/frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds with no TS errors

- [ ] **Step 4: Commit**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
git add EvoScientist/pm/frontend/src/api.ts
git commit -m "feat(pm): add phase + dependency types and API methods to frontend"
```

---

### Task 7: PhaseManager Component

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/PhaseManager.tsx`
- Modify: `EvoScientist/pm/frontend/src/components/ProjectSettingsPanel.tsx`

- [ ] **Step 1: Create `PhaseManager.tsx`**

Create `EvoScientist/pm/frontend/src/components/PhaseManager.tsx`:

```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, ProjectPhase } from '../api'

interface Props {
  projectId: string
  isOwnerOrEditor: boolean
}

const PRESET_COLORS = [
  '#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6',
  '#ef4444', '#14b8a6', '#f97316', '#64748b',
]

export function PhaseManager({ projectId, isOwnerOrEditor }: Props) {
  const qc = useQueryClient()
  const [addingName, setAddingName] = useState('')
  const [addingColor, setAddingColor] = useState('#6366f1')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')
  const [editColor, setEditColor] = useState('#6366f1')
  const [editDate, setEditDate] = useState('')

  const { data: phases = [] } = useQuery({
    queryKey: ['phases', projectId],
    queryFn: () => api.listPhases(projectId),
  })

  const createMutation = useMutation({
    mutationFn: () => api.createPhase(projectId, {
      name: addingName.trim(),
      color: addingColor,
      position: phases.length,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['phases', projectId] })
      setAddingName('')
      setAddingColor('#6366f1')
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<ProjectPhase> }) =>
      api.updatePhase(projectId, id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['phases', projectId] })
      setEditingId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (phaseId: string) => api.deletePhase(projectId, phaseId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['phases', projectId] })
      qc.invalidateQueries({ queryKey: ['tasks', projectId] })
    },
  })

  const startEdit = (p: ProjectPhase) => {
    setEditingId(p.id)
    setEditName(p.name)
    setEditColor(p.color)
    setEditDate(p.target_date ?? '')
  }

  const saveEdit = (id: string) => {
    updateMutation.mutate({
      id,
      data: { name: editName, color: editColor, target_date: editDate || null },
    })
  }

  const rowStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '8px 0',
    borderBottom: '1px solid var(--border-subtle)',
  }

  const inputStyle: React.CSSProperties = {
    background: 'var(--surface-input)',
    border: '1px solid var(--border)',
    borderRadius: 4,
    color: 'var(--text)',
    padding: '4px 8px',
    fontSize: 18,
    outline: 'none',
    fontFamily: 'inherit',
  }

  const btnStyle = (color: string): React.CSSProperties => ({
    padding: '3px 10px',
    borderRadius: 4,
    border: `1px solid ${color}`,
    color,
    background: 'transparent',
    cursor: 'pointer',
    fontSize: 16,
    fontFamily: 'var(--font-mono)',
  })

  return (
    <div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.1em', marginBottom: 10, fontFamily: 'var(--font-mono)' }}>
        PHASES
      </div>

      {phases.map(phase => (
        <div key={phase.id} style={rowStyle}>
          <div style={{ width: 14, height: 14, borderRadius: 3, background: phase.color, flexShrink: 0 }} />

          {editingId === phase.id ? (
            <>
              <input
                value={editName}
                onChange={e => setEditName(e.target.value)}
                style={{ ...inputStyle, flex: 1 }}
              />
              <input
                type="color"
                value={editColor}
                onChange={e => setEditColor(e.target.value)}
                style={{ width: 28, height: 28, border: 'none', padding: 0, cursor: 'pointer', background: 'transparent' }}
              />
              <input
                type="date"
                value={editDate}
                onChange={e => setEditDate(e.target.value)}
                style={{ ...inputStyle, width: 130 }}
                placeholder="Target date"
              />
              <button style={btnStyle('#10b981')} onClick={() => saveEdit(phase.id)}>✓</button>
              <button style={btnStyle('#64748b')} onClick={() => setEditingId(null)}>✕</button>
            </>
          ) : (
            <>
              <span style={{ flex: 1, fontSize: 19, color: 'var(--text)' }}>{phase.name}</span>
              {phase.target_date && (
                <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                  {phase.target_date}
                </span>
              )}
              {isOwnerOrEditor && (
                <>
                  <button style={btnStyle('#64748b')} onClick={() => startEdit(phase)}>edit</button>
                  <button style={btnStyle('#f43f5e')} onClick={() => deleteMutation.mutate(phase.id)}>✕</button>
                </>
              )}
            </>
          )}
        </div>
      ))}

      {isOwnerOrEditor && (
        <div style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 4, flexShrink: 0 }}>
            {PRESET_COLORS.map(c => (
              <div
                key={c}
                onClick={() => setAddingColor(c)}
                style={{
                  width: 14, height: 14, borderRadius: 3, background: c, cursor: 'pointer',
                  outline: addingColor === c ? `2px solid white` : 'none',
                  outlineOffset: 1,
                }}
              />
            ))}
          </div>
          <input
            value={addingName}
            onChange={e => setAddingName(e.target.value)}
            placeholder="New phase name…"
            style={{ ...inputStyle, flex: 1 }}
            onKeyDown={e => e.key === 'Enter' && addingName.trim() && createMutation.mutate()}
          />
          <button
            style={btnStyle('#6366f1')}
            onClick={() => createMutation.mutate()}
            disabled={!addingName.trim()}
          >
            + Add
          </button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Integrate PhaseManager into `ProjectSettingsPanel.tsx`**

Add import at the top of `ProjectSettingsPanel.tsx`:

```typescript
import { PhaseManager } from './PhaseManager'
```

Find the member section in the JSX and add the PhaseManager section before or after the members list. Locate the section that shows members (look for `Members` heading or similar) and add:

```tsx
{/* ── Phases ── */}
<div style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid var(--border-subtle)' }}>
  <PhaseManager
    projectId={projectId}
    isOwnerOrEditor={project.members.some(
      m => m.username === username && (m.role === 'owner' || m.role === 'editor')
    )}
  />
</div>
```

- [ ] **Step 3: Build to check for TypeScript errors**

```bash
cd EvoScientist/pm/frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds

- [ ] **Step 4: Commit**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
git add EvoScientist/pm/frontend/src/components/PhaseManager.tsx \
    EvoScientist/pm/frontend/src/components/ProjectSettingsPanel.tsx
git commit -m "feat(pm): add PhaseManager component in project settings"
```

---

### Task 8: DependencyPicker Component

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/DependencyPicker.tsx`
- Modify: `EvoScientist/pm/frontend/src/pages/TaskDetail.tsx`

- [ ] **Step 1: Create `DependencyPicker.tsx`**

Create `EvoScientist/pm/frontend/src/components/DependencyPicker.tsx`:

```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task, TaskDependency } from '../api'

interface Props {
  taskId: string
  projectId: string
  isOwnerOrEditor: boolean
}

export function DependencyPicker({ taskId, projectId, isOwnerOrEditor }: Props) {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [depType, setDepType] = useState<'hard' | 'soft'>('hard')
  const [cycleError, setCycleError] = useState<string | null>(null)

  const { data: depsData } = useQuery({
    queryKey: ['dependencies', projectId, taskId],
    queryFn: () => api.listDependencies(projectId, taskId),
  })

  const { data: allTasks = [] } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.listTasks(projectId),
    enabled: open,
  })

  const addMutation = useMutation({
    mutationFn: (depOnId: string) =>
      api.addDependency(projectId, taskId, { depends_on_id: depOnId, dep_type: depType }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dependencies', projectId, taskId] })
      qc.invalidateQueries({ queryKey: ['tasks', projectId] })
      setCycleError(null)
      setSearch('')
    },
    onError: (err: Error) => {
      setCycleError(err.message)
    },
  })

  const removeMutation = useMutation({
    mutationFn: (depOnId: string) => api.removeDependency(projectId, taskId, depOnId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['dependencies', projectId, taskId] })
      qc.invalidateQueries({ queryKey: ['tasks', projectId] })
    },
  })

  const deps = depsData?.dependencies ?? []
  const dependents = depsData?.dependents ?? []

  const existingDepIds = new Set([
    ...deps.map(d => d.depends_on_id),
    taskId,
  ])

  const searchResults = open && search.trim()
    ? allTasks.filter(
        t => !existingDepIds.has(t.id) &&
          t.title.toLowerCase().includes(search.toLowerCase())
      ).slice(0, 6)
    : []

  const sectionLabel: React.CSSProperties = {
    fontSize: 14,
    fontWeight: 700,
    color: 'var(--text-dim)',
    letterSpacing: '0.1em',
    fontFamily: 'var(--font-mono)',
    marginBottom: 6,
    marginTop: 12,
  }

  const chipStyle = (isBlocked: boolean): React.CSSProperties => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    padding: '3px 8px',
    borderRadius: 4,
    border: `1px solid ${isBlocked ? '#f43f5e' : 'var(--border)'}`,
    color: isBlocked ? '#f43f5e' : 'var(--text)',
    background: isBlocked ? 'rgba(244,63,94,0.07)' : 'var(--surface-card)',
    fontSize: 17,
    marginBottom: 4,
    marginRight: 4,
  })

  const inputStyle: React.CSSProperties = {
    background: 'var(--surface-input)',
    border: '1px solid var(--border)',
    borderRadius: 4,
    color: 'var(--text)',
    padding: '5px 9px',
    fontSize: 17,
    outline: 'none',
    width: '100%',
    boxSizing: 'border-box' as const,
    fontFamily: 'inherit',
  }

  const taskTitle = (id: string) => allTasks.find(t => t.id === id)?.title ?? id

  return (
    <div>
      <div
        style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}
        onClick={() => setOpen(v => !v)}
      >
        <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.1em', fontFamily: 'var(--font-mono)' }}>
          DEPENDENCIES
        </span>
        <span style={{ fontSize: 14, color: 'var(--text-dim)' }}>{open ? '▴' : '▾'}</span>
        {deps.length > 0 && (
          <span style={{ fontSize: 14, color: '#f59e0b', fontFamily: 'var(--font-mono)' }}>
            {deps.length} dep{deps.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {open && (
        <div style={{ paddingLeft: 4 }}>
          {/* Waiting on */}
          <div style={sectionLabel}>WAITING ON</div>
          {deps.length === 0 ? (
            <div style={{ fontSize: 17, color: 'var(--text-dim)', marginBottom: 8 }}>none</div>
          ) : (
            <div style={{ marginBottom: 8 }}>
              {deps.map(d => {
                const isBlocked = d.dep_type === 'hard'
                return (
                  <span key={d.depends_on_id} style={chipStyle(isBlocked)}>
                    {d.dep_type === 'hard' ? '🔒' : '↗'} {taskTitle(d.depends_on_id)}
                    {isOwnerOrEditor && (
                      <span
                        onClick={() => removeMutation.mutate(d.depends_on_id)}
                        style={{ cursor: 'pointer', opacity: 0.6, marginLeft: 2 }}
                      >
                        ✕
                      </span>
                    )}
                  </span>
                )
              })}
            </div>
          )}

          {/* Blocking */}
          <div style={sectionLabel}>BLOCKING</div>
          {dependents.length === 0 ? (
            <div style={{ fontSize: 17, color: 'var(--text-dim)', marginBottom: 8 }}>none</div>
          ) : (
            <div style={{ marginBottom: 8 }}>
              {dependents.map(d => (
                <span key={d.task_id} style={chipStyle(false)}>
                  {taskTitle(d.task_id)}
                </span>
              ))}
            </div>
          )}

          {/* Add dependency */}
          {isOwnerOrEditor && (
            <div style={{ marginTop: 10 }}>
              <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
                <select
                  value={depType}
                  onChange={e => setDepType(e.target.value as 'hard' | 'soft')}
                  style={{ ...inputStyle, width: 90 }}
                >
                  <option value="hard">hard</option>
                  <option value="soft">soft</option>
                </select>
                <input
                  value={search}
                  onChange={e => { setSearch(e.target.value); setCycleError(null) }}
                  placeholder="Search tasks to add…"
                  style={inputStyle}
                />
              </div>
              {cycleError && (
                <div style={{ fontSize: 15, color: '#f43f5e', marginBottom: 6 }}>
                  ⚠ {cycleError}
                </div>
              )}
              {searchResults.map(t => (
                <div
                  key={t.id}
                  onClick={() => addMutation.mutate(t.id)}
                  style={{
                    padding: '5px 9px',
                    cursor: 'pointer',
                    borderRadius: 4,
                    background: 'var(--surface-card)',
                    border: '1px solid var(--border-subtle)',
                    fontSize: 17,
                    marginBottom: 3,
                    color: 'var(--text)',
                  }}
                >
                  {t.title}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Add DependencyPicker to `TaskDetail.tsx`**

Add import at the top of `TaskDetail.tsx`:

```typescript
import { DependencyPicker } from '../components/DependencyPicker'
```

Find where the task's `description` or details section ends in the JSX (look for where comments or AI tab section starts) and add the DependencyPicker. It should render in the `details` tab only. Find the end of the details section (before the comments area or AI tab check) and add:

```tsx
{/* ── Dependencies ── */}
<div style={{ marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--border-subtle)' }}>
  <DependencyPicker
    taskId={task.id}
    projectId={projectId}
    isOwnerOrEditor={members.some(
      m => m.user_id === task.created_by || m.role === 'owner' || m.role === 'editor'
    )}
  />
</div>
```

Also add the blocked status badge near the status selector. Find where `editStatus` is used in the status dropdown and add a warning before it if `task.blocked_by.length > 0`:

```tsx
{task.blocked_by.length > 0 && (
  <div style={{
    marginBottom: 8,
    padding: '6px 10px',
    borderRadius: 5,
    background: 'rgba(244,63,94,0.08)',
    border: '1px solid rgba(244,63,94,0.3)',
    fontSize: 16,
    color: '#f43f5e',
    fontFamily: 'var(--font-mono)',
  }}>
    🔒 Blocked by {task.blocked_by.length} task{task.blocked_by.length !== 1 ? 's' : ''}
  </div>
)}
```

- [ ] **Step 3: Build to check for TypeScript errors**

```bash
cd EvoScientist/pm/frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds

- [ ] **Step 4: Commit**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
git add EvoScientist/pm/frontend/src/components/DependencyPicker.tsx \
    EvoScientist/pm/frontend/src/pages/TaskDetail.tsx
git commit -m "feat(pm): add DependencyPicker component and integrate into TaskDetail"
```

---

### Task 9: Board.tsx Phase Swimlanes

**Files:**
- Modify: `EvoScientist/pm/frontend/src/pages/Board.tsx`

The Board currently renders three `DroppableColumn` components side-by-side. The new layout wraps them in phase-grouped swimlanes. Each swimlane shows its own three columns with only the tasks/experiments in that phase.

- [ ] **Step 1: Add phase data fetching and swimlane components**

At the top of `Board.tsx`, add the import:

```typescript
import { api, Task, Experiment, ProjectPhase } from '../api'
```

After the existing `useQuery` calls for tasks and experiments, add:

```typescript
  const { data: phases = [] } = useQuery({
    queryKey: ['phases', projectId],
    queryFn: () => api.listPhases(projectId!),
    enabled: Boolean(projectId),
  })
```

- [ ] **Step 2: Add phase swimlane header component**

Add this component definition before the main Board function (after the existing helper components):

```tsx
interface PhaseSwimLaneProps {
  phase: ProjectPhase | null  // null = "Unphased"
  phaseTasks: Task[]
  phaseExps: Experiment[]
  // all the props DroppableColumn needs
  activeTaskId: string | null
  addingToCol: Task['status'] | null
  newTaskTitle: string
  onNewTaskTitleChange: (v: string) => void
  onAddStart: (status: Task['status']) => void
  onAddCancel: () => void
  onAddSubmit: (title: string) => void
  onCardClick: (task: Task) => void
  onEditClick: (task: Task, rect: DOMRect) => void
  onExpClick: (exp: Experiment) => void
  members: { user_id: string; username: string }[]
}

function PhaseSwimLane({
  phase, phaseTasks, phaseExps, activeTaskId,
  addingToCol, newTaskTitle, onNewTaskTitleChange,
  onAddStart, onAddCancel, onAddSubmit,
  onCardClick, onEditClick, onExpClick, members,
}: PhaseSwimLaneProps) {
  const done = phaseTasks.filter(t => t.status === 'done').length
  const total = phaseTasks.length
  const progress = total > 0 ? done / total : 0

  const headerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 14px',
    borderLeft: `4px solid ${phase?.color ?? '#64748b'}`,
    background: 'var(--surface-2)',
    borderBottom: '1px solid var(--border-subtle)',
    marginBottom: 0,
    borderRadius: '6px 6px 0 0',
    marginTop: 16,
  }

  return (
    <div>
      {/* Swimlane header */}
      <div style={headerStyle}>
        <span style={{
          fontWeight: 700,
          fontSize: 17,
          fontFamily: 'var(--font-mono)',
          color: phase?.color ?? 'var(--text-dim)',
          letterSpacing: '0.08em',
        }}>
          {phase?.name ?? 'UNPHASED'}
        </span>

        {/* Progress bar */}
        <div style={{ flex: 1, height: 6, background: 'var(--border-subtle)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            width: `${progress * 100}%`,
            height: '100%',
            background: phase?.color ?? '#64748b',
            borderRadius: 3,
            transition: 'width 0.3s',
          }} />
        </div>

        <span style={{ fontSize: 15, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}>
          {done}/{total}
        </span>

        {phase?.target_date && (
          <span style={{
            fontSize: 14,
            color: 'var(--text-dim)',
            background: 'var(--surface-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 4,
            padding: '1px 6px',
            fontFamily: 'var(--font-mono)',
          }}>
            due {phase.target_date}
          </span>
        )}
      </div>

      {/* Columns for this swimlane */}
      <div style={{ display: 'flex', gap: 12, padding: '12px 0' }}>
        {COLUMNS.map(col => {
          const colTasks = phaseTasks.filter(t => t.status === col.key)
          const colExps = phaseExps.filter(e => EXP_STATUS_TO_COL[e.status] === col.key)
          return (
            <DroppableColumn
              key={col.key}
              col={col}
              colTasks={colTasks}
              colExps={colExps}
              isDropTarget={false}
              activeTaskId={activeTaskId}
              addingToCol={addingToCol}
              newTaskTitle={newTaskTitle}
              onNewTaskTitleChange={onNewTaskTitleChange}
              onAddStart={onAddStart}
              onAddCancel={onAddCancel}
              onAddSubmit={onAddSubmit}
              onCardClick={onCardClick}
              onEditClick={onEditClick}
              onExpClick={onExpClick}
              members={members}
            />
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Update `DraggableCard` to show blocked badge**

In the `DraggableCard` component, add the 🔒 badge. Find the section that renders the card title (look for `task.title`) and add before or after it:

```tsx
{/* Blocked badge */}
{task.blocked_by.length > 0 && (
  <span style={{
    fontSize: 14,
    marginLeft: 4,
    color: '#f43f5e',
    title: `Blocked by ${task.blocked_by.length} task(s)`,
  }}>
    🔒
  </span>
)}
```

Also dim the card when blocked by adding to `cardStyle`:

```typescript
  const cardStyle: React.CSSProperties = {
    ...
    opacity: isDragging ? 0.35 : (task.blocked_by.length > 0 ? 0.75 : 1),
    ...
  }
```

- [ ] **Step 4: Replace the column rendering in the main Board JSX with swimlane rendering**

Find the section in the main Board function where `DroppableColumn` is rendered for each column (the `.map(col => <DroppableColumn ...>)` block). Replace the outer container with swimlane grouping:

```tsx
{/* ── Swimlanes ── */}
<div style={{ overflowY: 'auto', flex: 1, padding: '0 20px 20px' }}>
  {/* Phase swimlanes */}
  {phases.map(phase => {
    const phaseTasks = filteredTasks.filter(t => t.phase_id === phase.id)
    const phaseExps = filteredExps.filter(e => (e as any).phase_id === phase.id)
    return (
      <PhaseSwimLane
        key={phase.id}
        phase={phase}
        phaseTasks={phaseTasks}
        phaseExps={phaseExps}
        activeTaskId={activeTaskId}
        addingToCol={addingToCol}
        newTaskTitle={newTaskTitle}
        onNewTaskTitleChange={setNewTaskTitle}
        onAddStart={setAddingToCol}
        onAddCancel={() => setAddingToCol(null)}
        onAddSubmit={handleAddTask}
        onCardClick={t => setSelectedTask(t)}
        onEditClick={(t, rect) => openEditPopover(t, rect)}
        onExpClick={e => setSelectedExp(e)}
        members={project?.members ?? []}
      />
    )
  })}

  {/* Unphased section */}
  {(() => {
    const unphased = filteredTasks.filter(t => !t.phase_id)
    const unphasedExps = filteredExps.filter(e => !(e as any).phase_id)
    return (
      <PhaseSwimLane
        phase={null}
        phaseTasks={unphased}
        phaseExps={unphasedExps}
        activeTaskId={activeTaskId}
        addingToCol={addingToCol}
        newTaskTitle={newTaskTitle}
        onNewTaskTitleChange={setNewTaskTitle}
        onAddStart={setAddingToCol}
        onAddCancel={() => setAddingToCol(null)}
        onAddSubmit={handleAddTask}
        onCardClick={t => setSelectedTask(t)}
        onEditClick={(t, rect) => openEditPopover(t, rect)}
        onExpClick={e => setSelectedExp(e)}
        members={project?.members ?? []}
      />
    )
  })()}
</div>
```

**Note:** Variable names like `filteredTasks`, `filteredExps`, `selectedTask`, `handleAddTask`, `openEditPopover` should match the existing names in Board.tsx. Read the current Board.tsx variable names before making these edits and substitute accordingly.

- [ ] **Step 5: Build to check for TypeScript errors**

```bash
cd EvoScientist/pm/frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds

- [ ] **Step 6: Commit**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
git add EvoScientist/pm/frontend/src/pages/Board.tsx
git commit -m "feat(pm): add phase swimlanes and blocked badges to Board"
```

---

### Task 10: ExperimentsPage Phase Filter

**Files:**
- Modify: `EvoScientist/pm/frontend/src/pages/ExperimentsPage.tsx`

- [ ] **Step 1: Add phase filter state and fetch phases**

In `ExperimentsPage.tsx`, add phase state and query after the existing queries:

```typescript
  const [phaseFilter, setPhaseFilter] = useState<string | null>(null)

  const { data: phases = [] } = useQuery({
    queryKey: ['phases', projectId],
    queryFn: () => api.listPhases(projectId!),
    enabled: Boolean(projectId),
  })
```

- [ ] **Step 2: Filter experiments by phase**

Update the experiments rendering to filter by `phaseFilter`. Find where experiments are rendered (likely `experiments.map(...)`) and add filtering:

```typescript
  const displayedExperiments = phaseFilter
    ? experiments.filter(e => (e as any).phase_id === phaseFilter)
    : experiments
```

Then replace `experiments.map(...)` with `displayedExperiments.map(...)`.

- [ ] **Step 3: Add phase filter chips to the UI**

Find the toolbar/header area in ExperimentsPage and add phase filter chips:

```tsx
{/* Phase filter chips */}
{phases.length > 0 && (
  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
    <button
      onClick={() => setPhaseFilter(null)}
      style={{
        padding: '3px 10px',
        borderRadius: 12,
        border: `1px solid ${!phaseFilter ? '#6366f1' : 'var(--border-subtle)'}`,
        background: !phaseFilter ? 'rgba(99,102,241,0.12)' : 'transparent',
        color: !phaseFilter ? '#6366f1' : 'var(--text-dim)',
        cursor: 'pointer',
        fontSize: 15,
        fontFamily: 'var(--font-mono)',
      }}
    >
      ALL
    </button>
    {phases.map(phase => (
      <button
        key={phase.id}
        onClick={() => setPhaseFilter(phaseFilter === phase.id ? null : phase.id)}
        style={{
          padding: '3px 10px',
          borderRadius: 12,
          border: `1px solid ${phaseFilter === phase.id ? phase.color : 'var(--border-subtle)'}`,
          background: phaseFilter === phase.id ? `${phase.color}1a` : 'transparent',
          color: phaseFilter === phase.id ? phase.color : 'var(--text-dim)',
          cursor: 'pointer',
          fontSize: 15,
          fontFamily: 'var(--font-mono)',
          display: 'flex',
          alignItems: 'center',
          gap: 5,
        }}
      >
        <span style={{ width: 8, height: 8, borderRadius: '50%', background: phase.color, display: 'inline-block' }} />
        {phase.name}
      </button>
    ))}
  </div>
)}
```

- [ ] **Step 4: Build to check for TypeScript errors**

```bash
cd EvoScientist/pm/frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds

- [ ] **Step 5: Run full test suite**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
uv run pytest tests/pm/ -v --timeout=30
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add EvoScientist/pm/frontend/src/pages/ExperimentsPage.tsx
git commit -m "feat(pm): add phase filter chips to ExperimentsPage"
```

---

## Self-Review

**Spec coverage check:**
- ✅ `project_phases` table with all specified columns (Task 1)
- ✅ `task_dependencies` table with PRIMARY KEY (task_id, depends_on_id) and CASCADE (Task 1)
- ✅ `phase_id` FK on tasks + experiments with SET NULL (Task 1)
- ✅ All 7 phase CRUD functions (Task 2)
- ✅ All 5 dependency CRUD functions + `_has_cycle` (Task 3)
- ✅ Pydantic schemas: PhaseCreate, PhaseResponse, PhaseUpdate, AssignPhaseRequest, DependencyCreate, DependencyResponse, DependenciesListResponse (Task 4)
- ✅ 6 phase endpoints (Task 4)
- ✅ 3 dependency endpoints (Task 5)
- ✅ `phase_id` + `blocked_by` in task responses (Task 5)
- ✅ Self-dep → 400, cross-project → 400, cycle → 409 (Task 5)
- ✅ Frontend new types + API methods (Task 6)
- ✅ PhaseManager in ProjectSettingsPanel (Task 7)
- ✅ DependencyPicker in TaskDetail with blocked badge (Task 8)
- ✅ Board swimlanes with progress bars and 🔒 badges (Task 9)
- ✅ ExperimentsPage phase filter (Task 10)

**Gaps / notes:**
- Board Task 9 uses `(e as any).phase_id` because the `Experiment` interface in `api.ts` doesn't include `phase_id`. The backend returns it after the migration. Either update the `Experiment` interface in `api.ts` to include `phase_id: string | null` (recommended), or keep the cast. Add this fix to Task 6 if you want type safety.
- Board drag-between-swimlanes (calling `assignTaskPhase`) is noted in the spec but not fully wired in Task 9 — the swimlane `DroppableColumn` components currently only change status. Phase reassignment is accessible via TaskDetail. If drag-to-reassign-phase is required, extend the `DragEndEvent` handler to detect cross-phase drops using the droppable ID scheme `${phase_id}__${col_key}`.
- `update_phase` with `**kwargs` uses f-string SQL construction from whitelisted keys only — no injection risk since `allowed = {"name", "color", "position", "target_date"}` guards the set.
