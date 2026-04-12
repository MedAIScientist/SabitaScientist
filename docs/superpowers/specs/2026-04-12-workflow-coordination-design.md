# Design: Workflow Coordination — Phases & Task Dependencies

**Date:** 2026-04-12
**Branch target:** `feature/workflow-coordination`
**Status:** Approved

---

## Overview

Add project-level phases (named swimlane groups with a target date) and task dependency tracking (hard blocks + soft links with cycle detection) to the PM system. The Board view renders tasks as swimlane rows grouped by phase. Task detail shows dependencies inline with hard-block enforcement in the frontend.

---

## Goals

- Let owners/editors define named phases (e.g., "Data Collection", "Training", "Evaluation") and assign tasks and experiments to them
- Show the Board as phase swimlanes with per-phase progress bars
- Let users declare that Task B depends on Task A (hard block or soft link)
- Show a 🔒 badge on blocked task cards and disable status progression in the frontend when hard blockers are incomplete
- Prevent circular dependency graphs at the API layer (BFS cycle detection on add)

## Non-Goals

- Backend enforcement of hard block status transitions (frontend-only)
- Gantt chart / timeline view (separate feature)
- Phase templates (deferred)
- Dependencies between experiments (tasks only)

---

## Architecture

Two independent subsystems sharing no logic:

```
Phases subsystem
  crud/phases.py  →  api/routes/phases.py
  DB: project_phases table + phase_id FK on tasks + phase_id FK on experiments

Dependencies subsystem
  crud/dependencies.py  →  api/routes/dependencies.py
  DB: task_dependencies table
  Cycle detection: BFS on add, rolled back on cycle
```

Both subsystems surface in the same frontend views (Board, TaskDetail) but have no shared data path.

---

## Data Model

### New table: `project_phases`

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
```

**Key decisions:**
- `color` is a hex string stored by the client — no validation beyond length
- `position` is an integer ordinal; reordering updates all affected rows
- Deleting a phase sets `phase_id = NULL` on owned tasks/experiments (SET NULL FK)

### New table: `task_dependencies`

```sql
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

**Key decisions:**
- `PRIMARY KEY (task_id, depends_on_id)` prevents duplicate edges
- `ON DELETE CASCADE` on both FKs: deleting a task removes all its dependency edges
- `dep_type` is per-edge — one task can hard-block another while soft-linking a third
- Self-dependency (`task_id == depends_on_id`) rejected at the API layer (400)
- Cross-project dependencies rejected at the API layer (400)
- Cycle detection runs at `add_dependency` time inside a transaction (BFS); rolls back on cycle (409)

### Modified tables

```sql
-- Add phase_id to tasks
ALTER TABLE tasks ADD COLUMN phase_id TEXT REFERENCES project_phases(id) ON DELETE SET NULL;

-- Add phase_id to experiments
ALTER TABLE experiments ADD COLUMN phase_id TEXT REFERENCES project_phases(id) ON DELETE SET NULL;
```

Both columns are nullable — existing rows remain unphased.

### New dataclasses (`models.py`)

**`ProjectPhase`**: `id`, `project_id`, `name`, `color`, `position`, `created_by`, `created_at`, `target_date: str | None`

**`TaskDependency`**: `task_id`, `depends_on_id`, `dep_type`, `created_by`, `created_at`

---

## Backend API

### Phases — `api/routes/phases.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/projects/{pid}/phases` | owner/editor | Create phase |
| `GET` | `/projects/{pid}/phases` | any member | List phases ordered by position |
| `PATCH` | `/projects/{pid}/phases/{phid}` | owner/editor | Update name/color/position/target_date |
| `DELETE` | `/projects/{pid}/phases/{phid}` | owner/editor | Delete; tasks/experiments go unphased |
| `PATCH` | `/projects/{pid}/tasks/{tid}/phase` | owner/editor | Assign/unassign task to phase |
| `PATCH` | `/projects/{pid}/experiments/{eid}/phase` | owner/editor | Assign/unassign experiment to phase |

### Dependencies — `api/routes/dependencies.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/projects/{pid}/tasks/{tid}/dependencies` | owner/editor | Add dep; 409 on cycle, 400 on self/cross-project |
| `DELETE` | `/projects/{pid}/tasks/{tid}/dependencies/{dep_id}` | owner/editor | Remove dep |
| `GET` | `/projects/{pid}/tasks/{tid}/dependencies` | any member | List deps + dependents |

### Modified endpoints

