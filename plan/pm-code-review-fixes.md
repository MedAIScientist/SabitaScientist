# PM Code Review — Fix Plan

Priority labels: 🔴 P0 (blocking) → 🟡 P1 (important) → 🟢 P2 (nice-to-have)

---

## 🔴 P0: Blocking Issues (fix first)

### P0-1: CORS `*` + credentials anti-pattern

**Issue**: `app.py:77-78` sets `allow_origins=["*"]` with `allow_credentials=True`, which browsers reject per CORS spec.

**Fix**: Switch to explicit origins from config, or drop `allow_credentials=True` when using wildcard.

**Files**: `pm/api/app.py`
- Option A: Remove `allow_credentials=True` (if no cookies needed)
- Option B: Read `CORS_ORIGINS` from env/config and split into list:
  ```python
  allow_origins=cfg.pm_cors_origins or ["http://localhost:5173"],
  ```
  Add `pm_cors_origins` to `EvoScientistConfig` in `config/settings.py`

**Complexity**: Low (1 file, 2 lines changed + config field)

---

### P0-2: Missing FK `ON DELETE` on `created_by` columns

**Issue**: Most `created_by TEXT REFERENCES users(id)` lack `ON DELETE` clause (`tasks`, `runs`, `experiments`, `experiment_entries`, `experiment_assists`, `project_phases`, `task_dependencies`, `attachments`, `admissions`, `grants`, `conferences`, `irb_approvals`, `lab_wiki_pages`, `publications`, `publication_versions`, `sandboxes`, `pipelines`, `cvat_projects`, `webknossos_datasets`). Deleting a user raises FK violation.

**Fix**: Add migration or alter schema. SQLite's `ALTER TABLE` cannot add `ON DELETE` to an existing column — need to:
  1. Create new tables with correct constraints
  2. Copy data
  3. Drop old tables
  4. Rename new tables

**Files**: `pm/db.py`
- Update `_MIGRATIONS` with a schema recreation or add `ON DELETE SET NULL` behavior by:
  - Setting `created_by` to `NULL` before user deletion (in user delete CRUD)
  - Or recreating affected tables

**Alternative (simpler)**: In `crud/users.py` `delete_user()`, null out `created_by` references before deleting:
```python
tables_with_created_by = ["tasks", "runs", "experiments", ...]
for table in tables_with_created_by:
    conn.execute(f"UPDATE {table} SET created_by = NULL WHERE created_by = ?", (user_id,))
```
Then delete the user. This is safer and avoids schema rebuild.

**Complexity**: Medium (1 file in CRUD + list of all FK tables)

---

### P0-3: No transaction wrapping `accept_admission`

**Issue**: `crud/admissions.py:141-155` calls `create_project()` (which opens its own `get_db()` context) and then `UPDATE admissions` in a separate context. If either fails, the other isn't rolled back.

**Fix**: Refactor to use a single shared connection. Options:
- A: Pass connection to `create_project` variant that accepts existing conn
- B: Inline the project creation SQL in `accept_admission` within the same context
- C: Extract `accept_admission` logic into a single `get_db()` block with both INSERT and UPDATE

**Files**: `pm/crud/admissions.py`, `pm/crud/projects.py`
- Add `create_project_with_conn(conn, ...)` variant to projects CRUD
- Or inline both operations in `admissions.py`

**Complexity**: Low-Medium (2 files)

---

### P0-4: `_run_section_and_save` truncates to 800 chars

**Issue**: `drafting.py:245` stores `text[:800]` and appends to abstract. Sections >800 chars lose content.

**Fix**: Store the full generated text. Two approaches:
- A: Save as a full publication version file (not just abstract field)
- B: Create an `experiment_entry` with the full text and link to publication
- C: Extend `publication_versions` to store full text in a new column

**Recommended**: Use `publication_versions` properly — store the full section text as a version note or create a dedicated storage field. The `abstract` field is not the right place for section drafts.

**Files**: `pm/api/routes/drafting.py`, potentially `pm/db.py` (new column on `publication_versions`)

**Complexity**: Medium

---

## 🟡 P1: Important Issues

### P1-1: Audit middleware swallows exceptions

**Issue**: `audit_middleware.py:74` has `except Exception: pass` — audit failures are invisible.

**Fix**: Replace with at least a `logger.warning()` call. Add `logging.getLogger()` at top.

