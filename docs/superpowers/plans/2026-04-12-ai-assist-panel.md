# AI Writing Assistant Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an AI writing assistant side panel to the PM experiment view that lets researchers generate hypothesis, protocol, and entry body text using a streaming `writing` agent with full experiment context.

**Architecture:** New `experiment_assists` table + CRUD + 4 API routes mirror the existing `runs` subsystem. The panel dispatches to the same runner service (`writing` agent) and streams tokens via SSE. Two new frontend files (`AiAssistPanel.tsx`, `useAssistStream.ts`) plus minor additions to `api.ts` and `ExperimentDetail.tsx`.

**Tech Stack:** Python/FastAPI (backend), SQLite (storage), httpx (runner proxy), React 18 + TypeScript (frontend), TanStack Query v5, Fetch API SSE streaming.

**Spec:** `docs/superpowers/specs/2026-04-12-ai-assist-panel-design.md`

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Modify | `EvoScientist/pm/db.py` | Add `experiment_assists` table + index |
| Modify | `EvoScientist/pm/models.py` | Add `ExperimentAssist` dataclass |
| Create | `EvoScientist/pm/crud/assists.py` | create / get / list / update_status / update_output |
| Modify | `EvoScientist/pm/api/schemas.py` | Add `AssistCreate`, `AssistResponse` |
| Create | `EvoScientist/pm/api/routes/assists.py` | 4 REST endpoints + SSE proxy |
| Modify | `EvoScientist/pm/api/app.py` | Register assists routers |
| Modify | `EvoScientist/pm/frontend/src/api.ts` | Add `Assist` type + 4 API methods |
| Create | `EvoScientist/pm/frontend/src/hooks/useAssistStream.ts` | SSE hook for assist streaming |
| Create | `EvoScientist/pm/frontend/src/components/AiAssistPanel.tsx` | Side panel component |
| Modify | `EvoScientist/pm/frontend/src/components/ExperimentDetail.tsx` | Add ✦ AI button + panel |
| Create | `tests/pm/test_assist_crud.py` | CRUD unit tests |
| Create | `tests/pm/test_assist_routes.py` | API integration tests |

---

## Task 1: DB Schema + Dataclass

**Files:**
- Modify: `EvoScientist/pm/db.py`
- Modify: `EvoScientist/pm/models.py`
- Test: `tests/pm/test_db.py` (update existing table count)

- [ ] **Step 1: Add `experiment_assists` table to `_SCHEMA` in `db.py`**

  Open `EvoScientist/pm/db.py`. Find the closing `"""` of `_SCHEMA` (after `experiment_entries` table). Insert before it:

  ```sql

  CREATE TABLE IF NOT EXISTS experiment_assists (
      id             TEXT PRIMARY KEY,
      experiment_id  TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
      project_id     TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      prompt         TEXT NOT NULL,
      context_json   TEXT NOT NULL DEFAULT '{}',
      status         TEXT NOT NULL DEFAULT 'pending'
                     CHECK(status IN ('pending','running','done','failed','cancelled')),
      output         TEXT,
      error          TEXT,
      target_field   TEXT,
      created_by     TEXT NOT NULL REFERENCES users(id),
      created_at     TEXT NOT NULL,
      finished_at    TEXT
  );

  CREATE INDEX IF NOT EXISTS idx_experiment_assists_exp
      ON experiment_assists(experiment_id);
  ```

- [ ] **Step 2: Add `ExperimentAssist` dataclass to `models.py`**

  Open `EvoScientist/pm/models.py`. Append at the end:

  ```python


  @dataclass
  class ExperimentAssist:
      id: str
      experiment_id: str
      project_id: str
      prompt: str
      context_json: str
      status: str          # 'pending'|'running'|'done'|'failed'|'cancelled'
      created_by: str
      created_at: str
      output: str | None = None
      error: str | None = None
      target_field: str | None = None   # 'hypothesis'|'protocol'|'entry_body'|None
      finished_at: str | None = None
  ```

- [ ] **Step 3: Verify syntax**

  ```bash
  cd /path/to/worktree
  python3 -c "import ast; ast.parse(open('EvoScientist/pm/db.py').read()); print('db OK')"
  python3 -c "import ast; ast.parse(open('EvoScientist/pm/models.py').read()); print('models OK')"
  ```

  Expected: `db OK` and `models OK`

- [ ] **Step 4: Update existing DB test to expect 12 tables**

  Open `tests/pm/test_db.py`. Find any assertion that checks the table count. Update the expected count from `11` to `12`. Also add `'experiment_assists'` to any set of expected table names.

- [ ] **Step 5: Run DB tests**

  ```bash
  uv run pytest tests/pm/test_db.py -v --timeout=30
  ```

  Expected: all pass.

- [ ] **Step 6: Commit**

  ```bash
  git add EvoScientist/pm/db.py EvoScientist/pm/models.py tests/pm/test_db.py
  git commit -m "feat(pm): add experiment_assists table and ExperimentAssist dataclass"
  ```

---

## Task 2: CRUD Layer

**Files:**
- Create: `EvoScientist/pm/crud/assists.py`
- Create: `tests/pm/test_assist_crud.py`

