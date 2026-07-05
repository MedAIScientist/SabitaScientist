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

The **Project Management (PM) module** lives at `EvoScientist/pm/` — a full-stack FastAPI + SQLite + React SPA for running a university research ecosystem.

```
pm/
  api/              # ~50 FastAPI endpoints across 22 route files
    routes/         # Auth, projects, tasks, experiments, publications,
    |               # labs, grants, conferences, IRB, wiki, search, audit,
    |               # drafting, ai_tools, compute, peer_review, bibliography
    audit_middleware.py   # Auto-logs all mutations
    rate_limiter.py       # 200 req/min per IP
    soft_delete.py        # Soft delete helpers
  crud/             # Direct SQL data access (no ORM)
  compute/          # SLURM / SSH / Local compute backends
  s2/               # Semantic Scholar DB queries for citation verification
  runner/           # Async agent runner with SSE streaming
  frontend/         # 27 React pages (Vite + TypeScript)
  templates/        # YAML project templates (life-science, medical, ml-research)
  db.py             # 26 tables, 7 migrations
  models.py         # 25+ dataclasses
  notifications.py  # SMTP email notifications
  oidc.py           # Microsoft O365 SSO / Azure AD OIDC
  auth.py           # bcrypt + token auth
  storage.py        # S3-compatible object storage (Garage)
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

### API Endpoints (~50)

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
| `/audit/logs` | List (admin) | Audit trail |
| `/admin/stats` | System stats | Cross-lab analytics |
| `/pi/stats` | Lab analytics | Mentorship + publications |
| `/export/*` | CSV/JSON | Data export |

### AI-Powered Features

| Endpoint | Agent | What it does |
|---|---|---|
| `POST /projects/{id}/draft-paper` | writing | Full paper from project context |
| `POST /publications/{id}/draft-section` | writing | Abstract, intro, methods, results, etc. |
| `POST /projects/{id}/grant-proposal` | writing | NIH R01, NSF, TÜBİTAK 1001, etc. |
| `POST /projects/{id}/generate-hypothesis` | research | 3-5 testable hypotheses |
| `POST /projects/{id}/research-ideation` | research | Novel research directions |
| `POST /projects/{id}/validate-methodology` | research | Methods review |
| `POST /projects/{id}/verify-citations` | research + S2 DB | Citation verification |
| `POST /projects/{id}/literature-review` | research | Structured lit review |
| `POST /projects/{id}/experiments/{id}/generate-figures` | data_analysis | Publication-quality figures |
| `POST /publications/{id}/respond-to-reviewers` | writing | Reviewer response letter |
| `POST /publications/{id}/revise` | writing | Revise existing text |
| `POST /publications/{id}/generate-ai-review` | research | AI peer review |

### PM Tools (Agent Access)

9 tools registered in the EvoScientist agent (`tools/pm_tools.py`) allowing AI to create projects, tasks, experiments, and entries directly.

### Configuration

| Env Var | Purpose |
|---|---|
| `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET` | Microsoft 365 SSO |
| `OIDC_TENANT_ID` | Azure AD tenant |
| `PM_SMTP_HOST`, `PM_SMTP_USER`, `PM_SMTP_PASS` | Email notifications |
| `S2_DB_PATH` | Semantic Scholar database |
| `RUNNER_URL` | Agent runner URL (default: :8001) |
| `EVOSCIENTIST_PM_DB` | PM database path |
| `GARAGE_S3_ENDPOINT` | S3-compatible storage |

### Deployment

```bash
# Build and run full stack
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.pm.yml up -d

# With SSL
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.pm.yml -f deploy/docker-compose.ssl.yml up -d

# One-command setup on a fresh VPS
bash deploy/setup.sh
```

### Adding a new entity

1. Add CREATE TABLE to `db.py` _SCHEMA + migration to _MIGRATIONS
2. Add @dataclass to `models.py`
3. Add Pydantic schemas to `api/schemas.py`
4. Create `crud/{entity}.py` with direct SQL functions
5. Create `api/routes/{entity}.py` with FastAPI routes
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