```python
import logging
logger = logging.getLogger(__name__)
# ...
except Exception as exc:
    logger.warning("Audit log failed for %s %s: %s", request.method, request.url.path, exc)
```

**Files**: `pm/api/audit_middleware.py`

**Complexity**: Very Low (3 lines)

---

### P1-2: Zero pagination on list endpoints

**Issue**: All CRUD list functions return unlimited rows. Risk of OOM with large datasets.

**Fix**: Add `offset` and `limit` parameters to list CRUD functions and route handlers.

**Files**: All CRUD list functions + all route list handlers (~15-20 files)
- Pattern: `def list_X(db_path, ..., offset=0, limit=100) -> list[X]:`
- Add `LIMIT ? OFFSET ?` to SQL queries
- Add `offset` / `limit` query params to Pydantic schemas or route params

**Recommended**: Start with the most data-heavy endpoints:
1. `list_admissions`
2. `list_experiments`
3. `list_tasks`
4. `list_projects_for_user`
5. `list_publications`

**Complexity**: High (many files, repetitive but mechanical)

---

### P1-3: Groq runner state is in-memory only

**Issue**: `agent_runner.py:24-25` `_run_queues` and `_run_tasks` are module-level dicts. Server restart loses all active runs.

**Fix**: Persist run state to the database:
1. Add `queue_state` column or use the existing `runs` table `status` field
2. On startup, set all `running` runs to `failed` with error "Server restarted"
3. Optionally add a `run_output` DB table for streaming token persistence

**Files**: `pm/runner/agent_runner.py`, `pm/db.py` (potential migration)
- In `agent_runner.py`: on module init, query DB for orphaned `running` runs and mark them `failed`
- Update run status in DB as transitions happen

**Complexity**: Medium

---

### P1-4: Rate limiter is per-process

**Issue**: `rate_limiter.py:20` stores `_requests` in-process dict. Multiple uvicorn workers bypass rate limiting.

**Fix**: Options:
- A: Switch to a shared backend (Redis/Memcached) — best but adds dependency
- B: Document that uvicorn should run with `--workers 1` when rate limiter is needed
- C: Use SQLite-based rate limiting (cheap, no extra deps)

**Recommended**: Option B + C — add a fallback SQLite-based rate limiter:
```python
conn.execute("INSERT INTO rate_limits (ip, endpoint, requested_at) VALUES (?, ?, ?)")
count = conn.execute("SELECT COUNT(*) FROM rate_limits WHERE ip = ? AND requested_at > ?", ...)
```

**Files**: `pm/api/rate_limiter.py`, `pm/db.py` (new `rate_limits` table)

**Complexity**: Medium

---

### P1-5: Swagger UI exposed unconditionally

**Issue**: `app.py:71` always sets `docs_url="/api/docs"` regardless of environment.

**Fix**: Make docs URL configurable via `EvoScientistConfig`:
```python
docs_url=cfg.pm_docs_url if cfg.pm_docs_url else None,
```
Default to `/api/docs` in dev, `None` in production.

**Files**: `pm/api/app.py`, `EvoScientist/config/settings.py`

**Complexity**: Low (2 files)

---

### P1-6: `accept_admission` null `reviewer_id` crash

**Issue**: `crud/admissions.py:141-146` sets `created_by=reviewer_id`, but `reviewer_id` is `None` if no reviewer assigned. `create_project` inserts `None` into `created_by` which references `users(id) NOT NULL`, causing FK violation.

**Fix**: Fall back to `admission.created_by` (whoever imported the admission) when `reviewer_id` is None:
```python
created_by = reviewer_id or admission.created_by or "unknown"
```

**Files**: `pm/crud/admissions.py`

**Complexity**: Very Low (1 line change)

---

### P1-7: No input sanitization on Excel import

**Issue**: `crud/admissions.py:197-258` only checks `.xlsx` extension from filename (user-controlled). No magic-byte validation or cell sanitization.

**Fix**: 
1. Validate magic bytes (Excel files start with `PK\x03\x04`)
2. Set maximum row count and cell length limits
3. Strip control characters from cell values

```python
# Magic byte check
with open(file_path, "rb") as f:
    header = f.read(4)
    if header != b"PK\x03\x04":
        raise ValueError("Not a valid .xlsx file")
```

**Files**: `pm/crud/admissions.py`

**Complexity**: Low (15-20 lines added)

---