- [ ] **Step 1: Write the failing tests first**

  Create `tests/pm/test_assist_crud.py`:

  ```python
  """Tests for ExperimentAssist CRUD operations."""
  from __future__ import annotations

  from pathlib import Path

  import pytest

  from EvoScientist.pm.crud.assists import (
      create_assist,
      get_assist,
      list_assists_for_experiment,
      update_assist_output,
      update_assist_status,
  )
  from EvoScientist.pm.db import create_schema


  @pytest.fixture
  def db_path(tmp_path: Path) -> Path:
      path = tmp_path / "test.db"
      create_schema(path)
      import sqlite3
      conn = sqlite3.connect(path)
      conn.execute("PRAGMA foreign_keys = ON")
      now = "2024-01-01T00:00:00"
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
          """INSERT INTO experiments (id, project_id, name, status, tags,
             created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
          ("e1", "p1", "Exp 1", "planned", "[]", "u1", now, now),
      )
      conn.commit()
      conn.close()
      return path


  def test_create_assist(db_path):
      a = create_assist(db_path, experiment_id="e1", project_id="p1",
                        prompt="Write a hypothesis", context_json='{"name":"Exp 1"}',
                        target_field="hypothesis", created_by="u1")
      assert a.id
      assert a.experiment_id == "e1"
      assert a.project_id == "p1"
      assert a.prompt == "Write a hypothesis"
      assert a.status == "pending"
      assert a.target_field == "hypothesis"
      assert a.output is None


  def test_get_assist(db_path):
      a = create_assist(db_path, "e1", "p1", "p", "{}", None, "u1")
      fetched = get_assist(db_path, a.id)
      assert fetched is not None
      assert fetched.id == a.id


  def test_get_assist_not_found(db_path):
      assert get_assist(db_path, "nonexistent") is None


  def test_list_assists_for_experiment(db_path):
      create_assist(db_path, "e1", "p1", "p1", "{}", None, "u1")
      create_assist(db_path, "e1", "p1", "p2", "{}", None, "u1")
      results = list_assists_for_experiment(db_path, "e1")
      assert len(results) == 2
      # newest first
      assert results[0].created_at >= results[1].created_at


  def test_update_assist_status(db_path):
      a = create_assist(db_path, "e1", "p1", "p", "{}", None, "u1")
      update_assist_status(db_path, a.id, "running")
      fetched = get_assist(db_path, a.id)
      assert fetched.status == "running"


  def test_update_assist_output(db_path):
      a = create_assist(db_path, "e1", "p1", "p", "{}", None, "u1")
      update_assist_output(db_path, a.id, "done", "Generated text")
      fetched = get_assist(db_path, a.id)
      assert fetched.status == "done"
      assert fetched.output == "Generated text"
      assert fetched.finished_at is not None


  def test_cascade_delete(db_path):
      """Deleting experiment should cascade-delete its assists."""
      a = create_assist(db_path, "e1", "p1", "p", "{}", None, "u1")
      import sqlite3
      conn = sqlite3.connect(db_path)
      conn.execute("PRAGMA foreign_keys = ON")
      conn.execute("DELETE FROM experiments WHERE id = 'e1'")
      conn.commit()
      conn.close()
      assert get_assist(db_path, a.id) is None
  ```

- [ ] **Step 2: Run tests to verify they fail**

  ```bash
  uv run pytest tests/pm/test_assist_crud.py -v --timeout=30 2>&1 | head -20
  ```

  Expected: `ImportError` — `crud.assists` does not exist yet.

- [ ] **Step 3: Create `EvoScientist/pm/crud/assists.py`**

  ```python
  """CRUD operations for ExperimentAssist entities."""
  from __future__ import annotations

  import sqlite3
  import uuid
  from datetime import UTC, datetime
  from pathlib import Path

  from ..db import get_db
  from ..models import ExperimentAssist

  TERMINAL_STATUSES = frozenset({"done", "failed", "cancelled"})


  def _row_to_assist(row: sqlite3.Row) -> ExperimentAssist:
      return ExperimentAssist(
          id=row["id"],
          experiment_id=row["experiment_id"],
          project_id=row["project_id"],
          prompt=row["prompt"],
          context_json=row["context_json"],
          status=row["status"],
          output=row["output"],
          error=row["error"],
          target_field=row["target_field"],
          created_by=row["created_by"],
          created_at=row["created_at"],
          finished_at=row["finished_at"],
      )


  def create_assist(
      db_path: Path,
      experiment_id: str,
      project_id: str,
      prompt: str,
      context_json: str,
      target_field: str | None,
      created_by: str,
  ) -> ExperimentAssist:
      """Insert a new assist record with status 'pending' and return it."""
      assist_id = uuid.uuid4().hex
      now = datetime.now(UTC).isoformat()
      with get_db(db_path) as conn:
          conn.execute(
              """INSERT INTO experiment_assists
                 (id, experiment_id, project_id, prompt, context_json,
                  status, target_field, created_by, created_at)
                 VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
              (assist_id, experiment_id, project_id, prompt, context_json,
               target_field, created_by, now),
          )
      return ExperimentAssist(
          id=assist_id,
          experiment_id=experiment_id,
          project_id=project_id,
          prompt=prompt,
          context_json=context_json,
          status="pending",
          target_field=target_field,
          created_by=created_by,
          created_at=now,
      )


  def get_assist(db_path: Path, assist_id: str) -> ExperimentAssist | None:
      """Return ExperimentAssist by id, or None."""
      with get_db(db_path) as conn:
          row = conn.execute(
              "SELECT * FROM experiment_assists WHERE id = ?", (assist_id,)
          ).fetchone()
      return _row_to_assist(row) if row else None


  def list_assists_for_experiment(
      db_path: Path, experiment_id: str
  ) -> list[ExperimentAssist]:
      """Return all assists for an experiment, newest first."""
      with get_db(db_path) as conn:
          rows = conn.execute(
              """SELECT * FROM experiment_assists
                 WHERE experiment_id = ? ORDER BY created_at DESC""",
              (experiment_id,),
          ).fetchall()
      return [_row_to_assist(r) for r in rows]


  def update_assist_status(db_path: Path, assist_id: str, status: str) -> None:
      """Update assist status; sets finished_at when terminal."""
      now = datetime.now(UTC).isoformat()
      with get_db(db_path) as conn:
          if status == "running":
              conn.execute(
                  "UPDATE experiment_assists SET status = ? WHERE id = ?",
                  (status, assist_id),
              )
          elif status in TERMINAL_STATUSES:
              conn.execute(
                  "UPDATE experiment_assists SET status = ?, finished_at = ? WHERE id = ?",
                  (status, now, assist_id),
              )
          else:
              conn.execute(
                  "UPDATE experiment_assists SET status = ? WHERE id = ?",
                  (status, assist_id),
              )


  def update_assist_output(
      db_path: Path, assist_id: str, status: str, output: str, error: str | None = None
  ) -> None:
      """Save final output and terminal status."""
      now = datetime.now(UTC).isoformat()
      with get_db(db_path) as conn:
          conn.execute(
              """UPDATE experiment_assists
                 SET status = ?, output = ?, error = ?, finished_at = ?
                 WHERE id = ?""",
              (status, output, error, now, assist_id),
          )
  ```

