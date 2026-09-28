# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (Python 3.11–3.13 required)
uv sync --dev

# Run tests (no API keys needed)
uv run pytest
uv run pytest tests/pm/test_db.py -v          # PM DB schema tests
uv run pytest tests/pm/test_s2_queries.py -v  # S2 citation parser tests
uv run pytest -v --timeout=30

# Lint and format
uv run ruff check .
uv run ruff format .

# Run the PM dashboard locally
uv run EvoSci dashboard --host 0.0.0.0

# Run agent locally
EvoSci                          # interactive TUI
EvoSci onboard                  # interactive config wizard
```

## PM Module Architecture

The **Project Management (PM) module** lives at `EvoScientist/pm/` — a full-stack FastAPI + SQLite + React SPA for running a university research ecosystem. It is deeply integrated with EvoScientist's own infrastructure: paths, config, LLM, tools, memory, sessions, prompts, gateway, and langgraph dev.

```
pm/
  _evoscientist.py  # Bridge: EvoScientist paths, config, env resolution
  _ai.py            # Direct LLM via get_chat_model() + skills + memory + tools
  api/              # ~65 FastAPI endpoints across 30 route files
    routes/         # Auth, projects, tasks, experiments, publications,
    |               # labs, grants, conferences, IRB, wiki, search, audit,
    |               # drafting, ai_tools, compute, peer_review, bibliography,
    |               # mcp, memory_routes, middleware_routes, dashboard
    audit_middleware.py   # Auto-logs all mutations
    rate_limiter.py       # 200 req/min per IP
    soft_delete.py        # Soft delete helpers
  crud/             # Direct SQL data access (no ORM)
  compute/          # SLURM / SSH / Local compute backends
  s2/               # Semantic Scholar DB queries for citation verification
  runner/           # Async agent runner with SSE streaming
                    # Uses get_checkpointer() for persistence + memory recording
  frontend/         # 29+ React pages (Vite + TypeScript)
  templates/        # YAML project templates (life-science, medical, ml-research)
  db.py             # 26 tables, 7 migrations (path via EvoScientist.paths.DATA_DIR)
  models.py         # 25+ dataclasses
  notifications.py  # Email via EvoScientistConfig (email_smtp_*)
  oidc.py           # Microsoft O365 SSO via EvoScientistConfig (pm_oidc_*)
  auth.py           # bcrypt + token auth
  storage.py        # S3-compatible object storage via EvoScientistConfig
