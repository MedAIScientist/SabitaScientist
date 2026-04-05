# Lab Notes & Results Storage Design

**Date:** 2026-04-05
**Feature:** Experiment entity with lab notes and lab results, integrated into the EvoScientist PM dashboard

---

## Goal

Enable lab scientists to group related tasks under an **Experiment**, and attach freeform markdown documents — **lab notes** (observations, protocols, running log entries) and **lab results** (analysis write-ups, findings) — to each experiment. Experiments live at the project level and link to tasks via a many-to-many join.

---

## Architecture Overview

A new `Experiment` entity sits between `Project` and `Task`. Experiments are owned by a project and link to tasks via a join table. Each experiment holds an arbitrary number of **entries** — each entry is either a `note` or a `result`, distinguished by a `type` tag. Both types share identical structure (title + markdown body), so a single `experiment_entries` table handles both.

```
Project
  └── Experiment (many per project)
        ├── experiment_tasks join → Task (many-to-many)
        └── ExperimentEntry (many per experiment, type = 'note' | 'result')
```

---

## Data Model

### New SQLite tables (additions to `EvoScientist/pm/db.py` `_SCHEMA`)

```sql
CREATE TABLE IF NOT EXISTS experiments (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    hypothesis  TEXT,
    protocol    TEXT,
    status      TEXT NOT NULL DEFAULT 'planned'
                CHECK(status IN ('planned', 'running', 'completed')),
    tags        TEXT NOT NULL DEFAULT '[]',   -- JSON array of strings
    deadline    TEXT,                          -- ISO date string
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

### New dataclasses (additions to `EvoScientist/pm/models.py`)

```python
@dataclass
class Experiment:
    id: str
    project_id: str
    name: str
    status: str           # 'planned' | 'running' | 'completed'
    tags: list[str]       # deserialized from JSON TEXT column
    created_by: str
    created_at: str
    updated_at: str
    hypothesis: str | None = None
    protocol: str | None = None
    deadline: str | None = None   # ISO date string

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

---

## Backend

### New files

| File | Responsibility |
|------|----------------|
| `EvoScientist/pm/crud/experiments.py` | `create_experiment`, `get_experiment`, `list_experiments`, `update_experiment`, `delete_experiment`, `link_task`, `unlink_task`, `list_linked_tasks` |
| `EvoScientist/pm/crud/experiment_entries.py` | `create_entry`, `get_entry`, `list_entries` (with optional `type` filter), `update_entry`, `delete_entry` |
| `EvoScientist/pm/api/routes/experiments.py` | All HTTP routes for experiments and entries |

### Modified files

| File | Change |
|------|--------|
| `EvoScientist/pm/models.py` | Add `Experiment`, `ExperimentEntry` dataclasses |
| `EvoScientist/pm/db.py` | Add 3 new tables to `_SCHEMA` |
| `EvoScientist/pm/api/schemas.py` | Add `ExperimentCreate`, `ExperimentUpdate`, `ExperimentResponse`, `ExperimentEntryCreate`, `ExperimentEntryUpdate`, `ExperimentEntryResponse` |
| `EvoScientist/pm/api/app.py` | Register experiments router |

### API routes

All routes prefixed `/api/v1/projects/{project_id}/experiments`.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/` | owner/editor | Create experiment → 201 |
| `GET` | `/` | all roles | List experiments in project |
| `GET` | `/{exp_id}` | all roles | Get experiment detail |
| `PATCH` | `/{exp_id}` | owner/editor | Update experiment fields |
| `DELETE` | `/{exp_id}` | owner | Delete experiment → 204 |
| `POST` | `/{exp_id}/tasks` | owner/editor | Link a task `{task_id}` → 201 |
| `DELETE` | `/{exp_id}/tasks/{task_id}` | owner/editor | Unlink task → 204 |
| `GET` | `/{exp_id}/entries` | all roles | List entries (optional `?type=note\|result`) |
| `POST` | `/{exp_id}/entries` | owner/editor | Create entry → 201 |
| `PATCH` | `/{exp_id}/entries/{entry_id}` | owner/editor | Update entry |
| `DELETE` | `/{exp_id}/entries/{entry_id}` | owner/editor | Delete entry → 204 |

### Schemas

```python
class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hypothesis: str | None = None
    protocol: str | None = None
    status: str = Field(default='planned', pattern='^(planned|running|completed)$')
    tags: list[str] = []
    deadline: str | None = None  # ISO date

class ExperimentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    hypothesis: str | None = None
    protocol: str | None = None
    status: str | None = Field(default=None, pattern='^(planned|running|completed)$')
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
    type: str = Field(pattern='^(note|result)$')
    title: str = Field(min_length=1, max_length=200)
    body: str = ''

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