- `GET /projects/{pid}/tasks` and `GET /projects/{pid}/tasks/{tid}`: response includes `phase_id` and `blocked_by` (list of hard-blocking task IDs whose status is not `done`)

### Pydantic schemas (`schemas.py`)

```python
class PhaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    color: str = Field(default='#6366f1', pattern=r'^#[0-9a-fA-F]{6}$')
    position: int = Field(default=0, ge=0)
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

class DependencyCreate(BaseModel):
    depends_on_id: str
    dep_type: str = Field(default='hard', pattern='^(hard|soft)$')

class DependencyResponse(BaseModel):
    task_id: str
    depends_on_id: str
    dep_type: str
    created_by: str
    created_at: str
```

---

## CRUD Layer

### `crud/phases.py`

| Function | Signature |
|----------|-----------|
| `create_phase` | `(db_path, project_id, name, color, position, target_date, created_by) → ProjectPhase` |
| `list_phases` | `(db_path, project_id) → list[ProjectPhase]` ordered by `position` |
| `get_phase` | `(db_path, phase_id) → ProjectPhase \| None` |
| `update_phase` | `(db_path, phase_id, **kwargs) → ProjectPhase` |
| `delete_phase` | `(db_path, phase_id) → None` |
| `assign_task_phase` | `(db_path, task_id, phase_id \| None) → None` |
| `assign_experiment_phase` | `(db_path, experiment_id, phase_id \| None) → None` |

### `crud/dependencies.py`

| Function | Signature |
|----------|-----------|
| `add_dependency` | `(db_path, task_id, depends_on_id, dep_type, created_by) → TaskDependency` — raises `ValueError` on cycle/self/cross-project |
| `remove_dependency` | `(db_path, task_id, depends_on_id) → None` |
| `list_dependencies` | `(db_path, task_id) → list[TaskDependency]` — what this task waits on |
| `list_dependents` | `(db_path, task_id) → list[TaskDependency]` — what waits on this task |
| `get_blocked_by` | `(db_path, task_id) → list[str]` — IDs of hard-blocking tasks not yet done |
| `_has_cycle` | `(conn, project_id) → bool` — BFS across all dep edges in project (internal) |

---

## Frontend

### New files

**`src/components/PhaseManager.tsx`**
Rendered inside `ProjectSettingsPanel`. Displays phases as a reorderable list (drag handle, color swatch, name input, optional target date). Owner/editor only. Calls `createPhase`, `updatePhase`, `deletePhase`.

**`src/components/DependencyPicker.tsx`**
Rendered inside `TaskDetail` as a collapsible "Dependencies" section. Two lists: "Waiting on" (what I depend on) and "Blocking" (what depends on me). Inline task search to add new deps. Hard-blocked incomplete items shown in red. Cycle error shown inline on failed add.

### Modified files

**`Board.tsx`**
- Fetches phases alongside tasks: `listPhases(projectId)`
- Renders swimlane sections: one `<PhaseSwimLane>` per phase (sorted by `position`) + "Unphased" at bottom
- Swimlane header: left-border in phase color, phase name, `X / Y done` progress bar, optional target date chip
- Task cards show `🔒` badge and are visually dimmed when `blocked_by` is non-empty
- Dragging a task card between swimlane rows calls `assignTaskPhase`
- Hard-blocked card drag to `in_progress` column: snap back + toast "Blocked by: [Task X]"

**`TaskDetail.tsx`**
- Adds "Dependencies" collapsible section below description
- Renders `DependencyPicker`
- Status dropdown: disables `in_progress` and `done` options if `blocked_by` is non-empty, with tooltip listing blockers

**`ExperimentsPage.tsx`**
- Phase filter chip in `FilterToolbar` (alongside status/tag filters)
- Experiment cards show a phase color dot when assigned to a phase

**`api.ts`** — new methods
```typescript
// Phases
createPhase, listPhases, updatePhase, deletePhase,
assignTaskPhase, assignExperimentPhase

// Dependencies
addDependency, removeDependency, listDependencies

// Updated types
interface Task { ...; phase_id: string | null; blocked_by: string[] }
interface ProjectPhase { id, project_id, name, color, position, target_date, created_by, created_at }
interface TaskDependency { task_id, depends_on_id, dep_type, created_by, created_at }
```

### Board layout