- [ ] **Step 4: Run tests to verify they pass**

  ```bash
  uv run pytest tests/pm/test_assist_crud.py -v --timeout=30
  ```

  Expected: 7 tests pass.

- [ ] **Step 5: Commit**

  ```bash
  git add EvoScientist/pm/crud/assists.py tests/pm/test_assist_crud.py
  git commit -m "feat(pm): add ExperimentAssist CRUD layer"
  ```

---

## Task 3: Pydantic Schemas

**Files:**
- Modify: `EvoScientist/pm/api/schemas.py`

- [ ] **Step 1: Append `AssistCreate` and `AssistResponse` to `schemas.py`**

  Open `EvoScientist/pm/api/schemas.py`. Append at the very end (after `ErrorResponse`):

  ```python


  # ── Assists ───────────────────────────────────────────────────────────────────


  class AssistCreate(BaseModel):
      prompt: str = Field(min_length=1, max_length=4096)
      target_field: str | None = Field(
          default=None,
          pattern="^(hypothesis|protocol|entry_body)$",
      )


  class AssistResponse(BaseModel):
      id: str
      experiment_id: str
      project_id: str
      prompt: str
      status: str
      output: str | None
      error: str | None
      target_field: str | None
      created_by: str
      created_at: str
      finished_at: str | None
  ```

- [ ] **Step 2: Verify syntax**

  ```bash
  python3 -c "import ast; ast.parse(open('EvoScientist/pm/api/schemas.py').read()); print('OK')"
  ```

  Expected: `OK`

- [ ] **Step 3: Commit**

  ```bash
  git add EvoScientist/pm/api/schemas.py
  git commit -m "feat(pm): add AssistCreate and AssistResponse schemas"
  ```

---

## Task 4: API Routes

**Files:**
- Create: `EvoScientist/pm/api/routes/assists.py`
- Modify: `EvoScientist/pm/api/app.py`
- Create: `tests/pm/test_assist_routes.py`

- [ ] **Step 1: Write the failing route tests**

  Create `tests/pm/test_assist_routes.py`:

  ```python
  """Tests for experiment assist API endpoints."""
  from __future__ import annotations

  import json
  import sqlite3
  from datetime import datetime, timedelta, timezone
  from pathlib import Path
  from unittest.mock import AsyncMock, patch

  import bcrypt
  import pytest
  from fastapi.testclient import TestClient

  from EvoScientist.pm.api.app import create_app
  from EvoScientist.pm.db import create_schema


  @pytest.fixture
  def auth_client(tmp_path: Path):
      db_path = tmp_path / "test.db"
      create_schema(db_path)
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
      conn.execute(
          """INSERT INTO experiments (id, project_id, name, status, tags,
             created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
          ("e1", "p1", "Exp 1", "planned", '["ml"]', "u1", now, now),
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


  ASSIST_URL = "/api/v1/projects/p1/experiments/e1/assist"
  LIST_URL = "/api/v1/projects/p1/experiments/e1/assists"


  def test_list_assists_empty(auth_client):
      tc, _ = auth_client
      resp = tc.get(LIST_URL)
      assert resp.status_code == 200
      assert resp.json() == []


  def test_create_assist(auth_client):
      tc, _ = auth_client
      with patch("EvoScientist.pm.api.routes.assists._notify_runner", new_callable=AsyncMock):
          resp = tc.post(ASSIST_URL, json={"prompt": "Write a hypothesis", "target_field": "hypothesis"})
      assert resp.status_code == 201
      data = resp.json()
      assert data["prompt"] == "Write a hypothesis"
      assert data["target_field"] == "hypothesis"
      assert data["status"] == "pending"
      assert data["experiment_id"] == "e1"
      # context_json should include experiment name
      # (not in response, just verify assist was created)
      assert data["id"]


  def test_context_includes_experiment_fields(auth_client):
      """Context snapshot assembled by POST must include experiment name."""
      tc, db_path = auth_client
      with patch("EvoScientist.pm.api.routes.assists._notify_runner", new_callable=AsyncMock):
          resp = tc.post(ASSIST_URL, json={"prompt": "Help"})
      assist_id = resp.json()["id"]

      # Read context_json from DB directly
      conn = sqlite3.connect(db_path)
      row = conn.execute(
          "SELECT context_json FROM experiment_assists WHERE id = ?", (assist_id,)
      ).fetchone()
      conn.close()
      ctx = json.loads(row[0])
      assert ctx["name"] == "Exp 1"
      assert "entries" in ctx
      assert "linked_tasks" in ctx


  def test_create_assist_experiment_not_found(auth_client):
      tc, _ = auth_client
      with patch("EvoScientist.pm.api.routes.assists._notify_runner", new_callable=AsyncMock):
          resp = tc.post(
              "/api/v1/projects/p1/experiments/NOPE/assist",
              json={"prompt": "x"},
          )
      assert resp.status_code == 404


  def test_create_assist_not_member(auth_client):
      tc, db_path = auth_client
      # Add experiment in a different project that u1 is not a member of
      conn = sqlite3.connect(db_path)
      now = datetime.now(timezone.utc).isoformat()
      conn.execute(
          "INSERT INTO projects (id, name, created_by, created_at) VALUES (?,?,?,?)",
          ("p2", "Other", "u1", now),
      )
      conn.execute(
          """INSERT INTO experiments (id, project_id, name, status, tags,
             created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)""",
          ("e2", "p2", "Other Exp", "planned", "[]", "u1", now, now),
      )
      conn.commit()
      conn.close()
      with patch("EvoScientist.pm.api.routes.assists._notify_runner", new_callable=AsyncMock):
          resp = tc.post(
              "/api/v1/projects/p2/experiments/e2/assist",
              json={"prompt": "x"},
          )
      assert resp.status_code == 403


  def test_cancel_assist(auth_client):
      tc, _ = auth_client
      with patch("EvoScientist.pm.api.routes.assists._notify_runner", new_callable=AsyncMock):
          create_resp = tc.post(ASSIST_URL, json={"prompt": "Help"})
      assist_id = create_resp.json()["id"]

      with patch("EvoScientist.pm.api.routes.assists.httpx.AsyncClient") as mock_client:
          mock_client.return_value.__aenter__.return_value.delete = AsyncMock()
          resp = tc.delete(f"/api/v1/assists/{assist_id}")
      assert resp.status_code == 204
  ```

