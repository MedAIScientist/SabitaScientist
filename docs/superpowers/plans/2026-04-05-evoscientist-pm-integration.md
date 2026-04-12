# EvoScientist–PM Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable lab scientists to launch EvoScientist AI agent runs from PM task cards with live streaming output, persisted result cards, and a dedicated "⬡ AI RUNS" tab in the TaskDetail drawer.

**Architecture:** Separate FastAPI runner service (`pm/runner/`) wraps `create_cli_agent()` with asyncio queue-based token streaming. PM backend acts as sole API gateway — creates run records in SQLite, proxies SSE from runner via `httpx`, and updates run status as tokens stream. Frontend uses `fetch`+`ReadableStream` for auth-capable SSE and renders output in collapsible result cards.

**Tech Stack:** Python 3.11+, FastAPI, asyncio, httpx, Server-Sent Events (`text/event-stream`), React 18, TanStack Query v5, Vitest + Testing Library.

---

## File Map

**New backend files:**
- `EvoScientist/pm/models.py` — add `Run` dataclass
- `EvoScientist/pm/db.py` — add `runs` table to `_SCHEMA`
- `EvoScientist/pm/crud/runs.py` — CRUD for Run entities
- `EvoScientist/pm/api/schemas.py` — add `RunCreate`, `RunResponse`
- `EvoScientist/pm/api/routes/runs.py` — PM run endpoints (create, list, SSE proxy, cancel)
- `EvoScientist/pm/api/app.py` — register runs router
- `EvoScientist/pm/runner/__init__.py` — package init
- `EvoScientist/pm/runner/models.py` — RunRequest, RunEvent Pydantic models
- `EvoScientist/pm/runner/agent_runner.py` — asyncio task registry + agent streaming
- `EvoScientist/pm/runner/main.py` — runner FastAPI app factory
- `EvoScientist/pm/runner/routes/__init__.py` — package init
- `EvoScientist/pm/runner/routes/runs.py` — runner run endpoints (start, stream, cancel)

**New test files:**
- `tests/pm/test_crud_runs.py`
- `tests/pm/test_api_runs.py`
- `tests/pm/test_runner_routes.py`

**Modified backend files:**
- `EvoScientist/cli/_app.py` — co-start runner in `dashboard` command

**New frontend files:**
- `EvoScientist/pm/frontend/src/hooks/useRunStream.ts`
- `EvoScientist/pm/frontend/src/components/AiRunsTab.tsx`
- `EvoScientist/pm/frontend/src/hooks/__tests__/useRunStream.test.ts`
- `EvoScientist/pm/frontend/src/components/__tests__/AiRunsTab.test.tsx`

**Modified frontend files:**
- `EvoScientist/pm/frontend/src/api.ts` — add `Run` interface + 4 run functions
- `EvoScientist/pm/frontend/src/pages/TaskDetail.tsx` — add tab toggle + `AiRunsTab`
- `EvoScientist/pm/frontend/src/pages/__tests__/TaskDetail.test.tsx` — add tab tests

---

## Task 1: `Run` dataclass + `runs` table + CRUD

**Files:**
- Modify: `EvoScientist/pm/models.py`
- Modify: `EvoScientist/pm/db.py`
- Create: `EvoScientist/pm/crud/runs.py`
- Create: `tests/pm/test_crud_runs.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/pm/test_crud_runs.py
"""Tests for Run CRUD operations."""
from __future__ import annotations
from pathlib import Path
import pytest
from EvoScientist.pm.crud.projects import create_project
from EvoScientist.pm.crud.tasks import create_task
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.crud.runs import (
    create_run, get_run, list_runs_for_task,
    update_run_status, update_run_output,
)
from EvoScientist.pm.db import create_schema

@pytest.fixture
def setup(tmp_path: Path):
    db = tmp_path / "test.db"
    create_schema(db)
    user = create_user(db, username="u1", password_hash="h")
    project = create_project(db, name="P1", created_by=user.id)
    task = create_task(db, project_id=project.id, title="Gel assay", created_by=user.id)
    return db, user, project, task

def test_create_and_get_run(setup):
    db, user, _, task = setup
    run = create_run(db, task_id=task.id, project_id=task.project_id,
                     agent_type="research", prompt="Find gel protocols", created_by=user.id)
    assert run.id is not None
    assert run.status == "pending"
    assert run.agent_type == "research"
    fetched = get_run(db, run.id)
    assert fetched is not None
    assert fetched.prompt == "Find gel protocols"

def test_list_runs_for_task(setup):
    db, user, _, task = setup
    create_run(db, task.id, task.project_id, "research", "p1", user.id)
    create_run(db, task.id, task.project_id, "code", "p2", user.id)
    runs = list_runs_for_task(db, task.id)
    assert len(runs) == 2
    assert {r.agent_type for r in runs} == {"research", "code"}

def test_update_run_status(setup):
    db, user, _, task = setup
    run = create_run(db, task.id, task.project_id, "research", "p", user.id)
    update_run_status(db, run.id, "running")
    assert get_run(db, run.id).status == "running"

def test_update_run_output(setup):
    db, user, _, task = setup
    run = create_run(db, task.id, task.project_id, "research", "p", user.id)
    update_run_output(db, run.id, "done", "Found 3 protocols.")
    fetched = get_run(db, run.id)
    assert fetched.status == "done"
    assert fetched.output == "Found 3 protocols."
    assert fetched.finished_at is not None

def test_get_run_missing(setup):
    db, *_ = setup
    assert get_run(db, "nonexistent") is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
uv run pytest tests/pm/test_crud_runs.py -v 2>&1 | tail -15
```

Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Add `Run` dataclass to `EvoScientist/pm/models.py`**

After the `Comment` dataclass, add:

```python
@dataclass
class Run:
    id: str
    task_id: str
    project_id: str
    agent_type: str       # 'research' | 'code' | 'data_analysis' | 'writing'
    prompt: str
    status: str           # 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
    created_by: str
    created_at: str
    output: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
```

- [ ] **Step 4: Add `runs` table to `EvoScientist/pm/db.py`**

In `_SCHEMA`, after the `auth_tokens` table block (before the closing `"""`), add:

```sql
CREATE TABLE IF NOT EXISTS runs (
    id           TEXT PRIMARY KEY,
    task_id      TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    project_id   TEXT NOT NULL,
    agent_type   TEXT NOT NULL
                 CHECK(agent_type IN ('research', 'code', 'data_analysis', 'writing')),
    prompt       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK(status IN ('pending', 'running', 'done', 'failed', 'cancelled')),
    output       TEXT,
    error        TEXT,
    started_at   TEXT,
    finished_at  TEXT,
    created_by   TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
```

- [ ] **Step 5: Create `EvoScientist/pm/crud/runs.py`**