### P1-8: Hardcoded Groq model

**Issue**: `agent_runner.py:68` hardcodes `_MODEL = "mixtral-8x7b-32768"`.

**Fix**: Read from `EvoScientistConfig` with fallback:
```python
from ...config.settings import get_effective_config
_MODEL = getattr(get_effective_config(), "pm_runner_model", "mixtral-8x7b-32768")
```

**Files**: `pm/runner/agent_runner.py`, `EvoScientist/config/settings.py`

**Complexity**: Low (2 files)

---

## 🟢 P2: Nits & Suggestions

### P2-1: `__import__('time')` → top-level import

**Issue**: `drafting.py:482,537,587,646` uses inline `__import__('time')`.

**Fix**: Add `import time` at module top, replace all `__import__('time').time()` with `time.time()`.

**Files**: `pm/api/routes/drafting.py`

**Complexity**: Very Low (4 replacements + 1 import line)

---

### P2-2: Duplicate code in `_ai.py` sync/async functions

**Issue**: `run_llm_direct` and `run_llm_direct_async` share ~20 lines of identical skill-guidance-building and config logic.

**Fix**: Extract shared logic:
```python
def _prepare_llm_call(system_prompt, skill_guidance, model, temperature, max_tokens):
    if skill_guidance:
        system_prompt = _build_skill_augmented_system_prompt(system_prompt, skill_guidance)
    config = get_effective_config()
    model_name = model or getattr(config, "auxiliary_model", None) or DEFAULT_MODEL
    chat = get_chat_model(model_name, temperature=temperature, max_tokens=max_tokens)
    return chat, system_prompt
```

**Files**: `pm/_ai.py`

**Complexity**: Low (extract method, ~20 lines to 5)

---

### P2-3: 404 leaks project existence

**Issue**: `projects.py:94-104` returns 404 for unknown projects but `require_project_role` returns 403 for known ones, allowing existence probing.

**Fix**: Make `get_project_detail` return a generic "not found or access denied" for both cases:
```python
if not project:
    raise HTTPException(status_code=404, detail="Project not found or access denied")
```
Alternatively, change `require_project_role` to return 404 instead of 403.

**Files**: `pm/api/routes/projects.py`

**Complexity**: Very Low (1 line change)

---

### P2-4: Inline imports in drafting routes

**Issue**: `drafting.py` has scattered inline imports (`from ...crud.publications import create_version` at lines 220, 248, 328, 390, 410).

**Fix**: Move all imports to module top.

**Files**: `pm/api/routes/drafting.py`

**Complexity**: Very Low (move 5 import lines)

---

### P2-5: Missing `ON DELETE` on `attachments.uploaded_by`

**Issue**: `db.py:171` `uploaded_by TEXT REFERENCES users(id)` has no `ON DELETE` clause (migration added `classification` but didn't fix this).

**Fix**: Same approach as P0-2 — null out `uploaded_by` in `delete_user()` or add to the null-out list.

**Files**: `pm/crud/users.py` (covered by P0-2 fix)

---

### P2-6: `getattr(config, "auxiliary_model")` should be explicit config field

**Issue**: `_ai.py:77` uses `getattr(config, "auxiliary_model", None)` which is fragile — no type checking, no documentation, no default.

**Fix**: Add explicit `auxiliary_model: str = "gpt-4o"` to `EvoScientistConfig`. Use `config.auxiliary_model` directly.

**Files**: `EvoScientist/config/settings.py`, `pm/_ai.py`

**Complexity**: Low (2 files)

---

## Execution Order

```
Phase 1 — P0 fixes (data integrity & security)
├── P0-1: CORS fix
├── P0-2: FK ON DELETE fix
├── P0-3: Transaction wrapping
└── P0-4: Draft truncation fix

Phase 2 — P1 fixes (reliability & production readiness)
├── P1-1: Audit exception logging
├── P1-2: Pagination (start with top 5 endpoints)
├── P1-3: Runner state persistence
├── P1-4: Rate limiter per-process
├── P1-5: Swagger docs toggle
├── P1-6: Null reviewer crash
├── P1-7: Excel sanitization
└── P1-8: Groq model configurable

Phase 3 — P2 fixes (code quality)
├── P2-1: Import style
├── P2-2: DRY in _ai.py
├── P2-3: 404/403 info leak
├── P2-4: Inline imports
└── P2-6: Config field explicitness
```