```
┌─ [Phase 1: Data Collection]  ██████░░ 3/5 · due Apr 30 ─────────────┐
│  todo              in_progress         done                           │
│  [Task A]          [Task B 🔒]         [Task C]                       │
│                    [Task D]                                           │
├─ [Phase 2: Training]  ░░░░░░░░ 0/3 ──────────────────────────────────┤
│  [Task E]          —                   —                              │
├─ [Unphased] ──────────────────────────────────────────────────────────┤
│  [Task F]          [Task G]            —                              │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Add dep creates cycle | BFS in transaction → rollback → API 409 `"cycle detected"` |
| Self-dependency | API 400 `"task cannot depend on itself"` |
| Cross-project dependency | API 400 `"tasks must belong to the same project"` |
| Assign task to phase from different project | API 400 `"phase does not belong to this project"` |
| Delete phase with tasks | Tasks set to `phase_id=NULL` (SET NULL), no error |
| Hard-blocked drag to `in_progress` | Frontend: toast + drag reverts |
| Hard-blocked status dropdown | Frontend: options disabled + tooltip listing blockers |

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Add | `EvoScientist/pm/db.py` | `project_phases`, `task_dependencies` tables; `phase_id` migration on tasks + experiments |
| Add | `EvoScientist/pm/models.py` | `ProjectPhase`, `TaskDependency` dataclasses |
| Create | `EvoScientist/pm/crud/phases.py` | Phase CRUD + assign helpers |
| Create | `EvoScientist/pm/crud/dependencies.py` | Dependency CRUD + BFS cycle detection |
| Modify | `EvoScientist/pm/api/schemas.py` | `PhaseCreate`, `PhaseResponse`, `DependencyCreate`, `DependencyResponse` |
| Create | `EvoScientist/pm/api/routes/phases.py` | 6 phase endpoints |
| Create | `EvoScientist/pm/api/routes/dependencies.py` | 3 dependency endpoints |
| Modify | `EvoScientist/pm/api/app.py` | Register phases + dependencies routers |
| Modify | `EvoScientist/pm/api/routes/tasks.py` | Include `phase_id` + `blocked_by` in task responses |
| Create | `EvoScientist/pm/frontend/src/components/PhaseManager.tsx` | Phase CRUD UI in settings |
| Create | `EvoScientist/pm/frontend/src/components/DependencyPicker.tsx` | Dep picker in TaskDetail |
| Modify | `EvoScientist/pm/frontend/src/pages/Board.tsx` | Phase swimlanes, blocked badges |
| Modify | `EvoScientist/pm/frontend/src/pages/TaskDetail.tsx` (or component) | Dependencies section, disabled status |
| Modify | `EvoScientist/pm/frontend/src/pages/ExperimentsPage.tsx` | Phase filter chip |
| Modify | `EvoScientist/pm/frontend/src/api.ts` | New types + API methods |
| Create | `tests/pm/test_phase_crud.py` | Phase CRUD tests |
| Create | `tests/pm/test_dependency_crud.py` | Dep CRUD + cycle detection tests |
| Create | `tests/pm/test_phase_routes.py` | Phase API tests |
| Create | `tests/pm/test_dependency_routes.py` | Dep API tests |

---

## Testing

### Backend

**`tests/pm/test_phase_crud.py`**
- Create phase, list ordered by position, get, update, delete (tasks go unphased), assign task/experiment to phase

**`tests/pm/test_dependency_crud.py`**
- Add hard dep, add soft dep, remove dep, self-dep raises ValueError, cycle A→B→C→A rejected, cross-project rejected, `get_blocked_by` returns only hard blockers not yet done

**`tests/pm/test_phase_routes.py`**
- 201 create, 200 list, 404 unknown phase, 403 viewer cannot create/update/delete, 400 cross-project phase assign

**`tests/pm/test_dependency_routes.py`**
- 201 add dep, 204 remove, 409 cycle, 400 self-dep, 200 list returns both deps + dependents, task detail includes `blocked_by`

### Frontend (Vitest)

**`PhaseManager.test.tsx`**: renders phase list, creates new phase, color picker updates, delete removes from list

**`DependencyPicker.test.tsx`**: shows "Waiting on" and "Blocking" sections, adds dep, shows cycle error inline

**`Board.test.tsx`** (extend existing): swimlanes render per phase, unphased section present, blocked card shows 🔒 badge, hard-block drag shows toast

---

## Out of Scope

- Backend enforcement of hard block status transitions
- Gantt / timeline view
- Phase templates
- Experiment-to-experiment dependencies
- Dependency visualization graph