- [ ] **Step 2: Run to verify tests fail**

  ```bash
  uv run pytest tests/pm/test_assist_routes.py -v --timeout=30 2>&1 | head -15
  ```

  Expected: `ImportError` — routes module not found.

- [ ] **Step 3: Create `EvoScientist/pm/api/routes/assists.py`**

  ```python
  """Experiment AI writing assistant endpoints."""
  from __future__ import annotations

  import json
  import os
  from pathlib import Path

  import httpx
  from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
  from fastapi.responses import StreamingResponse

  from ...crud.assists import (
      create_assist,
      get_assist,
      list_assists_for_experiment,
      update_assist_output,
      update_assist_status,
  )
  from ...crud.experiment_entries import list_entries
  from ...crud.experiments import get_experiment, list_linked_tasks
  from ...db import get_db_path
  from ...models import User
  from ..deps import get_current_user, require_project_role
  from ..schemas import AssistCreate, AssistResponse

  router = APIRouter()
  global_router = APIRouter()

  RUNNER_URL = os.getenv("RUNNER_URL", "http://127.0.0.1:8001")
  _MAX_ENTRY_BODY = 500  # chars per entry body in context snapshot


  # ── Helpers ───────────────────────────────────────────────────────────────────

  def _assist_to_response(a) -> AssistResponse:
      return AssistResponse(
          id=a.id,
          experiment_id=a.experiment_id,
          project_id=a.project_id,
          prompt=a.prompt,
          status=a.status,
          output=a.output,
          error=a.error,
          target_field=a.target_field,
          created_by=a.created_by,
          created_at=a.created_at,
          finished_at=a.finished_at,
      )


  def _build_context(experiment_id: str, project_id: str) -> str:
      """Assemble a JSON snapshot of experiment + entries + linked task titles."""
      exp = get_experiment(get_db_path(), experiment_id)
      entries = list_entries(get_db_path(), experiment_id, entry_type=None)
      linked = list_linked_tasks(get_db_path(), experiment_id)

      entry_snippets = [
          {
              "type": e.type,
              "title": e.title,
              "body": e.body[:_MAX_ENTRY_BODY] if e.body else "",
          }
          for e in entries
      ]

      ctx = {
          "name": exp.name,
          "hypothesis": exp.hypothesis or "",
          "protocol": exp.protocol or "",
          "status": exp.status,
          "tags": exp.tags,
          "deadline": exp.deadline or "",
          "entries": entry_snippets,
          "linked_tasks": [t.title for t in linked],
      }
      return json.dumps(ctx)


  def _build_prompt(prompt: str, context_json: str) -> str:
      """Combine experiment context with user prompt for the writing agent."""
      ctx = json.loads(context_json)
      lines = [
          "You are an AI writing assistant for a scientific experiment.",
          "",
          f"Experiment: {ctx['name']}",
          f"Hypothesis: {ctx['hypothesis'] or 'not set'}",
          f"Protocol: {ctx['protocol'] or 'not set'}",
          f"Status: {ctx['status']}",
          f"Tags: {', '.join(ctx['tags']) if ctx['tags'] else 'none'}",
      ]
      if ctx["entries"]:
          lines.append("")
          notes = [e for e in ctx["entries"] if e["type"] == "note"]
          results = [e for e in ctx["entries"] if e["type"] == "result"]
          if notes:
              lines.append("Existing notes:")
              for e in notes:
                  lines.append(f"  - {e['title']}: {e['body']}")
          if results:
              lines.append("Existing results:")
              for e in results:
                  lines.append(f"  - {e['title']}: {e['body']}")
      if ctx["linked_tasks"]:
          lines.append(f"\nLinked tasks: {', '.join(ctx['linked_tasks'])}")
      lines.append(f"\nUser request: {prompt}")
      return "\n".join(lines)


  async def _notify_runner(assist_id: str, full_prompt: str, workspace_dir: str) -> None:
      """Fire-and-forget: tell the runner to start the writing agent."""
      try:
          async with httpx.AsyncClient(timeout=10) as client:
              await client.post(
                  f"{RUNNER_URL}/runs",
                  json={
                      "run_id": assist_id,
                      "agent_type": "writing",
                      "prompt": full_prompt,
                      "workspace_dir": workspace_dir,
                  },
              )
      except Exception:
          update_assist_status(get_db_path(), assist_id, "failed")


  # ── Routes ────────────────────────────────────────────────────────────────────

  @router.post(
      "/{project_id}/experiments/{exp_id}/assist",
      response_model=AssistResponse,
      status_code=status.HTTP_201_CREATED,
      summary="Create an AI writing assist for an experiment",
  )
  async def create_experiment_assist(
      project_id: str,
      exp_id: str,
      body: AssistCreate,
      background_tasks: BackgroundTasks,
      current_user: User = Depends(require_project_role("owner", "editor")),
  ):
      """Create an assist record and dispatch the writing agent."""
      exp = get_experiment(get_db_path(), exp_id)
      if not exp or exp.project_id != project_id:
          raise HTTPException(status_code=404, detail="Experiment not found")

      context_json = _build_context(exp_id, project_id)
      full_prompt = _build_prompt(body.prompt, context_json)

      assist = create_assist(
          get_db_path(),
          experiment_id=exp_id,
          project_id=project_id,
          prompt=body.prompt,
          context_json=context_json,
          target_field=body.target_field,
          created_by=current_user.id,
      )

      workspace_base = os.getenv(
          "EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs")
      )
      workspace_dir = str(Path(workspace_base) / "assists" / assist.id)

      background_tasks.add_task(_notify_runner, assist.id, full_prompt, workspace_dir)
      return _assist_to_response(assist)


  @router.get(
      "/{project_id}/experiments/{exp_id}/assists",
      response_model=list[AssistResponse],
      summary="List AI assists for an experiment",
  )
  def list_experiment_assists(
      project_id: str,
      exp_id: str,
      current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
  ):
      exp = get_experiment(get_db_path(), exp_id)
      if not exp or exp.project_id != project_id:
          raise HTTPException(status_code=404, detail="Experiment not found")
      return [
          _assist_to_response(a)
          for a in list_assists_for_experiment(get_db_path(), exp_id)
      ]


  @global_router.get(
      "/assists/{assist_id}/stream",
      summary="SSE stream of assist output tokens",
  )
  async def stream_assist_output(
      assist_id: str,
      current_user: User = Depends(get_current_user),
  ):
      """SSE stream. Returns saved output immediately if assist is already complete."""
      assist = get_assist(get_db_path(), assist_id)
      if not assist:
          raise HTTPException(status_code=404, detail="Assist not found")

      if assist.status in ("done", "failed", "cancelled"):
          async def _completed():
              if assist.output:
                  yield f'data: {json.dumps({"type": "token", "data": assist.output})}\n\n'
              yield f'data: {json.dumps({"type": "status", "data": assist.status})}\n\n'
          return StreamingResponse(
              _completed(),
              media_type="text/event-stream",
              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
          )

      update_assist_status(get_db_path(), assist_id, "running")

      async def _proxy():
          accumulated: list[str] = []
          final_status = "failed"
          try:
              async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
                  async with client.stream(
                      "GET", f"{RUNNER_URL}/runs/{assist_id}/stream"
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
              update_assist_output(
                  get_db_path(), assist_id, final_status, "".join(accumulated)
              )

      return StreamingResponse(
          _proxy(),
          media_type="text/event-stream",
          headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
      )


  @global_router.delete(
      "/assists/{assist_id}",
      status_code=status.HTTP_204_NO_CONTENT,
      summary="Cancel a running assist",
  )
  async def cancel_assist(
      assist_id: str,
      current_user: User = Depends(get_current_user),
  ):
      assist = get_assist(get_db_path(), assist_id)
      if not assist:
          raise HTTPException(status_code=404, detail="Assist not found")
      try:
          async with httpx.AsyncClient(timeout=5) as client:
              await client.delete(f"{RUNNER_URL}/runs/{assist_id}")
      except Exception:
          pass
      update_assist_status(get_db_path(), assist_id, "cancelled")
  ```

