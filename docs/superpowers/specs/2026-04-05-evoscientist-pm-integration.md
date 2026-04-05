# EvoScientist–PM Integration Design Spec

**Goal:** Enable biology lab scientists to launch EvoScientist AI agent runs directly from PM task cards and view live streaming output, all within the existing kanban board UI.

**Architecture:** Separate EvoScientist runner microservice (`pm/runner/`) wraps `create_cli_agent()`. The PM backend acts as the sole API gateway — the frontend never talks to the runner directly. Results stream via Server-Sent Events (SSE) proxied through the PM backend and are persisted in a new `runs` SQLite table.

**Tech Stack:** Python 3.11+, FastAPI, asyncio, SSE (`text/event-stream`), React 18, TanStack Query v5, `EventSource` Web API, existing IBM Plex / Deep Lab dark theme.

---

## Design Decisions

| Question | Decision |
|----------|----------|
| Integration approach | B — Separate runner microservice |
| Interaction model | C — Pre-filled editable prompt, single-shot, output saved as result card |
| Agents exposed | 4 — Research, Code, Data Analysis, Writing |
| Panel location | B — Dedicated "⬡ AI RUNS" tab in TaskDetail drawer |
| Output display | C — Collapsible result cards with Copy + Add to Notes actions |

---

## Architecture

```
Frontend (React SPA)
    │
    ▼  REST + SSE
PM Backend  (FastAPI :8000)
    │  ├─ persists runs in SQLite  (new `runs` table)
    │  └─ proxies SSE stream from runner
    │
    ▼  HTTP  (internal, never exposed to browser)
Runner Service  (FastAPI :8001)
    └─ create_cli_agent() → asyncio background task → SSE token stream
```

**Data flow for a single run:**
1. User selects agent + edits prompt → clicks **▶ RUN EVOSCIENTIST**
2. Frontend → `POST /api/v1/projects/{pid}/tasks/{tid}/runs` (`{agent_type, prompt}`)
3. PM creates `runs` record (status: `pending`), POSTs to runner, sets task `session_id = run_id`
4. Frontend opens SSE: `GET /api/v1/runs/{run_id}/stream`
5. PM proxies runner's SSE; accumulates output tokens to DB as they arrive
6. Runner emits `status: done` or `status: failed` → PM closes SSE, finalises record
7. Frontend invalidates `['runs', taskId]` → result card appears in history

---

## Data Model

### New `runs` table (PM SQLite)

```sql
CREATE TABLE runs (
  id           TEXT PRIMARY KEY,
  task_id      TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
  project_id   TEXT NOT NULL,
  agent_type   TEXT NOT NULL,   -- 'research' | 'code' | 'data_analysis' | 'writing'
  prompt       TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'pending',
                                -- pending | running | done | failed | cancelled
  output       TEXT,            -- full accumulated output (saved on completion)
  error        TEXT,            -- error message if failed
  started_at   TEXT,
  finished_at  TEXT,
  created_by   TEXT NOT NULL,
  created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### Modified: `tasks` table

`session_id` (already present, unused) — populated with the `run_id` of the most recent run for that task.

### SSE event schema (runner → PM → frontend)

```
data: {"type": "token",  "data": "Found 3 protocols…"}
data: {"type": "status", "data": "running"}
data: {"type": "status", "data": "done"}
data: {"type": "error",  "data": "LLM rate limit exceeded"}
```

### Frontend `Run` type (`api.ts`)

```typescript
interface Run {
  id: string
  task_id: string
  agent_type: 'research' | 'code' | 'data_analysis' | 'writing'
  prompt: string
  status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
  output: string | null
  error: string | null
  started_at: string | null
  finished_at: string | null
  created_by: string
  created_at: string
}
```

---

## Backend Changes

### New: Runner service (`EvoScientist/pm/runner/`)

```
pm/runner/
├── main.py           # FastAPI app, CORS (localhost only), lifespan
├── agent_runner.py   # create_cli_agent wrapper; asyncio task registry
├── routes/
│   └── runs.py       # POST /runs, GET /runs/{id}/stream, DELETE /runs/{id}
└── models.py         # RunRequest, RunEvent, RunStatus
```

**Runner API:**

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/runs` | Start agent run in background asyncio task; returns `{run_id}` immediately |
| `GET` | `/runs/{run_id}/stream` | SSE: emits `token` and `status` events until done/failed |
| `DELETE` | `/runs/{run_id}` | Cancel in-progress run (cancels asyncio task) |

**`agent_runner.py` core logic:**
```python
_active_runs: dict[str, asyncio.Task] = {}

async def start_run(run_id: str, agent_type: str, prompt: str, workspace_dir: Path) -> None:
    agent = create_cli_agent(workspace_dir=workspace_dir)
    task = asyncio.create_task(_stream_agent(run_id, agent, prompt))
    _active_runs[run_id] = task

async def _stream_agent(run_id: str, agent, prompt: str) -> None:
    async for chunk in agent.astream({"messages": [("human", prompt)]}):
        yield RunEvent(type="token", data=extract_text(chunk))
    yield RunEvent(type="status", data="done")
```

**Workspace isolation:** Each run uses `{EVOSCIENTIST_WORKSPACE_DIR}/{project_id}/{task_id}/` so artifacts from different tasks never collide.

**Config (`pm/runner/main.py`):**
- `RUNNER_HOST` env var (default `127.0.0.1`)
- `RUNNER_PORT` env var (default `8001`)

### New PM backend files