---

## Frontend

### New files

| File | Responsibility |
|------|----------------|
| `src/pages/ExperimentsPage.tsx` | List experiments for current project; create new; click to open detail |
| `src/components/ExperimentDetail.tsx` | Slide-in drawer with OVERVIEW / NOTES / RESULTS tabs |
| `src/components/EntryEditor.tsx` | Shared create/edit form for notes and results (title + textarea) |
| `src/hooks/useExperiments.ts` | TanStack Query v5 wrappers for all experiment + entry API calls |
| `src/pages/__tests__/ExperimentsPage.test.tsx` | Tests for list, empty state, role-gated create button |
| `src/components/__tests__/ExperimentDetail.test.tsx` | Tests for tab switching, entry rendering, task linking |
| `src/components/__tests__/EntryEditor.test.tsx` | Tests for form submit, cancel, validation |

### Modified files

| File | Change |
|------|--------|
| `src/api.ts` | Add `Experiment`, `ExperimentEntry` TypeScript interfaces + 11 API functions |
| `src/pages/Board.tsx` | Add `⚗ EXPERIMENTS` button in project header navigating to `ExperimentsPage` |

### Component breakdown

**`ExperimentsPage`**
- Grid of experiment cards: name, status badge (planned=amber, running=cyan, completed=emerald), tag chips, entry counts ("3 notes · 1 result"), linked task count.
- "＋ New Experiment" button (owner/editor only). Click opens a creation modal with name + status fields; hypothesis/protocol/tags/deadline editable after creation inside ExperimentDetail.
- Click any card → opens `ExperimentDetail` drawer.

**`ExperimentDetail`** (drawer, same pattern as `TaskDetail`)
- Three tabs: **OVERVIEW**, **NOTES**, **RESULTS**
- OVERVIEW tab: editable name, hypothesis (textarea), protocol (textarea), status selector, tags input, deadline picker. Below: linked tasks section — searchable task picker (search by title), linked tasks as removable chips.
- NOTES tab: list of note entries (title + collapsed body preview). "+ Add Note" button opens `EntryEditor`. Click entry to expand inline; pencil icon to edit via `EntryEditor`; trash to delete.
- RESULTS tab: identical layout but filtered to `type='result'`. "+ Add Result" button.

**`EntryEditor`** (modal or inline panel)
- Title input (required), body textarea (markdown, min-height 120px).
- SAVE and CANCEL buttons. Submits to `createEntry` or `updateEntry` mutation.

**`useExperiments` hook**
- `useExperiments(projectId)` — query for list
- `useExperiment(projectId, expId)` — query for single
- `useCreateExperiment`, `useUpdateExperiment`, `useDeleteExperiment`
- `useLinkTask`, `useUnlinkTask`
- `useEntries(projectId, expId, type?)` — query for entries
- `useCreateEntry`, `useUpdateEntry`, `useDeleteEntry`

### TypeScript interfaces

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

---

## Testing

### Backend tests

| File | Coverage |
|------|----------|
| `tests/pm/test_crud_experiments.py` | create, get, list, update, delete; link/unlink tasks; list linked tasks |
| `tests/pm/test_crud_experiment_entries.py` | create, get, list (with type filter), update, delete |
| `tests/pm/test_api_experiments.py` | All 11 API routes; 401 without auth; 404 for missing experiment; role enforcement (viewer cannot create/edit/delete) |

### Frontend tests

| File | Coverage |
|------|----------|
| `tests/ExperimentsPage.test.tsx` | Renders card list, empty state, create button visible to owner/editor, hidden to viewer |
| `tests/ExperimentDetail.test.tsx` | Tab switching, notes/results rendered per type, task linker renders linked tasks |
| `tests/EntryEditor.test.tsx` | Submit with valid data calls mutation, cancel closes editor, empty title disables submit |

---

## Error Handling

- `GET /experiments/{exp_id}` on a non-existent or wrong-project experiment → 404
- `POST /{exp_id}/tasks` with a `task_id` that belongs to a different project → 422 with message "Task does not belong to this project"
- `POST /{exp_id}/tasks` with a `task_id` already linked → 409 Conflict
- Viewer role attempting create/edit/delete → 403 (via `require_project_role`)
- Tags stored as JSON; malformed JSON in DB falls back to `[]` on deserialization

---

## Out of Scope

- File attachments (images, CSVs) — entries are markdown text only
- Experiment versioning or history
- Exporting experiments to PDF/LaTeX
- Cross-project experiments