- [ ] **Step 4: Register routers in `app.py`**

  Open `EvoScientist/pm/api/app.py`.

  Change:
  ```python
  from .routes import attachments, auth, experiments, projects, runs, tasks, users
  ```
  To:
  ```python
  from .routes import assists, attachments, auth, experiments, projects, runs, tasks, users
  ```

  After `app.include_router(attachments.global_router, ...)`, add:
  ```python
      app.include_router(
          assists.router, prefix="/api/v1/projects", tags=["assists"]
      )
      app.include_router(
          assists.global_router, prefix="/api/v1", tags=["assists"]
      )
  ```

- [ ] **Step 5: Run route tests**

  ```bash
  uv run pytest tests/pm/test_assist_routes.py -v --timeout=30
  ```

  Expected: all 6 tests pass.

- [ ] **Step 6: Run full PM test suite to check for regressions**

  ```bash
  uv run pytest tests/pm/ -q --timeout=30 2>&1 | tail -5
  ```

  Expected: all pass.

- [ ] **Step 7: Commit**

  ```bash
  git add EvoScientist/pm/api/routes/assists.py EvoScientist/pm/api/app.py tests/pm/test_assist_routes.py
  git commit -m "feat(pm): add experiment assist API routes and SSE stream"
  ```

---

## Task 5: Frontend API Client

**Files:**
- Modify: `EvoScientist/pm/frontend/src/api.ts`

- [ ] **Step 1: Add `Assist` interface and API methods to `api.ts`**

  Open `EvoScientist/pm/frontend/src/api.ts`.

  **A.** After the closing `}` of the `api` object (after `deleteAttachment`), but BEFORE `export interface UserRecord`, add to the `api` object (append inside the `}` before closing):

  ```typescript
    // ── Assists ──────────────────────────────────────────────────────────────
    createAssist: (
      projectId: string,
      expId: string,
      data: { prompt: string; target_field?: string | null }
    ) => request<Assist>('POST', `/projects/${projectId}/experiments/${expId}/assist`, data),
    listAssists: (projectId: string, expId: string) =>
      request<Assist[]>('GET', `/projects/${projectId}/experiments/${expId}/assists`),
    cancelAssist: (assistId: string) =>
      request<void>('DELETE', `/assists/${assistId}`),
    assistStreamUrl: (assistId: string): string =>
      `/api/v1/assists/${assistId}/stream`,
  ```

  **B.** After the `Attachment` interface at the end of the file, append:

  ```typescript

  export interface Assist {
    id: string
    experiment_id: string
    project_id: string
    prompt: string
    status: 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
    output: string | null
    error: string | null
    target_field: 'hypothesis' | 'protocol' | 'entry_body' | null
    created_by: string
    created_at: string
    finished_at: string | null
  }
  ```

- [ ] **Step 2: TypeScript check**

  ```bash
  cd EvoScientist/pm/frontend && npx tsc --noEmit 2>&1 | head -20
  ```

  Expected: no errors.

- [ ] **Step 3: Commit**

  ```bash
  git add EvoScientist/pm/frontend/src/api.ts
  git commit -m "feat(pm): add Assist type and assist API client methods"
  ```

---

## Task 6: useAssistStream Hook

**Files:**
- Create: `EvoScientist/pm/frontend/src/hooks/useAssistStream.ts`