```python
"""CRUD operations for Run entities."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Run


def create_run(
    db_path: Path,
    task_id: str,
    project_id: str,
    agent_type: str,
    prompt: str,
    created_by: str,
) -> Run:
    """Create a run record with status 'pending' and return it."""
    run_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO runs (id, task_id, project_id, agent_type, prompt,
               status, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (run_id, task_id, project_id, agent_type, prompt, created_by, now),
        )
    return Run(
        id=run_id,
        task_id=task_id,
        project_id=project_id,
        agent_type=agent_type,
        prompt=prompt,
        status="pending",
        created_by=created_by,
        created_at=now,
    )


def get_run(db_path: Path, run_id: str) -> Run | None:
    """Return Run by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return _row_to_run(row) if row else None


def list_runs_for_task(db_path: Path, task_id: str) -> list[Run]:
    """Return all runs for a task, newest first."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE task_id = ? ORDER BY created_at DESC",
            (task_id,),
        ).fetchall()
    return [_row_to_run(r) for r in rows]


def update_run_status(db_path: Path, run_id: str, status: str) -> None:
    """Update run status; sets started_at when transitioning to 'running'."""
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        if status == "running":
            conn.execute(
                "UPDATE runs SET status=?, started_at=? WHERE id=?",
                (status, now, run_id),
            )
        else:
            conn.execute("UPDATE runs SET status=? WHERE id=?", (status, run_id))


def update_run_output(
    db_path: Path, run_id: str, status: str, output: str, error: str | None = None
) -> None:
    """Save final output and terminal status (done/failed/cancelled)."""
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE runs SET status=?, output=?, error=?, finished_at=? WHERE id=?",
            (status, output, error, now, run_id),
        )


def _row_to_run(row) -> Run:
    return Run(
        id=row["id"],
        task_id=row["task_id"],
        project_id=row["project_id"],
        agent_type=row["agent_type"],
        prompt=row["prompt"],
        status=row["status"],
        output=row["output"],
        error=row["error"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        created_by=row["created_by"],
        created_at=row["created_at"],
    )
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/pm/test_crud_runs.py -v 2>&1 | tail -15
```

Expected: 5 tests PASS

- [ ] **Step 7: Commit**

```bash
git add EvoScientist/pm/models.py EvoScientist/pm/db.py \
        EvoScientist/pm/crud/runs.py tests/pm/test_crud_runs.py
git commit -m "feat(pm): add Run model, runs table, and CRUD operations"
```

---

## Task 2: PM API schemas + run routes + register router

**Files:**
- Modify: `EvoScientist/pm/api/schemas.py`
- Create: `EvoScientist/pm/api/routes/runs.py`
- Modify: `EvoScientist/pm/api/app.py`
- Create: `tests/pm/test_api_runs.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/pm/test_api_runs.py
"""Tests for PM run API endpoints."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.crud.projects import create_project, add_member
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
    import EvoScientist.pm.crud.runs as runs_mod
    import EvoScientist.pm.api.routes.auth as auth_r
    import EvoScientist.pm.api.routes.users as users_r
    import EvoScientist.pm.api.routes.projects as proj_r
    import EvoScientist.pm.api.routes.tasks as tasks_r
    import EvoScientist.pm.api.routes.runs as runs_r
    for mod in [deps_mod, users_mod, proj_mod, tasks_mod, runs_mod,
                auth_r, users_r, proj_r, tasks_r, runs_r]:
        if hasattr(mod, "get_db_path"):
            mod.get_db_path = lambda: tmp_db
    return create_app(tmp_db)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def member_token(tmp_db, client):
    create_user(tmp_db, username="lab", password_hash=hash_password("pass"))
    resp = client.post("/api/v1/auth/login", json={"username": "lab", "password": "pass"})
    return resp.json()["token"]


@pytest.fixture
def project_task(tmp_db, member_token, client):
    headers = {"Authorization": f"Bearer {member_token}"}
    proj = client.post("/api/v1/projects", json={"name": "CRISPR"}, headers=headers).json()
    task = client.post(
        f"/api/v1/projects/{proj['id']}/tasks",
        json={"title": "Gel assay"},
        headers=headers,
    ).json()
    return proj["id"], task["id"]


def test_create_run_returns_201(client, member_token, project_task):
    project_id, task_id = project_task
    with patch("EvoScientist.pm.api.routes.runs._notify_runner", new=AsyncMock()):
        resp = client.post(
            f"/api/v1/projects/{project_id}/tasks/{task_id}/runs",
            json={"agent_type": "research", "prompt": "Find gel protocols"},
            headers={"Authorization": f"Bearer {member_token}"},
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["agent_type"] == "research"
    assert data["task_id"] == task_id


def test_list_runs_returns_empty_initially(client, member_token, project_task):
    project_id, task_id = project_task
    resp = client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/runs",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_runs_returns_created_runs(client, member_token, project_task):
    project_id, task_id = project_task
    headers = {"Authorization": f"Bearer {member_token}"}
    with patch("EvoScientist.pm.api.routes.runs._notify_runner", new=AsyncMock()):
        client.post(
            f"/api/v1/projects/{project_id}/tasks/{task_id}/runs",
            json={"agent_type": "research", "prompt": "p1"},
            headers=headers,
        )
    resp = client.get(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/runs",
        headers=headers,
    )
    assert len(resp.json()) == 1


def test_create_run_requires_auth(client, project_task):
    project_id, task_id = project_task
    resp = client.post(
        f"/api/v1/projects/{project_id}/tasks/{task_id}/runs",
        json={"agent_type": "research", "prompt": "p"},
    )
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/pm/test_api_runs.py -v 2>&1 | tail -15
```

Expected: FAIL with `ImportError` or `404`

- [ ] **Step 3: Add schemas to `EvoScientist/pm/api/schemas.py`**

At the end of the file (after `CommentResponse`), add:

```python
# ── Runs ──────────────────────────────────────────────────────────────────────


class RunCreate(BaseModel):
    agent_type: str = Field(pattern="^(research|code|data_analysis|writing)$")
    prompt: str = Field(min_length=1, max_length=4096)


class RunResponse(BaseModel):
    id: str
    task_id: str
    project_id: str
    agent_type: str
    prompt: str
    status: str
    output: str | None
    error: str | None
    started_at: str | None
    finished_at: str | None
    created_by: str
    created_at: str
```

- [ ] **Step 4: Create `EvoScientist/pm/api/routes/runs.py`**

