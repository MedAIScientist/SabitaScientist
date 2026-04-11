# Design: AI Writing Assistant Panel for PM Experiments

**Date:** 2026-04-12
**Branch target:** `feature/multi_project`
**Status:** Approved

---

## Overview

Add an AI writing assistant side panel to the PM experiment view. The panel lets researchers generate and apply AI-drafted text to experiment fields (hypothesis, protocol) and entry bodies (notes, results) using the full experiment context as a prompt prefix.

---

## Goals

- Let users invoke the `writing` agent from within an experiment without leaving the experiment view
- Auto-include full experiment context (fields + all entries + linked task titles) so the AI produces relevant output without manual copy-paste
- Apply generated text directly to the target field with one click
- Keep a history of past assists within the session

## Non-Goals

- Multi-turn conversation (single prompt → single response per assist)
- Streaming partial output to the DB (output saved only on completion)
- Rate limiting per user (deferred)
- AI analysis of uploaded file contents (separate feature)

---

## Architecture

The feature adds a self-contained `experiment_assists` subsystem alongside the existing `runs` subsystem. It reuses the runner service for agent execution and SSE streaming.

```
Browser (AiAssistPanel)
  └── POST /api/v1/projects/{pid}/experiments/{eid}/assist
        └── Assembles context snapshot, creates assist record
              └── Dispatches to runner service (writing agent)
  └── GET  /api/v1/assists/{assist_id}/stream   (SSE)
        └── Runner streams tokens → accumulated in DB on finish
```

---

## Data Model

### New table: `experiment_assists`

```sql
CREATE TABLE experiment_assists (
    id             TEXT PRIMARY KEY,
    experiment_id  TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    project_id     TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    prompt         TEXT NOT NULL,
    context_json   TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK(status IN ('pending','running','done','failed','cancelled')),
    output         TEXT,
    error          TEXT,
    target_field   TEXT,   -- 'hypothesis'|'protocol'|'entry_body'|NULL
    created_by     TEXT NOT NULL REFERENCES users(id),
    created_at     TEXT NOT NULL,
    finished_at    TEXT
);
CREATE INDEX idx_experiment_assists_exp ON experiment_assists(experiment_id);
```

**Key decisions:**
- `context_json` is a snapshot at request time — immune to concurrent edits during streaming
- `target_field` is a UI hint stored with the record; nullable (user can always paste manually)
- Cascade-deletes with experiment — no orphan records
- No FK to `tasks` — completely independent of the existing runs table

### New dataclass: `ExperimentAssist`

Mirrors `Run` in structure. Fields: `id`, `experiment_id`, `project_id`, `prompt`, `context_json`, `status`, `output`, `error`, `target_field`, `created_by`, `created_at`, `finished_at`.

---

## Backend API

### Routes — `api/routes/assists.py`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/projects/{pid}/experiments/{eid}/assist` | owner/editor | Create assist, dispatch to runner |
| `GET` | `/projects/{pid}/experiments/{eid}/assists` | any member | List assists for experiment |
| `GET` | `/assists/{assist_id}/stream` | any member | SSE token stream |
| `DELETE` | `/assists/{assist_id}` | owner/editor | Cancel running assist |

### Request body (`POST`)

```json
{
  "prompt": "Write a hypothesis testing whether X affects Y",
  "target_field": "hypothesis"
}
```

### Context assembly (server-side on `POST`)

The endpoint fetches and serialises into `context_json`:
1. Experiment fields: `name`, `hypothesis`, `protocol`, `status`, `tags`, `deadline`
2. All entries: `type`, `title`, `body` (each body truncated to 500 chars if >20 entries total)
3. Linked task titles only (no descriptions)

This becomes the system prompt prefix sent to the `writing` agent:

```
You are an AI writing assistant for a scientific experiment.

Experiment: {name}
Hypothesis: {hypothesis or "not set"}
Protocol: {protocol or "not set"}
Status: {status}
Tags: {tags}

Existing notes:
- {title}: {body}...

Existing results:
- {title}: {body}...

Linked tasks: {task titles}

User request: {prompt}
```

### Runner integration

The existing runner service handles dispatch identically to task runs — the assist endpoint calls runner with `agent_type='writing'` and the assembled prompt string. No changes to runner internals required.

---

## New Backend Files

| File | Purpose |
|------|---------|
| `EvoScientist/pm/crud/assists.py` | create / list / get / update_status / cancel |
| `EvoScientist/pm/api/routes/assists.py` | 4 endpoints above |

### Modified Backend Files

| File | Change |
|------|--------|
| `EvoScientist/pm/db.py` | Add `experiment_assists` table + index to `_SCHEMA` |
| `EvoScientist/pm/models.py` | Add `ExperimentAssist` dataclass |
| `EvoScientist/pm/api/app.py` | Register `assists.router` and `assists.global_router` |

---

## Frontend

### New Files

| File | Purpose |
|------|---------|
| `frontend/src/components/AiAssistPanel.tsx` | Side panel component |
| `frontend/src/hooks/useAssistStream.ts` | SSE hook (mirrors `useRunStream`) |

### Modified Files

| File | Change |
|------|--------|
| `frontend/src/api.ts` | Add `Assist` type + `createAssist`, `listAssists`, `cancelAssist`, `assistStreamUrl` |
| `frontend/src/components/ExperimentDetail.tsx` | Add ✦ AI button to header, render `AiAssistPanel` |

### UI Layout

```
┌─────────────────────────────────┐
│  ✦ AI ASSISTANT          [✕]   │
├─────────────────────────────────┤
│  Apply to: [hypothesis ▾]       │
│  (hypothesis / protocol /       │
│   new note / new result)        │
├─────────────────────────────────┤
│  ┌─────────────────────────┐   │
│  │ prompt textarea…        │   │
│  └─────────────────────────┘   │
│  [▶ GENERATE]                  │
├─────────────────────────────────┤
│  streamed output (monospace)    │
│                                 │
│  [✔ APPLY]  [✕ DISCARD]       │  ← shown when status='done'
└─────────────────────────────────┘
```

### Apply behaviour by target field

| `target_field` | APPLY action |
|----------------|-------------|
| `hypothesis` | `PATCH /experiments/{eid}` with `{ hypothesis: output }` |
| `protocol` | `PATCH /experiments/{eid}` with `{ protocol: output }` |
| `entry_body` (note) | Pre-fills `EntryEditor` with output as body, opens editor for `note` type |
| `entry_body` (result) | Pre-fills `EntryEditor` with output as body, opens editor for `result` type |

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Runner unreachable | `status='failed'`, error shown in panel with retry button |
| LLM provider error | Streamed as `error` SSE event, displayed inline |
| Experiment deleted mid-stream | SSE closes, panel shows "Experiment no longer exists" |
| Panel closed mid-stream | Frontend calls `DELETE /assists/{id}`, runner aborts agent |

---

## Testing

### Backend

- `tests/pm/test_assist_crud.py` — CRUD: create, list, cancel, cascade delete with experiment
- `tests/pm/test_assist_routes.py` — API tests with mocked runner:
  - Context snapshot contains experiment fields + entries + task titles
  - 404 on unknown experiment
  - 403 for non-members
  - Status transitions (pending → running → done/failed/cancelled)

### Frontend (Vitest)

- `AiAssistPanel.test.tsx`:
  - Panel renders closed by default
  - Opens on ✦ AI button click
  - APPLY triggers `PATCH` on `hypothesis` / `protocol`
  - APPLY opens `EntryEditor` for `new note` / `new result`
  - DISCARD clears output, panel stays open

---

## Out of Scope

- Multi-turn conversation
- Streaming partial output to DB
- Rate limiting per user
- AI analysis of uploaded file contents