- [ ] **Step 1: Create the hook**

  Create `EvoScientist/pm/frontend/src/hooks/useAssistStream.ts`:

  ```typescript
  import { useEffect, useRef, useState } from 'react'

  export type AssistStreamStatus = 'idle' | 'streaming' | 'done' | 'failed' | 'cancelled'

  export interface AssistStreamState {
    output: string
    isStreaming: boolean
    streamStatus: AssistStreamStatus
  }

  /**
   * Streams SSE output for an experiment assist.
   * Resets state whenever assistId changes.
   */
  export function useAssistStream(assistId: string | null): AssistStreamState {
    const [output, setOutput] = useState('')
    const [isStreaming, setIsStreaming] = useState(false)
    const [streamStatus, setStreamStatus] = useState<AssistStreamStatus>('idle')
    const controllerRef = useRef<AbortController | null>(null)

    useEffect(() => {
      setOutput('')
      setIsStreaming(false)
      setStreamStatus('idle')

      if (!assistId) return

      const controller = new AbortController()
      controllerRef.current = controller
      setIsStreaming(true)
      setStreamStatus('streaming')

      async function stream() {
        const token = sessionStorage.getItem('pm_token')
        let response: Response

        try {
          response = await fetch(`/api/v1/assists/${assistId}/stream`, {
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
                  setStreamStatus(event.data as AssistStreamStatus)
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
    }, [assistId])

    return { output, isStreaming, streamStatus }
  }
  ```

- [ ] **Step 2: TypeScript check**

  ```bash
  cd EvoScientist/pm/frontend && npx tsc --noEmit 2>&1 | head -10
  ```

  Expected: no errors.

- [ ] **Step 3: Commit**

  ```bash
  git add EvoScientist/pm/frontend/src/hooks/useAssistStream.ts
  git commit -m "feat(pm): add useAssistStream SSE hook"
  ```

---

## Task 7: AiAssistPanel Component

**Files:**
- Create: `EvoScientist/pm/frontend/src/components/AiAssistPanel.tsx`