```python
"""Run endpoints — create, list, SSE proxy, cancel."""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ...crud.runs import (
    create_run,
    get_run,
    list_runs_for_task,
    update_run_output,
    update_run_status,
)
from ...crud.tasks import get_task, update_task
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role
from ..schemas import RunCreate, RunResponse

router = APIRouter()

RUNNER_URL = os.getenv("RUNNER_URL", "http://127.0.0.1:8001")


def _run_to_response(r) -> RunResponse:
    return RunResponse(
        id=r.id,
        task_id=r.task_id,
        project_id=r.project_id,
        agent_type=r.agent_type,
        prompt=r.prompt,
        status=r.status,
        output=r.output,
        error=r.error,
        started_at=r.started_at,
        finished_at=r.finished_at,
        created_by=r.created_by,
        created_at=r.created_at,
    )


async def _notify_runner(
    run_id: str, agent_type: str, prompt: str, workspace_dir: str
) -> None:
    """Fire-and-forget: tell the runner service to start the agent run."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{RUNNER_URL}/runs",
                json={
                    "run_id": run_id,
                    "agent_type": agent_type,
                    "prompt": prompt,
                    "workspace_dir": workspace_dir,
                },
            )
    except Exception:
        # Runner unreachable — mark run as failed so UI shows an error
        update_run_status(get_db_path(), run_id, "failed")


@router.post(
    "/{project_id}/tasks/{task_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_run(
    project_id: str,
    task_id: str,
    body: RunCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Create a run record and dispatch it to the runner service."""
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")

    run = create_run(
        get_db_path(),
        task_id=task_id,
        project_id=project_id,
        agent_type=body.agent_type,
        prompt=body.prompt,
        created_by=current_user.id,
    )
    # Link run to task via session_id
    update_task(get_db_path(), task_id, session_id=run.id)

    # Workspace isolated per project + task
    workspace_base = os.getenv(
        "EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs")
    )
    workspace_dir = str(Path(workspace_base) / project_id / task_id)

    background_tasks.add_task(
        _notify_runner, run.id, body.agent_type, body.prompt, workspace_dir
    )
    return _run_to_response(run)


@router.get("/{project_id}/tasks/{task_id}/runs", response_model=list[RunResponse])
def list_task_runs(
    project_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List all runs for a task, newest first."""
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return [_run_to_response(r) for r in list_runs_for_task(get_db_path(), task_id)]


@router.get("/runs/{run_id}/stream")
async def stream_run_output(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """SSE stream of run output tokens. Returns saved output if run is complete."""
    run = get_run(get_db_path(), run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Already complete — stream saved output then close
    if run.status in ("done", "failed", "cancelled"):
        async def _completed():
            if run.output:
                yield f'data: {json.dumps({"type": "token", "data": run.output})}\n\n'
            yield f'data: {json.dumps({"type": "status", "data": run.status})}\n\n'
        return StreamingResponse(
            _completed(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Mark running and proxy SSE from runner
    update_run_status(get_db_path(), run_id, "running")

    async def _proxy():
        accumulated: list[str] = []
        final_status = "failed"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
                async with client.stream(
                    "GET", f"{RUNNER_URL}/runs/{run_id}/stream"
                ) as resp:
                    async for raw_line in resp.aiter_lines():
                        if not raw_line:
                            continue
                        yield f"{raw_line}\n\n"
                        if raw_line.startswith("data: "):
                            try:
                                event = json.loads(raw_line[6:])
                                if event.get("type") == "token":
                                    accumulated.append(event["data"])
                                elif event.get("type") == "status":
                                    final_status = event["data"]
                            except Exception:
                                pass
        except Exception as exc:
            yield f'data: {json.dumps({"type": "error", "data": str(exc)})}\n\n'
            yield f'data: {json.dumps({"type": "status", "data": "failed"})}\n\n'
            final_status = "failed"
        finally:
            update_run_output(
                get_db_path(), run_id, final_status, "".join(accumulated)
            )

    return StreamingResponse(
        _proxy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """Cancel a running run."""
    run = get_run(get_db_path(), run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.delete(f"{RUNNER_URL}/runs/{run_id}")
    except Exception:
        pass
    update_run_status(get_db_path(), run_id, "cancelled")
```

- [ ] **Step 5: Register runs router in `EvoScientist/pm/api/app.py`**

Add runs import and router registration. Change:
```python
from .routes import auth, projects, tasks, users
```
to:
```python
from .routes import auth, projects, runs, tasks, users
```

After `app.include_router(tasks.router, ...)`, add:
```python
    app.include_router(runs.router, prefix="/api/v1", tags=["runs"])
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/pm/test_api_runs.py -v 2>&1 | tail -15
```

Expected: 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git add EvoScientist/pm/api/schemas.py EvoScientist/pm/api/routes/runs.py \
        EvoScientist/pm/api/app.py tests/pm/test_api_runs.py
git commit -m "feat(pm): add run API routes (create, list, SSE proxy, cancel)"
```

---

## Task 3: Runner service — models + agent_runner

**Files:**
- Create: `EvoScientist/pm/runner/__init__.py`
- Create: `EvoScientist/pm/runner/models.py`
- Create: `EvoScientist/pm/runner/agent_runner.py`

No test file in this task — agent_runner is tested via the runner route tests in Task 4.

- [ ] **Step 1: Create `EvoScientist/pm/runner/__init__.py`**

```python
"""EvoScientist PM runner service — wraps create_cli_agent for HTTP/SSE dispatch."""
```

- [ ] **Step 2: Create `EvoScientist/pm/runner/models.py`**

```python
"""Pydantic models for the runner service API."""
from __future__ import annotations
from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    run_id: str
    agent_type: str = Field(pattern="^(research|code|data_analysis|writing)$")
    prompt: str = Field(min_length=1)
    workspace_dir: str


class RunEvent(BaseModel):
    type: str   # 'token' | 'status' | 'error'
    data: str