```

### Database — 26 tables

| Category | Tables |
|---|---|
| Core | users, auth_tokens, projects, project_members, tasks, task_comments, runs |
| Experiments | experiments, experiment_tasks, experiment_entries, experiment_assists |
| Lab Management | labs, lab_members, lab_wiki_pages |
| Publications | publications, publication_versions, publication_reviews, publication_experiments |
| Research Ops | grants, conferences, irb_approvals |
| Pipeline | project_phases, task_dependencies, attachments |
| Admin | audit_log, admissions |

### API Endpoints (~65)

| Prefix | Routes | Features |
|---|---|---|
| `/auth` | login, logout, OIDC | Password + Microsoft SSO |
| `/users` | CRUD + search | User management |
| `/projects` | CRUD + members | Kanban boards |
| `/labs` | CRUD + members | Multi-tenant labs |
| `/publications` | CRUD + pipeline | Paper lifecycle + AI drafting |
| `/grants` | CRUD | TÜBİTAK, TÜSEB, NIH, etc. |
| `/conferences` | CRUD | Submission deadlines |
| `/irb` | CRUD | Ethics approvals |
| `/templates` | List + from-template | Domain project templates |
| `/admissions` | List + import + review | Applicant pipeline |
| `/search` | Global search | Across all entities |
| `/wiki` | CRUD | Lab wiki pages |
| `/audit/logs` | List (admin) | Audit trail |
| `/admin/stats` | System stats | Cross-lab analytics |
| `/pi/stats` | Lab analytics | Mentorship + publications |
| `/export/*` | CSV/JSON | Data export |
| `/mcp/*` | Marketplace + installed | MCP server management |
| `/memory/*` | Observations + search + workers + skills | EvoScientist memory subsystem |
| `/middleware/available` | List | Agent middleware catalog |
| `/system/health` | Health check | LangGraph dev + skills status |

### AI-Powered Features

| Endpoint | Backend | What it does |
|---|---|---|
| `POST /projects/{id}/draft-paper` | runner / direct LLM | Full paper from project context |
| `POST /publications/{id}/draft-section` | runner / direct LLM | Abstract, intro, methods, results, etc. |
| `POST /projects/{id}/grant-proposal` | **direct LLM** via `get_chat_model()` + `ml-paper-writing` skill | NIH R01, NSF, TÜBİTAK 1001, etc. |
| `POST /projects/{id}/generate-hypothesis` | runner | 3-5 testable hypotheses |
| `POST /projects/{id}/research-ideation` | runner | Novel research directions |
| `POST /projects/{id}/validate-methodology` | runner | Methods review |
| `POST /projects/{id}/verify-citations` | runner + S2 DB | Citation verification |
| `POST /projects/{id}/literature-review` | runner | Structured lit review |
| `POST /projects/{id}/experiments/{id}/generate-figures` | **direct LLM** via `get_chat_model()` | Publication-quality figures |
| `POST /publications/{id}/respond-to-reviewers` | runner | Reviewer response letter |
| `POST /publications/{id}/revise` | runner | Revise existing text |
| `POST /publications/{id}/generate-ai-review` | runner | AI peer review |

All AI endpoints can optionally load EvoScientist skill SKILL.md files for guidance.
Direct LLM endpoints use `EvoScientist.llm.get_chat_model()` (200+ models, provider routing).

### EvoScientist Integration Points

| EvoScientist module | PM integration | What it provides |
|---|---|---|
| `paths.py` | `pm/_evoscientist.py` | DATA_DIR, WORKSPACE_ROOT, RUNS_DIR |
| `config/settings.py` | `pm/_evoscientist.py` | 16 PM config fields, `get_effective_config()` |
| `llm/models.py` | `pm/_ai.py` | `get_chat_model()` for direct LLM access |
| `prompts.py` | `pm/_ai.py` | WRITING_GUIDELINES, REPORT_TEMPLATE |
| `tools/search.py` | `pm/_ai.py` | `tavily_search()` for web research |
| `tools/think.py` | `pm/_ai.py` | `think_tool()` for structured reasoning |
| `memory/` | `pm/runner/agent_runner.py`, `pm/_ai.py` | `record_observation_file()`, `search_observation_files()`, `build_observation_index_context()` |
| `gateway/local.py` | `pm/runner/agent_runner.py` | `LocalThreadStore` for thread ID generation |
| `sessions.py` | `pm/runner/agent_runner.py` | `get_checkpointer()` for persistent agent checkpoints |
| `langgraph_dev/` | `pm/api/routes/dashboard.py` | `is_langgraph_dev_running()` for health checks |
| `mcp/` | `pm/api/routes/mcp.py` | `install_mcp_server()`, `fetch_marketplace_index()` |

### Frontend Pages (29+)

| Route | Page | Features |
|---|---|---|
| `/projects` | Projects | List, create, manage projects |
| `/projects/:id` | Board | Kanban board with tasks, phases |
| `/projects/:id/experiments` | ExperimentsPage | Experiment CRUD, entries |
| `/projects/:id/report` | ProjectReportPage | Per-project report |
| `/labs` | LabsPage | Multi-tenant lab management |
| `/labs/:id` | LabDetail | Lab members, projects |
| `/labs/:id/impact` | ImpactPage | Research impact (S2 citations) |
| `/labs/:id/wiki` | WikiPages | Lab wiki |
| `/labs/:id/wiki/:slug` | WikiPageView | Wiki page content |
| `/publications` | PublicationsPage | Paper lifecycle |
| `/publications/:id` | PublicationDetail | Versions, reviews, AI drafting |
| `/grants` | GrantsPage | Grant tracking |
| `/grants/:id` | GrantDetail | Grant details |
| `/conferences` | ConferencesPage | Conference deadlines |
| `/irb` | IRBPage | Ethics approvals |
| `/admissions` | AdmissionsPage | Applicant pipeline |
| `/admissions/:id` | AdmissionDetail | Review, aid decisions |
| `/mcp` | MCPPage | Browse marketplace, install/remove |
| `/memory` | MemoryPage | Search/record/link observations |
| `/health` | SystemHealthPage | LangGraph dev, skills, runner status |
| `/analytics` | AnalyticsPage | Cross-lab stats |
| `/admin` | AdminDashboard | System-wide admin |
| `/users` | UsersPage | User CRUD |
| `/profile` | ProfilePage | User settings |
| `/reports` | GlobalReportPage | Aggregate reports |

### PM Tools (Agent Access)

9 tools registered in the EvoScientist agent (`tools/pm_tools.py`) allowing AI to create projects, tasks, experiments, and entries directly. Agent runs in PM also record observations to `EvoScientist.memory` for cross-session context.

### Configuration

All PM configuration is managed through `EvoScientistConfig` (added to `config/settings.py` with `_ENV_MAPPINGS`). Legacy env vars still work via mappings.

| Config Field | Env Var | Purpose |
|---|---|---|
| `pm_db_path` | `EVOSCIENTIST_PM_DB` | PM SQLite DB path |
| `pm_runner_url` | — | Agent runner URL (default: :8001) |
| `pm_base_url` | `PM_BASE_URL` | PM web UI base URL |
| `pm_smtp_from` | `PM_SMTP_FROM` | Notification sender address |
| `pm_max_upload_mb` | `PM_MAX_UPLOAD_MB` | Max attachment upload size |
| `pm_garage_*` | `GARAGE_*` | S3/Garage object storage |
| `pm_oidc_*` | `OIDC_*` | Microsoft 365 SSO |
| `pm_s2_db_path` | `S2_DB_PATH` | Semantic Scholar citation DB |
| `email_smtp_*` | — | Shared EvoScientist email settings |

### Deployment

Production server: `medaiadm@10.150.145.10` — domain `https://medai.medipol.edu.tr`
Uses Docker Compose on bare metal (no Swarm/K8s). Three containers: `evoscientist`, `evoscientist-garage`, `evoscientist-nginx`.

**IMPORTANT — deploy ONLY via the deploy script. Never run ad-hoc Docker commands.**

```bash
# Deploy to production (syncs code → builds Docker → restarts container)
./deploy/deploy.sh medaiadm@10.150.145.10
```

The deploy script handles:
1. **Rsync** — syncs source code (excluding .git, node_modules, .venv, .env, etc.)
2. **SSL check** — verifies certs at `deploy/nginx/ssl/`
3. **Docker build** — builds `evoscientist:prod` image (uses cache, no `--no-cache`)
4. **Deploy** — recreates evoscientist container (garage + nginx stay up), waits for healthy

**Services:**

| Container | Image | Ports |
|-----------|-------|-------|
| evoscientist | evoscientist:prod | 7860 (API + SPA), 8001 (runner) |
| evoscientist-garage | dxflrs/garage:v1.0.1 | 3900 (S3) |
| evoscientist-nginx | nginx:alpine | 80 → 443 → evoscientist:7860 |

**Compose file:** `deploy/docker-compose.prod.yml` (single unified file)

**Data volumes:** `evoscientist-prod-data` (/data with pm.db + workspaces), `evoscientist-home`

**Secrets:** `.env` at project root + `deploy/.env` (deploy overrides root). SSL certs at `deploy/nginx/ssl/`.

**OIDC / Microsoft SSO:** Azure App with Client ID `991f879e-3b91-4d8f-850d-0b2ad468c976`. Redirect URI must match `https://medai.medipol.edu.tr/api/v1/auth/oidc/callback`.

**Skills:** EvoScientist skills installed at `skills/` on the server (from `evoscientist/evoskills`).

**Troubleshooting:**
- Check health: `curl -sk https://medai.medipol.edu.tr/api/v1/health`
- View logs: `docker logs evoscientist`
- DB query: `docker exec evoscientist python3 -c "import sqlite3; c=sqlite3.connect('/data/pm.db')"`

### Adding a new entity

1. Add CREATE TABLE to `db.py` _SCHEMA + migration to _MIGRATIONS
2. Add @dataclass to `models.py`
3. Add Pydantic schemas to `api/schemas.py`
4. Create `crud/{entity}.py` with direct SQL functions (use explicit named params + `_row_to_*()` helpers)
5. Create `api/routes/{entity}.py` with FastAPI routes (use Pydantic schemas + `response_model=` + `log_action()`)
6. Wire in `api/app.py`
7. Create frontend page in `pm/frontend/src/pages/`
8. Add route in `main.tsx`
9. Add API methods in `api.ts`

---

## Behavioral Guidelines

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding
State assumptions. If uncertain, ask. If multiple interpretations exist, present them. If a simpler approach exists, say so.

### 2. Simplicity First
Minimum code that solves the problem. No features beyond what was asked. No abstractions for single-use code.

### 3. Surgical Changes
Touch only what you must. Match existing style. Remove imports/variables YOUR changes made unused. Don't remove pre-existing dead code.

### 4. Goal-Driven Execution
Define success criteria. Loop until verified. For multi-step tasks:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
```