- [ ] **Step 1: Create `AiAssistPanel.tsx`**

  Create `EvoScientist/pm/frontend/src/components/AiAssistPanel.tsx`:

  ```tsx
  import { useState } from 'react'
  import { useMutation, useQueryClient } from '@tanstack/react-query'
  import { api, Assist, Experiment, ExperimentEntry } from '../api'
  import { useAssistStream } from '../hooks/useAssistStream'

  const TARGET_OPTIONS = [
    { value: 'hypothesis', label: 'Hypothesis' },
    { value: 'protocol',   label: 'Protocol' },
    { value: 'entry_body', label: 'New Note body' },
    { value: 'result_body', label: 'New Result body' },
  ] as const

  type TargetOption = typeof TARGET_OPTIONS[number]['value']

  interface Props {
    experiment: Experiment
    projectId: string
    onClose: () => void
    onApplyHypothesis: (text: string) => void
    onApplyProtocol: (text: string) => void
    onApplyEntryBody: (text: string, type: 'note' | 'result') => void
  }

  export function AiAssistPanel({
    experiment, projectId, onClose,
    onApplyHypothesis, onApplyProtocol, onApplyEntryBody,
  }: Props) {
    const qc = useQueryClient()
    const [prompt, setPrompt] = useState('')
    const [target, setTarget] = useState<TargetOption>('hypothesis')
    const [activeAssistId, setActiveAssistId] = useState<string | null>(null)
    const [appliedText, setAppliedText] = useState<string | null>(null)

    const { output, isStreaming, streamStatus } = useAssistStream(activeAssistId)

    const isRunning = isStreaming || streamStatus === 'streaming'
    const isDone = streamStatus === 'done'
    const hasFailed = streamStatus === 'failed'

    const createMutation = useMutation({
      mutationFn: () => api.createAssist(projectId, experiment.id, {
        prompt,
        target_field: target === 'result_body' ? 'entry_body' : target,
      }),
      onSuccess: (assist: Assist) => {
        setActiveAssistId(assist.id)
        setAppliedText(null)
        qc.invalidateQueries({ queryKey: ['assists', experiment.id] })
      },
    })

    const cancelMutation = useMutation({
      mutationFn: () => api.cancelAssist(activeAssistId!),
      onSuccess: () => setActiveAssistId(null),
    })

    function handleApply() {
      const text = output || ''
      if (!text) return
      if (target === 'hypothesis') onApplyHypothesis(text)
      else if (target === 'protocol') onApplyProtocol(text)
      else if (target === 'entry_body') onApplyEntryBody(text, 'note')
      else if (target === 'result_body') onApplyEntryBody(text, 'result')
      setAppliedText(text)
      setActiveAssistId(null)
    }

    function handleDiscard() {
      setActiveAssistId(null)
      setAppliedText(null)
    }

    const accent = '#a78bfa'  // purple — distinct from orange (tasks) and green (results)

    return (
      <div style={{
        position: 'fixed', right: 420, top: 0, bottom: 0, width: 360,
        background: 'var(--surface-panel)', borderLeft: '1px solid var(--border)',
        zIndex: 31, display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: '12px 14px 10px', borderBottom: '1px solid var(--border-subtle)',
          flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span style={{
            fontSize: 18, fontWeight: 700, fontFamily: 'var(--font-mono)',
            color: accent, letterSpacing: '0.08em',
          }}>
            ✦ AI ASSISTANT
          </span>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: 'var(--text-3)', fontSize: 22, cursor: 'pointer', padding: 2 }}
          >✕</button>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '10px 14px' }}>
          {/* Target field selector */}
          <div style={{ marginBottom: 10 }}>
            <div style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontWeight: 700, marginBottom: 5 }}>
              APPLY TO
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
              {TARGET_OPTIONS.map(opt => (
                <button
                  key={opt.value}
                  onClick={() => setTarget(opt.value)}
                  style={{
                    background: target === opt.value ? `${accent}14` : 'var(--surface-input)',
                    border: `1px solid ${target === opt.value ? `${accent}44` : 'var(--border)'}`,
                    borderRadius: 3, padding: '5px 8px',
                    color: target === opt.value ? accent : 'var(--text-3)',
                    fontSize: 15, fontFamily: 'var(--font-mono)', cursor: 'pointer',
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Prompt */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 16, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontWeight: 700, marginBottom: 5 }}>
              PROMPT
            </div>
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              rows={4}
              disabled={isRunning}
              placeholder="Describe what to write…"
              style={{
                width: '100%', boxSizing: 'border-box',
                background: 'var(--surface-input)', border: `1px solid ${accent}33`,
                borderRadius: 4, color: 'var(--text-2)', fontSize: 16,
                padding: '6px 8px', fontFamily: 'inherit', resize: 'vertical',
                outline: 'none', opacity: isRunning ? 0.5 : 1,
              }}
            />
          </div>

          {/* Generate / Stop button */}
          {isRunning ? (
            <button
              onClick={() => cancelMutation.mutate()}
              style={{
                width: '100%', background: 'rgba(244,63,94,0.08)',
                border: '1px solid rgba(244,63,94,0.28)', borderRadius: 3,
                padding: '6px 0', color: '#f43f5e', fontSize: 16, fontWeight: 700,
                fontFamily: 'var(--font-mono)', cursor: 'pointer', marginBottom: 10,
              }}
            >
              ■ STOP
            </button>
          ) : (
            <button
              onClick={() => createMutation.mutate()}
              disabled={!prompt.trim()}
              style={{
                width: '100%', background: `${accent}14`,
                border: `1px solid ${accent}44`, borderRadius: 3,
                padding: '6px 0', color: accent, fontSize: 16, fontWeight: 700,
                fontFamily: 'var(--font-mono)', cursor: 'pointer', marginBottom: 10,
                opacity: !prompt.trim() ? 0.4 : 1,
              }}
            >
              ▶ GENERATE
            </button>
          )}

          {/* Output */}
          {(isRunning || isDone || hasFailed || output) && (
            <div style={{
              border: `1px solid ${accent}22`, borderRadius: 4, overflow: 'hidden', marginBottom: 8,
            }}>
              <div style={{
                background: `${accent}08`, padding: '4px 8px',
                fontSize: 15, color: accent, fontFamily: 'var(--font-mono)', fontWeight: 700,
              }}>
                {isRunning ? 'GENERATING…' : hasFailed ? 'FAILED' : 'OUTPUT'}
              </div>
              <div style={{
                padding: '6px 8px', background: 'var(--surface-input)',
                maxHeight: 200, overflowY: 'auto',
              }}>
                <pre style={{
                  fontSize: 15, color: 'var(--text-2)', fontFamily: 'var(--font-mono)',
                  margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.6,
                }}>
                  {output || (isRunning ? '…' : '')}
                  {isRunning && <span style={{ color: accent }}>▋</span>}
                </pre>
              </div>
              {isDone && output && (
                <div style={{ display: 'flex', gap: 4, padding: '6px 8px', borderTop: `1px solid ${accent}18` }}>
                  <button
                    onClick={handleApply}
                    style={{
                      flex: 1, background: `${accent}14`, border: `1px solid ${accent}44`,
                      borderRadius: 3, padding: '4px 0', color: accent,
                      fontSize: 15, fontFamily: 'var(--font-mono)', cursor: 'pointer', fontWeight: 700,
                    }}
                  >
                    ✔ APPLY
                  </button>
                  <button
                    onClick={handleDiscard}
                    style={{
                      flex: 1, background: 'var(--surface-input)', border: '1px solid var(--border)',
                      borderRadius: 3, padding: '4px 0', color: 'var(--text-3)',
                      fontSize: 15, fontFamily: 'var(--font-mono)', cursor: 'pointer',
                    }}
                  >
                    ✕ DISCARD
                  </button>
                </div>
              )}
            </div>
          )}

          {appliedText && (
            <div style={{
              fontSize: 15, color: '#10b981', fontFamily: 'var(--font-mono)',
              padding: '4px 0',
            }}>
              ✓ Applied to {TARGET_OPTIONS.find(o => o.value === target)?.label ?? target}
            </div>
          )}
        </div>
      </div>
    )
  }
  ```

- [ ] **Step 2: TypeScript check**

  ```bash
  cd EvoScientist/pm/frontend && npx tsc --noEmit 2>&1 | head -20
  ```

  Expected: no errors.

- [ ] **Step 3: Commit**

  ```bash
  git add EvoScientist/pm/frontend/src/components/AiAssistPanel.tsx
  git commit -m "feat(pm): add AiAssistPanel component with streaming output and apply actions"
  ```

---

## Task 8: Wire into ExperimentDetail

**Files:**
- Modify: `EvoScientist/pm/frontend/src/components/ExperimentDetail.tsx`

- [ ] **Step 1: Add imports and state**

  Open `EvoScientist/pm/frontend/src/components/ExperimentDetail.tsx`.

  **A.** Change the import line from:
  ```typescript
  import { api, Experiment, ExperimentEntry, Task } from '../api'
  ```
  To:
  ```typescript
  import { api, Experiment, ExperimentEntry, Task } from '../api'
  import { AiAssistPanel } from './AiAssistPanel'
  ```

  **B.** Inside `ExperimentDetail`, after `const [taskSearch, setTaskSearch] = useState('')`, add:
  ```typescript
    const [showAiPanel, setShowAiPanel] = useState(false)
    const [pendingEntryBody, setPendingEntryBody] = useState<{ text: string; type: 'note' | 'result' } | null>(null)
  ```

  **C.** Add an `updateExperimentMutation` after the existing mutations (after `unlinkTaskMutation`):
  ```typescript
    const updateExperimentMutation = useMutation({
      mutationFn: (data: { hypothesis?: string; protocol?: string }) =>
        api.updateExperiment(projectId, experiment.id, data),
      onSuccess: () => qc.invalidateQueries({ queryKey: ['experiment', experiment.id] }),
    })
  ```