```

- [ ] **Step 3: Create `EvoScientist/pm/runner/agent_runner.py`**

```python
"""Asyncio task registry for EvoScientist agent runs with queue-based SSE streaming."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# Per-run asyncio queues: run_id → Queue of {type, data} dicts
# None sentinel in the queue signals end of stream.
_run_queues: dict[str, asyncio.Queue[dict | None]] = {}
_run_tasks: dict[str, asyncio.Task] = {}

# Prompt prefixes guide the main agent to delegate to the correct sub-agent
AGENT_PROMPTS: dict[str, str] = {
    "research": (
        "Use the research-agent sub-agent to complete the following task. "
        "Return concise, actionable findings with sources.\n\nTask: "
    ),
    "code": (
        "Use the code-agent sub-agent to implement the following. "
        "Write clean, reproducible code with minimal dependencies.\n\nTask: "
    ),
    "data_analysis": (
        "Use the data-analysis-agent sub-agent to analyze and report on the following. "
        "Include statistics and produce publication-ready figures where appropriate.\n\nTask: "
    ),
    "writing": (
        "Use the writing-agent sub-agent to draft a paper-ready Markdown report for the following. "
        "Do not fabricate results or citations.\n\nTask: "
    ),
}


async def start_run(
    run_id: str, agent_type: str, prompt: str, workspace_dir: str
) -> None:
    """Start an agent run as a background asyncio task."""
    queue: asyncio.Queue[dict | None] = asyncio.Queue()
    _run_queues[run_id] = queue
    task = asyncio.create_task(
        _run_agent(run_id, agent_type, prompt, workspace_dir, queue)
    )
    _run_tasks[run_id] = task


async def _run_agent(
    run_id: str,
    agent_type: str,
    prompt: str,
    workspace_dir: str,
    queue: asyncio.Queue,
) -> None:
    """Execute the agent and push token/status events into the queue."""
    # Lazy import so runner can start without loading the full EvoScientist stack
    from langchain_core.messages import AIMessage, AIMessageChunk

    from EvoScientist.EvoScientist import create_cli_agent

    prefix = AGENT_PROMPTS.get(agent_type, "")
    full_prompt = f"{prefix}{prompt}"

    Path(workspace_dir).mkdir(parents=True, exist_ok=True)

    try:
        agent = create_cli_agent(workspace_dir=workspace_dir)

        async for chunk in agent.astream(
            {"messages": [{"role": "user", "content": full_prompt}]},
            config={"configurable": {"thread_id": run_id}},
            stream_mode=["messages", "updates"],
            subgraphs=True,
        ):
            if not isinstance(chunk, tuple) or len(chunk) != 3:
                continue
            _, mode_str, data = chunk
            if mode_str != "messages":
                continue
            msg = data[0] if isinstance(data, tuple) and len(data) >= 1 else None
            if msg is None:
                continue
            if not isinstance(msg, (AIMessage, AIMessageChunk)):
                continue

            raw = msg.content
            if isinstance(raw, str):
                text = raw
            elif isinstance(raw, list):
                text = "".join(
                    b.get("text", "") if isinstance(b, dict) else ""
                    for b in raw
                )
            else:
                text = ""

            # Skip empty chunks and tool-selector JSON
            if text and not text.lstrip().startswith('{"tools":'):
                await queue.put({"type": "token", "data": text})

        await queue.put({"type": "status", "data": "done"})

    except asyncio.CancelledError:
        await queue.put({"type": "status", "data": "cancelled"})
    except Exception as exc:
        logger.exception("Agent run %s failed", run_id)
        await queue.put({"type": "error", "data": str(exc)})
        await queue.put({"type": "status", "data": "failed"})
    finally:
        _run_tasks.pop(run_id, None)
        # Leave queue in _run_queues briefly so streaming client can drain it


async def stream_events(run_id: str) -> AsyncGenerator[dict, None]:
    """Yield events from the run queue until a terminal status event."""
    queue = _run_queues.get(run_id)
    if queue is None:
        yield {"type": "error", "data": "Run not found or already completed"}
        yield {"type": "status", "data": "failed"}
        return

    try:
        while True:
            event = await queue.get()
            yield event
            if event.get("type") == "status":
                break
    finally:
        _run_queues.pop(run_id, None)


async def cancel(run_id: str) -> bool:
    """Cancel an in-progress run. Returns True if a task was cancelled."""
    task = _run_tasks.pop(run_id, None)
    if task and not task.done():
        task.cancel()
        return True
    return False
```

- [ ] **Step 4: Verify Python syntax (no import errors)**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
uv run python -c "from EvoScientist.pm.runner.agent_runner import start_run, stream_events, cancel; print('OK')"
```

Expected output: `OK`

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/runner/__init__.py \
        EvoScientist/pm/runner/models.py \
        EvoScientist/pm/runner/agent_runner.py
git commit -m "feat(pm/runner): add runner package, models, and agent_runner with asyncio queue streaming"
```

---

## Task 4: Runner FastAPI app + routes

**Files:**
- Create: `EvoScientist/pm/runner/routes/__init__.py`
- Create: `EvoScientist/pm/runner/routes/runs.py`
- Create: `EvoScientist/pm/runner/main.py`
- Create: `tests/pm/test_runner_routes.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/pm/test_runner_routes.py
"""Tests for the runner service routes."""
from __future__ import annotations
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def runner_client():
    from EvoScientist.pm.runner.main import create_runner_app
    return TestClient(create_runner_app())


def test_start_run_returns_202(runner_client):
    with patch("EvoScientist.pm.runner.routes.runs.agent_runner.start_run", new=AsyncMock()):
        resp = runner_client.post("/runs", json={
            "run_id": "abc123",
            "agent_type": "research",
            "prompt": "Find protocols",
            "workspace_dir": "/tmp/test_workspace",
        })
    assert resp.status_code == 202
    assert resp.json() == {"run_id": "abc123"}


def test_start_run_invalid_agent_type(runner_client):
    resp = runner_client.post("/runs", json={
        "run_id": "abc123",
        "agent_type": "invalid",
        "prompt": "p",
        "workspace_dir": "/tmp",
    })
    assert resp.status_code == 422


def test_cancel_run_returns_204_when_found(runner_client):
    with patch("EvoScientist.pm.runner.routes.runs.agent_runner.cancel", new=AsyncMock(return_value=True)):
        resp = runner_client.delete("/runs/abc123")
    assert resp.status_code == 204


def test_cancel_run_returns_404_when_not_found(runner_client):
    with patch("EvoScientist.pm.runner.routes.runs.agent_runner.cancel", new=AsyncMock(return_value=False)):
        resp = runner_client.delete("/runs/missing")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/pm/test_runner_routes.py -v 2>&1 | tail -15
```

Expected: FAIL with `ImportError`

- [ ] **Step 3: Create `EvoScientist/pm/runner/routes/__init__.py`**

```python
"""Runner route package."""
```

- [ ] **Step 4: Create `EvoScientist/pm/runner/routes/runs.py`**

```python
"""Runner run endpoints: start, stream SSE, cancel."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from .. import agent_runner
from ..models import RunRequest