| File | Purpose |
|------|---------|
| `pm/crud/runs.py` | `create_run`, `get_run`, `list_runs_for_task`, `update_run_status`, `append_run_output` |
| `pm/api/routes/runs.py` | PM-side run endpoints (see below) |

**New PM API endpoints (`pm/api/routes/runs.py`):**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/projects/{pid}/tasks/{tid}/runs` | Member | Create run, call runner, update task `session_id` |
| `GET` | `/api/v1/projects/{pid}/tasks/{tid}/runs` | Member | List all runs for a task |
| `GET` | `/api/v1/runs/{run_id}/stream` | Member | SSE proxy to runner |
| `DELETE` | `/api/v1/runs/{run_id}` | Member | Cancel run (calls runner DELETE) |

### Modified PM backend files

| File | Change |
|------|--------|
| `pm/db.py` | Add `runs` table to `CREATE_SCHEMA` |
| `pm/api/main.py` | Register `runs` router; add `RUNNER_URL` setting (default `http://127.0.0.1:8001`) |
| `pm/api/schemas.py` | Add `RunCreate`, `RunResponse`, `RunListResponse` |
| `pm/api/routes/tasks.py` | `PUT` handler: update `session_id` on task when run starts |

---

## Frontend Changes

### New files

**`src/components/AiRunsTab.tsx`**

Props: `{ task: Task, projectId: string }`

Renders the full AI RUNS tab content:
- **Agent grid** — 2×2 grid of agent buttons (Research / Code / Data Analysis / Writing); selected agent highlighted cyan
- **Prompt textarea** — pre-filled with `${task.title}. ${task.description ?? ''}`, editable, 3 rows
- **▶ RUN EVOSCIENTIST button** — disabled while a run is `running`; label changes to **▶ RUN AGAIN** when history exists
- **Active run card** (while `status === 'running'`):
  - Pulsing cyan dot + "RUNNING" label
  - Scrolling token output (monospace, dark bg)
  - **■ STOP** button → calls `cancelRun(run_id)`
- **Run history** — list of `Run` objects from `listRuns(taskId)`, newest first:
  - Collapsed by default; click header to expand
  - Expanded: full output text + **📋 Copy** + **💬 Add to Notes** actions
  - Status badges: ✓ green (done), ✗ rose (failed), ◌ slate (cancelled)
  - Timestamp + duration (computed from `started_at`/`finished_at`)

**`src/hooks/useRunStream.ts`**

```typescript
function useRunStream(runId: string | null): { output: string; status: RunStatus }
```

- Opens `EventSource` on `GET /api/v1/runs/{runId}/stream` when `runId` is non-null
- Accumulates `token` events into `output` string
- Updates `status` on `status` events
- Closes `EventSource` on `done`, `failed`, or `cancelled`
- Cleans up on unmount

### Modified files

**`src/pages/TaskDetail.tsx`**
- Add tab toggle: `DETAILS` | `⬡ AI RUNS`
- Import and render `<AiRunsTab task={task} projectId={projectId} />` when AI tab is active
- Tab label shows a count badge when `runs.length > 0`: `⬡ AI RUNS (2)`

**`src/api.ts`** — 4 new functions:
```typescript
createRun: (projectId: string, taskId: string, data: { agent_type: string; prompt: string }) =>
  request<Run>('POST', `/projects/${projectId}/tasks/${taskId}/runs`, data),

listRuns: (projectId: string, taskId: string) =>
  request<Run[]>('GET', `/projects/${projectId}/tasks/${taskId}/runs`),

cancelRun: (runId: string) =>
  request<void>('DELETE', `/runs/${runId}`),

streamRunUrl: (runId: string) => `/api/v1/runs/${runId}/stream`,
```

---

## UI Behaviour

### AI RUNS tab — interaction flow

1. **Idle:** Agent grid (Research selected by default) + editable prompt pre-filled from task title/description + **▶ RUN EVOSCIENTIST** button
2. **Run starts:** Button disabled, active run card appears with pulsing indicator + streaming output
3. **Run completes:** Active run card replaced by result card (collapsed, showing agent type + duration). Run button re-enabled as **▶ RUN AGAIN**. TanStack Query cache for `['runs', taskId]` invalidated.
4. **Result card expanded:** Shows full output + **📋 Copy** (copies output to clipboard) + **💬 Add to Notes** (appends a comment to the task via existing `POST .../comments` endpoint with `body: output`)
5. **Run failed:** Card shows ✗ badge + error message in rose. Run button re-enabled.

### "Add to Notes" behaviour

Calls the existing `POST /api/v1/projects/{pid}/tasks/{tid}/comments` endpoint:
```json
{ "body": "**[Research Run · 2026-04-05]**\n\n{output}" }
```
The task comment appears in the DETAILS tab Lab Notes section. No new endpoint needed.

---

## Startup

The runner service is started alongside the PM backend. The existing CLI command `EvoSci dashboard` will be updated to start both:

```bash
# Existing
uvicorn EvoScientist.pm.api.main:app --port 8000

# Added (background)
uvicorn EvoScientist.pm.runner.main:app --port 8001
```

A `RUNNER_URL` env var on the PM backend points to the runner (default `http://127.0.0.1:8001`). If the runner is unreachable, the PM returns `503 Service Unavailable` on run creation with a clear error message.

---

## Out of Scope

- Multi-turn conversation within a run (single-shot only; each new run starts fresh)
- Planner and Debug agents (Debug is terminal-native; Planner is redundant with PM task structure)
- Artifact file browser (artifacts written to workspace are accessible via filesystem, not surfaced in PM UI)
- Run notifications / webhooks
- Per-project workspace configuration in PM UI (workspace path set via env var)