- [ ] **Step 2: Add ✦ AI button to the header**

  Find the close button in the header:
  ```tsx
          <button
            onClick={onClose}
            aria-label="✕"
            style={{ background: 'none', border: 'none', color: 'var(--text-3)', fontSize: 24, cursor: 'pointer', padding: 4 }}
          >
            ✕
          </button>
  ```

  Replace it with:
  ```tsx
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <button
              onClick={() => setShowAiPanel(p => !p)}
              style={{
                background: showAiPanel ? 'rgba(167,139,250,0.12)' : 'none',
                border: showAiPanel ? '1px solid rgba(167,139,250,0.3)' : '1px solid transparent',
                borderRadius: 4, color: '#a78bfa', fontSize: 18,
                cursor: 'pointer', padding: '2px 8px',
                fontFamily: 'var(--font-mono)', fontWeight: 700,
              }}
              title="AI Writing Assistant"
            >
              ✦ AI
            </button>
            <button
              onClick={onClose}
              aria-label="✕"
              style={{ background: 'none', border: 'none', color: 'var(--text-3)', fontSize: 24, cursor: 'pointer', padding: 4 }}
            >
              ✕
            </button>
          </div>
  ```

- [ ] **Step 3: Render `AiAssistPanel` and handle apply callbacks**

  Just before the closing `</div>` of the entire `ExperimentDetail` return, add:

  ```tsx
      {showAiPanel && (
        <AiAssistPanel
          experiment={experiment}
          projectId={projectId}
          onClose={() => setShowAiPanel(false)}
          onApplyHypothesis={(text) => updateExperimentMutation.mutate({ hypothesis: text })}
          onApplyProtocol={(text) => updateExperimentMutation.mutate({ protocol: text })}
          onApplyEntryBody={(text, type) => {
            setPendingEntryBody({ text, type })
            setTab(type === 'note' ? 'notes' : 'results')
            setShowEditor(true)
            setEditingEntry(null)
          }}
        />
      )}
  ```

- [ ] **Step 4: Pass `pendingEntryBody` to `EntryEditor` when set**

  Find the `showEditor` block that renders `<EntryEditor>` for new entries:
  ```tsx
          {showEditor && (
            <div style={{ marginBottom: 10 }}>
              <EntryEditor type={type} onSave={onSaveNew} onCancel={onCancelEditor} />
            </div>
          )}
  ```

  The `EntryEditor` is inside `EntriesTab`. Pass `initialBody` from the pending body. In the parent `ExperimentDetail`, pass `pendingBody` to `EntriesTab`:

  Add `pendingBody?: string` to `EntriesTab` props, and in `EntryEditor` for new entries use `initialBody={pendingBody ?? ''}`.

  **A.** Add `pendingBody?: string` to `EntriesTab` props interface (after `expId: string`):
  ```typescript
    pendingBody?: string
  ```

  **B.** In `EntriesTab` destructuring, add `pendingBody`:
  ```typescript
  function EntriesTab({
    entries, type, editingEntry, showEditor,
    onAdd, onEdit, onDelete, onSaveNew, onSaveEdit, onCancelEditor,
    projectId, expId, pendingBody,
  }: { ...existing...; pendingBody?: string })
  ```

  **C.** Change the `<EntryEditor>` for new entries to:
  ```tsx
              <EntryEditor type={type} onSave={onSaveNew} onCancel={onCancelEditor} initialBody={pendingBody ?? ''} />
  ```

  **D.** In the parent `ExperimentDetail`, pass `pendingBody` to `EntriesTab`:
  ```tsx
              pendingBody={pendingEntryBody?.type === (tab === 'notes' ? 'note' : 'result') ? pendingEntryBody.text : undefined}
  ```
  And clear it on cancel by adding to `onCancelEditor`:
  ```typescript
            onCancelEditor={() => { setShowEditor(false); setEditingEntry(null); setPendingEntryBody(null) }}
  ```

- [ ] **Step 5: TypeScript check**

  ```bash
  cd EvoScientist/pm/frontend && npx tsc --noEmit 2>&1 | head -20
  ```

  Fix any errors, then re-check until clean.

- [ ] **Step 6: Run full test suite**

  ```bash
  uv run pytest --timeout=30 -q 2>&1 | tail -5
  ```

  Expected: all pass (1481+ tests).

- [ ] **Step 7: Commit**

  ```bash
  git add EvoScientist/pm/frontend/src/components/ExperimentDetail.tsx
  git commit -m "feat(pm): wire AiAssistPanel into ExperimentDetail with apply callbacks"
  ```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| `experiment_assists` table with all columns | Task 1 |
| `ExperimentAssist` dataclass | Task 1 |
| CRUD: create/get/list/update_status/update_output | Task 2 |
| `AssistCreate`, `AssistResponse` schemas | Task 3 |
| POST `/experiments/{eid}/assist` — create + dispatch | Task 4 |
| GET `/experiments/{eid}/assists` — list | Task 4 |
| GET `/assists/{id}/stream` — SSE proxy | Task 4 |
| DELETE `/assists/{id}` — cancel | Task 4 |
| Context snapshot includes exp + entries + linked tasks | Task 4 (`_build_context`) |
| System prompt assembled from context | Task 4 (`_build_prompt`) |
| Runner dispatch reuses `writing` agent | Task 4 (`_notify_runner`) |
| `Assist` TS type + 4 API methods | Task 5 |
| `useAssistStream` SSE hook | Task 6 |
| `AiAssistPanel` with prompt/target/stream/apply/discard | Task 7 |
| ✦ AI button in ExperimentDetail header | Task 8 |
| Apply → PATCH experiment for hypothesis/protocol | Task 8 |
| Apply → pre-fills EntryEditor for note/result | Task 8 |
| Error: runner unreachable → `status='failed'` | Task 4 (`_notify_runner`) |
| Cancel: frontend calls DELETE → runner abort | Tasks 7 + 4 |
| Tests: CRUD, routes, cascade delete | Tasks 2 + 4 |

All spec requirements covered. ✅