router = APIRouter()


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def start_run(body: RunRequest):
    """Accept a run request and launch the agent as a background asyncio task."""
    await agent_runner.start_run(
        body.run_id, body.agent_type, body.prompt, body.workspace_dir
    )
    return {"run_id": body.run_id}


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    """SSE stream of token and status events for a run."""
    async def event_gen():
        async for event in agent_runner.stream_events(run_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_run(run_id: str):
    """Cancel an in-progress run."""
    cancelled = await agent_runner.cancel(run_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Run not found or already complete")
```

- [ ] **Step 5: Create `EvoScientist/pm/runner/main.py`**

```python
"""FastAPI application factory for the EvoScientist runner service."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.runs import router as runs_router


def create_runner_app() -> FastAPI:
    """Create and configure the runner FastAPI app."""
    app = FastAPI(
        title="EvoScientist Runner",
        version="1.0.0",
        docs_url="/docs",
        redoc_url=None,
    )

    # Only allow PM backend (localhost) — runner is not browser-accessible
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:7860", "http://localhost:7860"],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(runs_router)
    return app
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/pm/test_runner_routes.py -v 2>&1 | tail -15
```

Expected: 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git add EvoScientist/pm/runner/routes/__init__.py \
        EvoScientist/pm/runner/routes/runs.py \
        EvoScientist/pm/runner/main.py \
        tests/pm/test_runner_routes.py
git commit -m "feat(pm/runner): add runner FastAPI app with SSE stream and cancel routes"
```

---

## Task 5: Frontend `api.ts` — Run interface + 4 new functions

**Files:**
- Modify: `EvoScientist/pm/frontend/src/api.ts`

- [ ] **Step 1: Add `Run` interface and 4 API functions to `api.ts`**

At the end of the `api` object (after `addComment`), before the closing `}`, add:

```typescript
  createRun: (projectId: string, taskId: string, data: { agent_type: string; prompt: string }) =>
    request<Run>('POST', `/projects/${projectId}/tasks/${taskId}/runs`, data),
  listRuns: (projectId: string, taskId: string) =>
    request<Run[]>('GET', `/projects/${projectId}/tasks/${taskId}/runs`),
  cancelRun: (runId: string) =>
    request<void>('DELETE', `/runs/${runId}`),
  streamRunUrl: (runId: string): string => `/api/v1/runs/${runId}/stream`,
```

After the existing `Comment` interface at the bottom of the file, add:

```typescript
export interface Run {
  id: string
  task_id: string
  project_id: string
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

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd EvoScientist/pm/frontend && npx tsc --noEmit 2>&1
```

Expected: no output (zero errors)

- [ ] **Step 3: Commit**

```bash
git add EvoScientist/pm/frontend/src/api.ts
git commit -m "feat(pm/frontend): add Run interface and createRun/listRuns/cancelRun/streamRunUrl to api"
```

---

## Task 6: `useRunStream` hook

**Files:**
- Create: `EvoScientist/pm/frontend/src/hooks/useRunStream.ts`
- Create: `EvoScientist/pm/frontend/src/hooks/__tests__/useRunStream.test.ts`

- [ ] **Step 1: Write failing tests**

```typescript
// EvoScientist/pm/frontend/src/hooks/__tests__/useRunStream.test.ts
import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useRunStream } from '../useRunStream'

describe('useRunStream', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    // Mock sessionStorage
    Object.defineProperty(window, 'sessionStorage', {
      value: { getItem: vi.fn(() => 'test-token') },
      writable: true,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('starts with idle state when runId is null', () => {
    const { result } = renderHook(() => useRunStream(null))
    expect(result.current.output).toBe('')
    expect(result.current.isStreaming).toBe(false)
  })

  it('accumulates token events into output', async () => {
    const mockReader = {
      read: vi.fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode('data: {"type":"token","data":"Hello "}\n\n') })
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode('data: {"type":"token","data":"world"}\n\n') })
        .mockResolvedValueOnce({ done: true, value: undefined }),
    }
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => mockReader },
    })
    vi.stubGlobal('fetch', mockFetch)

    const { result } = renderHook(() => useRunStream('run123'))

    await act(async () => {
      await vi.runAllTimersAsync()
    })

    expect(result.current.output).toContain('Hello ')
    expect(result.current.output).toContain('world')
  })

  it('sets isStreaming false when done event received', async () => {
    const mockReader = {
      read: vi.fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode('data: {"type":"status","data":"done"}\n\n') })
        .mockResolvedValueOnce({ done: true, value: undefined }),
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      body: { getReader: () => mockReader },
    }))

    const { result } = renderHook(() => useRunStream('run123'))

    await act(async () => {
      await vi.runAllTimersAsync()
    })

    expect(result.current.isStreaming).toBe(false)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/hooks/__tests__/useRunStream.test.ts --reporter=verbose 2>&1 | tail -15
```

Expected: FAIL with `Cannot find module`

- [ ] **Step 3: Create `EvoScientist/pm/frontend/src/hooks/useRunStream.ts`**

```typescript
import { useEffect, useRef, useState } from 'react'

export type RunStreamStatus = 'idle' | 'streaming' | 'done' | 'failed' | 'cancelled'

export interface RunStreamState {
  output: string
  isStreaming: boolean
  streamStatus: RunStreamStatus
}

/**
 * Streams SSE output for a run using fetch+ReadableStream (supports auth headers).
 * Resets state whenever runId changes.
 */
export function useRunStream(runId: string | null): RunStreamState {
  const [output, setOutput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamStatus, setStreamStatus] = useState<RunStreamStatus>('idle')
  const controllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    setOutput('')
    setIsStreaming(false)
    setStreamStatus('idle')

    if (!runId) return

    const controller = new AbortController()
    controllerRef.current = controller
    setIsStreaming(true)
    setStreamStatus('streaming')

    async function stream() {
      const token = sessionStorage.getItem('pm_token')
      let response: Response

      try {
        response = await fetch(`/api/v1/runs/${runId}/stream`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: controller.signal,
        })
      } catch {
        if (!controller.signal.aborted) {
          setIsStreaming(false)
          setStreamStatus('failed')
        }
        return
      }

      const reader = response.body?.getReader()
      if (!reader) { setIsStreaming(false); setStreamStatus('failed'); return }

      const decoder = new TextDecoder()
      let buffer = ''

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const event = JSON.parse(line.slice(6)) as { type: string; data: string }
              if (event.type === 'token') {
                setOutput(prev => prev + event.data)
              } else if (event.type === 'status') {
                const s = event.data as RunStreamStatus
                setStreamStatus(s)
                setIsStreaming(false)
              } else if (event.type === 'error') {
                setStreamStatus('failed')
                setIsStreaming(false)
              }
            } catch { /* malformed SSE line — ignore */ }
          }
        }
      } catch {
        if (!controller.signal.aborted) {
          setIsStreaming(false)
          setStreamStatus('failed')
        }
      }
    }

    stream()

    return () => {
      controller.abort()
      controllerRef.current = null
    }
  }, [runId])

  return { output, isStreaming, streamStatus }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/hooks/__tests__/useRunStream.test.ts --reporter=verbose 2>&1 | tail -15
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/hooks/useRunStream.ts \
        EvoScientist/pm/frontend/src/hooks/__tests__/useRunStream.test.ts
git commit -m "feat(pm/frontend): add useRunStream hook with fetch-based SSE streaming"
```

---

## Task 7: `AiRunsTab` component

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/AiRunsTab.tsx`
- Create: `EvoScientist/pm/frontend/src/components/__tests__/AiRunsTab.test.tsx`

- [ ] **Step 1: Write failing tests**

```typescript
// EvoScientist/pm/frontend/src/components/__tests__/AiRunsTab.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AiRunsTab } from '../AiRunsTab'
import type { Task } from '../../api'

vi.mock('../../api', () => ({
  api: {
    listRuns: vi.fn().mockResolvedValue([]),
    createRun: vi.fn().mockResolvedValue({ id: 'r1', status: 'pending', agent_type: 'research', prompt: 'p', task_id: 't1', project_id: 'p1', output: null, error: null, started_at: null, finished_at: null, created_by: 'u1', created_at: '2026-01-01' }),
    cancelRun: vi.fn().mockResolvedValue(undefined),
  },
}))

vi.mock('../../hooks/useRunStream', () => ({
  useRunStream: vi.fn(() => ({ output: '', isStreaming: false, streamStatus: 'idle' })),
}))

const MOCK_TASK: Task = {
  id: 't1', project_id: 'p1', title: 'Gel electrophoresis',
  description: 'Run gel for CRISPR verification',
  assignee_id: null, status: 'todo', priority: 'medium',
  deadline: null, session_id: null, created_by: 'u1',
  created_at: '2026-01-01', updated_at: '2026-01-01',
}

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

describe('AiRunsTab', () => {
  it('renders all 4 agent buttons', () => {
    render(wrap(<AiRunsTab task={MOCK_TASK} projectId="p1" />))
    expect(screen.getByText(/Research/i)).toBeInTheDocument()
    expect(screen.getByText(/Code/i)).toBeInTheDocument()
    expect(screen.getByText(/Analysis/i)).toBeInTheDocument()
    expect(screen.getByText(/Writing/i)).toBeInTheDocument()
  })

  it('pre-fills prompt from task title and description', () => {
    render(wrap(<AiRunsTab task={MOCK_TASK} projectId="p1" />))
    const textarea = screen.getByRole('textbox')
    expect((textarea as HTMLTextAreaElement).value).toContain('Gel electrophoresis')
  })

  it('RUN button is enabled when Research is selected and prompt is non-empty', () => {
    render(wrap(<AiRunsTab task={MOCK_TASK} projectId="p1" />))
    const btn = screen.getByRole('button', { name: /RUN EVOSCIENTIST/i })
    expect(btn).not.toBeDisabled()
  })

  it('shows NO PREVIOUS RUNS when run list is empty', async () => {
    render(wrap(<AiRunsTab task={MOCK_TASK} projectId="p1" />))
    await waitFor(() =>
      expect(screen.getByText(/NO PREVIOUS RUNS/i)).toBeInTheDocument()
    )
  })

  it('shows run history when runs exist', async () => {
    const { api } = await import('../../api')
    vi.mocked(api.listRuns).mockResolvedValue([{
      id: 'r1', task_id: 't1', project_id: 'p1',
      agent_type: 'research', prompt: 'p', status: 'done',
      output: 'Protocol found.', error: null,
      started_at: '2026-01-01T00:00:00Z', finished_at: '2026-01-01T00:01:00Z',
      created_by: 'u1', created_at: '2026-01-01T00:00:00Z',
    }])
    render(wrap(<AiRunsTab task={MOCK_TASK} projectId="p1" />))
    await waitFor(() => expect(screen.getByText(/RESEARCH/i)).toBeInTheDocument())
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/__tests__/AiRunsTab.test.tsx --reporter=verbose 2>&1 | tail -15
```

Expected: FAIL with `Cannot find module`

- [ ] **Step 3: Create `EvoScientist/pm/frontend/src/components/AiRunsTab.tsx`**

```tsx
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Run, Task } from '../api'
import { useRunStream } from '../hooks/useRunStream'

const AGENTS: { key: 'research' | 'code' | 'data_analysis' | 'writing'; label: string; icon: string; desc: string }[] = [
  { key: 'research',      label: 'Research',  icon: '🔬', desc: 'Find protocols & methods' },
  { key: 'code',          label: 'Code',      icon: '⚙',  desc: 'Implement scripts' },
  { key: 'data_analysis', label: 'Analysis',  icon: '📊', desc: 'Metrics & plots' },
  { key: 'writing',       label: 'Writing',   icon: '✍',  desc: 'Draft report' },
]

const STATUS_COLORS: Record<string, string> = {
  done: '#10b981', failed: '#f43f5e', cancelled: '#64748b',
  running: '#22d3ee', pending: '#f59e0b',
}

interface Props { task: Task; projectId: string }

export function AiRunsTab({ task, projectId }: Props) {
  const qc = useQueryClient()
  const defaultPrompt = [task.title, task.description].filter(Boolean).join('. ')

  const [selectedAgent, setSelectedAgent] = useState<'research' | 'code' | 'data_analysis' | 'writing'>('research')
  const [prompt, setPrompt] = useState(defaultPrompt)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null)

  const { output: streamOutput, isStreaming, streamStatus } = useRunStream(activeRunId)

  const { data: runs = [] } = useQuery({
    queryKey: ['runs', task.id],
    queryFn: () => api.listRuns(projectId, task.id),
  })

  const createRunMutation = useMutation({
    mutationFn: () => api.createRun(projectId, task.id, { agent_type: selectedAgent, prompt }),
    onSuccess: (run) => {
      setActiveRunId(run.id)
      qc.invalidateQueries({ queryKey: ['runs', task.id] })
    },
  })

  const cancelMutation = useMutation({
    mutationFn: (runId: string) => api.cancelRun(runId),
    onSuccess: () => {
      setActiveRunId(null)
      qc.invalidateQueries({ queryKey: ['runs', task.id] })
    },
  })

  // When streaming completes, clear activeRunId and refresh list
  if (activeRunId && !isStreaming && streamStatus !== 'idle' && streamStatus !== 'streaming') {
    setActiveRunId(null)
    qc.invalidateQueries({ queryKey: ['runs', task.id] })
  }

  const hasHistory = runs.length > 0
  const isRunning = isStreaming || createRunMutation.isPending

  const handleAddToNotes = (run: Run) => {
    if (!run.output) return
    const body = `**[${run.agent_type.toUpperCase()} Run · ${run.created_at.slice(0, 10)}]**\n\n${run.output}`
    api.addComment(projectId, task.id, body).then(() =>
      qc.invalidateQueries({ queryKey: ['comments', task.id] })
    )
  }

  return (
    <div style={{ padding: '10px 8px', background: '#0a1220', height: '100%', overflowY: 'auto' }}>
      {/* Agent picker */}
      <div style={{ fontSize: 7, color: '#334155', letterSpacing: '0.1em', fontWeight: 700, marginBottom: 6 }}>
        SELECT AGENT
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4, marginBottom: 10 }}>
        {AGENTS.map(a => (
          <button
            key={a.key}
            onClick={() => setSelectedAgent(a.key)}
            style={{
              background: selectedAgent === a.key ? 'rgba(34,211,238,0.08)' : 'rgba(100,140,200,0.04)',
              border: selectedAgent === a.key ? '1px solid rgba(34,211,238,0.28)' : '1px solid rgba(100,140,200,0.1)',
              borderRadius: 3, padding: '5px 6px', textAlign: 'left', cursor: 'pointer',
            }}
          >
            <div style={{ fontSize: 9, color: selectedAgent === a.key ? '#22d3ee' : '#64748b', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
              {a.icon} {a.label}
            </div>
            <div style={{ fontSize: 7, color: '#334155', marginTop: 1 }}>{a.desc}</div>
          </button>
        ))}
      </div>

      {/* Prompt */}
      <div style={{ fontSize: 7, color: '#334155', letterSpacing: '0.1em', fontWeight: 700, marginBottom: 4 }}>
        PROMPT
      </div>
      <textarea
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        rows={3}
        disabled={isRunning}
        placeholder="Describe what the agent should do…"
        style={{
          width: '100%', boxSizing: 'border-box', background: '#070b12', border: '1px solid rgba(34,211,238,0.18)',
          borderRadius: 3, color: '#94a3b8', fontSize: 9, padding: '5px 6px', resize: 'none',
          fontFamily: 'var(--font-sans)', marginBottom: 6, opacity: isRunning ? 0.5 : 1,
        }}
      />

      {/* Run / Run Again button */}
      <button
        onClick={() => createRunMutation.mutate()}
        disabled={isRunning || !prompt.trim()}
        style={{
          width: '100%', background: 'rgba(34,211,238,0.1)', border: '1px solid rgba(34,211,238,0.28)',
          borderRadius: 3, padding: '6px 0', color: '#22d3ee', fontSize: 9, fontWeight: 700,
          fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', cursor: 'pointer',
          marginBottom: 10, opacity: (isRunning || !prompt.trim()) ? 0.4 : 1,
        }}
      >
        {hasHistory ? '▶ RUN AGAIN' : '▶ RUN EVOSCIENTIST'}
      </button>

      {/* Active run (streaming) */}
      {activeRunId && (
        <div style={{ border: '1px solid rgba(34,211,238,0.2)', borderRadius: 4, overflow: 'hidden', marginBottom: 8 }}>
          <div style={{ background: 'rgba(34,211,238,0.06)', padding: '5px 8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 6, height: 6, background: '#22d3ee', borderRadius: '50%' }} />
              <span style={{ fontSize: 8, color: '#22d3ee', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                {selectedAgent.toUpperCase()} · RUNNING
              </span>
            </div>
            <button
              onClick={() => cancelMutation.mutate(activeRunId)}
              style={{ background: 'rgba(244,63,94,0.08)', border: '1px solid rgba(244,63,94,0.2)', borderRadius: 2, padding: '1px 6px', color: '#f43f5e', fontSize: 8, cursor: 'pointer', fontFamily: 'var(--font-mono)' }}
            >
              ■ STOP
            </button>
          </div>
          <div style={{ padding: '6px 8px', background: '#050810', minHeight: 60, maxHeight: 120, overflowY: 'auto' }}>
            <pre style={{ fontSize: 8, color: '#64748b', fontFamily: 'var(--font-mono)', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.6 }}>
              {streamOutput || '…'}
              {isStreaming && <span style={{ color: '#22d3ee' }}>▋</span>}
            </pre>
          </div>
        </div>
      )}

      {/* Run history */}
      {runs.length === 0 && !activeRunId ? (
        <div style={{ fontSize: 8, color: '#1e2d3d', textAlign: 'center', marginTop: 8, fontFamily: 'var(--font-mono)' }}>
          NO PREVIOUS RUNS
        </div>
      ) : (
        <>
          <div style={{ fontSize: 7, color: '#334155', letterSpacing: '0.1em', fontWeight: 700, marginBottom: 4 }}>
            RUN HISTORY · {runs.length} {runs.length === 1 ? 'RUN' : 'RUNS'}
          </div>
          {runs.map(run => (
            <RunCard
              key={run.id}
              run={run}
              expanded={expandedRunId === run.id}
              onToggle={() => setExpandedRunId(expandedRunId === run.id ? null : run.id)}
              onAddToNotes={handleAddToNotes}
            />
          ))}
        </>
      )}
    </div>
  )
}

function RunCard({ run, expanded, onToggle, onAddToNotes }: {
  run: Run; expanded: boolean
  onToggle: () => void; onAddToNotes: (r: Run) => void
}) {
  const color = STATUS_COLORS[run.status] ?? '#64748b'
  const duration = run.started_at && run.finished_at
    ? `${Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000)}s`
    : null

  return (
    <div style={{ border: `1px solid ${color}22`, borderRadius: 4, overflow: 'hidden', marginBottom: 4 }}>
      <button
        onClick={onToggle}
        style={{ width: '100%', background: `${color}0a`, padding: '5px 8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', border: 'none', cursor: 'pointer' }}
      >
        <div>
          <span style={{ fontSize: 8, color, fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
            {run.status === 'done' ? '✓' : run.status === 'failed' ? '✗' : '◌'} {run.agent_type.toUpperCase()}
          </span>
          <span style={{ fontSize: 7, color: '#334155', marginLeft: 6 }}>
            {run.created_at.slice(0, 10)}{duration ? ` · ${duration}` : ''}
          </span>
        </div>
        <span style={{ fontSize: 9, color: '#475569' }}>{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div style={{ padding: '6px 8px', background: '#070b12' }}>
          {run.output ? (
            <pre style={{ fontSize: 8, color: '#94a3b8', fontFamily: 'var(--font-mono)', margin: '0 0 6px', whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.5, maxHeight: 120, overflowY: 'auto' }}>
              {run.output}
            </pre>
          ) : run.error ? (
            <div style={{ fontSize: 8, color: '#f43f5e', marginBottom: 6 }}>{run.error}</div>
          ) : null}
          {run.output && (
            <div style={{ display: 'flex', gap: 4 }}>
              <button
                onClick={() => navigator.clipboard.writeText(run.output!)}
                style={{ background: 'rgba(34,211,238,0.06)', border: '1px solid rgba(34,211,238,0.15)', borderRadius: 2, padding: '2px 6px', fontSize: 7, color: '#22d3ee', cursor: 'pointer', fontFamily: 'var(--font-mono)' }}
              >
                📋 Copy
              </button>
              <button
                onClick={() => onAddToNotes(run)}
                style={{ background: 'rgba(34,211,238,0.06)', border: '1px solid rgba(34,211,238,0.15)', borderRadius: 2, padding: '2px 6px', fontSize: 7, color: '#22d3ee', cursor: 'pointer', fontFamily: 'var(--font-mono)' }}
              >
                💬 Add to Notes
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/components/__tests__/AiRunsTab.test.tsx --reporter=verbose 2>&1 | tail -15
```

Expected: 5 tests PASS

- [ ] **Step 5: Run full frontend test suite to check no regressions**

```bash
npx vitest run --reporter=verbose 2>&1 | tail -10
```

Expected: all existing tests PASS + 5 new tests

- [ ] **Step 6: Commit**

```bash
git add EvoScientist/pm/frontend/src/components/AiRunsTab.tsx \
        EvoScientist/pm/frontend/src/components/__tests__/AiRunsTab.test.tsx
git commit -m "feat(pm/frontend): add AiRunsTab component with agent picker, prompt, streaming output, and run history cards"
```

---

## Task 8: `TaskDetail` tab integration

**Files:**
- Modify: `EvoScientist/pm/frontend/src/pages/TaskDetail.tsx`
- Modify: `EvoScientist/pm/frontend/src/pages/__tests__/TaskDetail.test.tsx`

- [ ] **Step 1: Write failing tests (add to existing `TaskDetail.test.tsx`)**

Read the current test file to find where to add. Then add these two tests at the end of the existing describe block:

```typescript
it('renders DETAILS and AI RUNS tabs', () => {
  render(<TaskDetail task={MOCK_TASK} projectId="p1" onClose={() => {}} members={[]} />)
  expect(screen.getByRole('button', { name: /DETAILS/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /AI RUNS/i })).toBeInTheDocument()
})

it('shows AiRunsTab when AI RUNS tab is clicked', () => {
  render(<TaskDetail task={MOCK_TASK} projectId="p1" onClose={() => {}} members={[]} />)
  fireEvent.click(screen.getByRole('button', { name: /AI RUNS/i }))
  // AiRunsTab renders the agent buttons
  expect(screen.getByText(/Research/i)).toBeInTheDocument()
})
```

Also add the `AiRunsTab` mock at the top of the test file (with existing vi.mock calls):

```typescript
vi.mock('../components/AiRunsTab', () => ({
  AiRunsTab: ({ task }: { task: { title: string } }) => (
    <div data-testid="ai-runs-tab">
      <span>Research</span>
      <span>AI tab for {task.title}</span>
    </div>
  ),
}))
```

- [ ] **Step 2: Run tests to verify new ones fail**

```bash
cd EvoScientist/pm/frontend && npx vitest run src/pages/__tests__/TaskDetail.test.tsx --reporter=verbose 2>&1 | tail -15
```

Expected: existing tests PASS, new ones FAIL

- [ ] **Step 3: Add tab toggle to `TaskDetail.tsx`**

Read the current `TaskDetail.tsx`. Then make these targeted changes:

Add the import at the top (with other component imports):
```tsx
import { AiRunsTab } from '../components/AiRunsTab'
```

Add state in the component (with other `useState` declarations):
```tsx
const [activeTab, setActiveTab] = useState<'details' | 'ai'>('details')
```

Replace the header section that shows the task title to include the tab bar. Find the area just below the task title where the EDIT button or status badge lives, and add the tab row immediately after the title:

```tsx
{/* Tab bar */}
<div style={{ display: 'flex', borderBottom: '1px solid rgba(100,140,200,0.12)', marginBottom: 8 }}>
  <button
    onClick={() => setActiveTab('details')}
    style={{
      padding: '4px 10px', fontSize: 9, fontFamily: 'var(--font-mono)',
      color: activeTab === 'details' ? '#22d3ee' : '#475569',
      borderBottom: activeTab === 'details' ? '2px solid #22d3ee' : '2px solid transparent',
      background: 'none', border: 'none', borderBottomStyle: 'solid',
      borderBottomWidth: 2, borderBottomColor: activeTab === 'details' ? '#22d3ee' : 'transparent',
      cursor: 'pointer', fontWeight: activeTab === 'details' ? 700 : 400,
    }}
  >
    DETAILS
  </button>
  <button
    onClick={() => setActiveTab('ai')}
    style={{
      padding: '4px 10px', fontSize: 9, fontFamily: 'var(--font-mono)',
      color: activeTab === 'ai' ? '#22d3ee' : '#475569',
      background: 'none', border: 'none', borderBottomStyle: 'solid',
      borderBottomWidth: 2, borderBottomColor: activeTab === 'ai' ? '#22d3ee' : 'transparent',
      cursor: 'pointer', fontWeight: activeTab === 'ai' ? 700 : 400,
    }}
  >
    ⬡ AI RUNS
  </button>
</div>
```

Wrap the existing task fields (status, priority, description, assignee, deadline, comments) in a conditional:
```tsx
{activeTab === 'details' ? (
  <> {/* existing detail fields */ } </>
) : (
  <AiRunsTab task={task} projectId={projectId} />
)}
```

**Note:** Read the full current TaskDetail.tsx to find the exact location of the detail fields section before making this edit.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd EvoScientist/pm/frontend && npx vitest run --reporter=verbose 2>&1 | tail -12
```

Expected: all tests PASS including 2 new tab tests

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/frontend/src/pages/TaskDetail.tsx \
        EvoScientist/pm/frontend/src/pages/__tests__/TaskDetail.test.tsx
git commit -m "feat(pm/frontend): add DETAILS / AI RUNS tab toggle in TaskDetail"
```

---

## Task 9: `dashboard` CLI — co-start runner service

**Files:**
- Modify: `EvoScientist/cli/_app.py`

No test file — the dashboard command is an integration test (manual).

- [ ] **Step 1: Read `EvoScientist/cli/_app.py`** to see current `dashboard` command (lines 57–79)

- [ ] **Step 2: Update `dashboard` command to co-start runner**

Replace the entire `dashboard` function with:

```python
@app.command()
def dashboard(
    port: int = typer.Option(7860, "--port", help="Port to run the PM server on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind the PM server to"),
    runner_port: int = typer.Option(8001, "--runner-port", help="Port for the runner service"),
    open: bool = typer.Option(True, "--open/--no-open", help="Open browser after starting"),
) -> None:
    """Start the project management dashboard (+ EvoScientist runner service)."""
    import os
    import threading

    import uvicorn

    from EvoScientist.pm.api.app import create_app
    from EvoScientist.pm.runner.main import create_runner_app

    # Start runner service in a background daemon thread
    runner_server = uvicorn.Server(
        uvicorn.Config(
            create_runner_app(),
            host="127.0.0.1",
            port=runner_port,
            log_level="error",
        )
    )

    def _start_runner() -> None:
        import asyncio
        asyncio.run(runner_server.serve())

    runner_thread = threading.Thread(target=_start_runner, daemon=True)
    runner_thread.start()

    # Tell PM backend where the runner lives
    os.environ["RUNNER_URL"] = f"http://127.0.0.1:{runner_port}"

    if open:
        import time
        import webbrowser

        def _open_browser() -> None:
            time.sleep(1.5)
            webbrowser.open(f"http://{host}:{port}")

        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(create_app(), host=host, port=port, log_level="info")
```

- [ ] **Step 3: Verify no syntax errors**

```bash
cd /Users/akaplan/Documents/Academic_Research/EvoScientist
uv run python -c "from EvoScientist.cli._app import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run full backend test suite to confirm no regressions**

```bash
uv run pytest tests/pm/ -v --timeout=30 2>&1 | tail -20
```

Expected: all tests PASS (59 existing + new runs/runner tests)

- [ ] **Step 5: Run full frontend test suite + TypeScript + build**

```bash
cd EvoScientist/pm/frontend && npx vitest run 2>&1 | tail -5 && npx tsc --noEmit && npx vite build 2>&1 | tail -5
```

Expected: all tests PASS, zero TypeScript errors, build succeeds

- [ ] **Step 6: Commit**

```bash
git add EvoScientist/cli/_app.py
git commit -m "feat(pm): co-start runner service in dashboard command"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| Separate runner microservice | Tasks 3, 4 |
| `runs` table in SQLite | Task 1 |
| `POST /projects/{pid}/tasks/{tid}/runs` | Task 2 |
| `GET .../runs` list | Task 2 |
| `GET /runs/{id}/stream` SSE proxy | Task 2 |
| `DELETE /runs/{id}` cancel | Task 2 |
| Runner: `POST /runs`, `GET /runs/{id}/stream`, `DELETE /runs/{id}` | Task 4 |
| `task.session_id` updated with run_id | Task 2 (in create_new_run) |
| Frontend `api.ts` functions | Task 5 |
| `useRunStream` hook | Task 6 |
| `AiRunsTab` component: agents, prompt, streaming, history | Task 7 |
| Collapsible result cards + Copy + Add to Notes | Task 7 |
| DETAILS / AI RUNS tabs in TaskDetail | Task 8 |
| Workspace isolation per project+task | Task 2 (workspace_dir calculation) |
| `EvoSci dashboard` starts runner | Task 9 |
| Already-complete runs stream saved output | Task 2 (stream_run_output) |

All spec requirements covered.

**Placeholder scan:** No TBD/TODO items. All code blocks are complete.

**Type consistency:**
- `Run` dataclass (Task 1) → `RunResponse` schema (Task 2) → `Run` TS interface (Task 5) — all fields match
- `_notify_runner(run_id, agent_type, prompt, workspace_dir)` called in Task 2, defined in same file ✅
- `agent_runner.start_run(run_id, agent_type, prompt, workspace_dir)` called in Task 4, defined in Task 3 ✅
- `api.listRuns(projectId, taskId)` in AiRunsTab (Task 7) matches Task 5 signature ✅
- `api.addComment(projectId, taskId, body)` used in AiRunsTab — already exists in `api.ts` ✅
