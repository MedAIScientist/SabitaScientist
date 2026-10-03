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

# Run Gazzali locally (API + SPA on :7860, AI runner on :8001)
uv run python -m gazzali --host 0.0.0.0
```

## Gazzali Architecture

The **Project Management (PM) module** lives at `gazzali/` — a full-stack FastAPI + SQLite + React SPA for running a university research ecosystem. It runs standalone: it imports nothing from the rest of the EvoScientist package (see "Standalone PM" below).

```
gazzali/
  settings.py       # Paths + config from env vars
  _ai.py            # Direct LLM (OpenAI-compatible endpoint) + skill guidance
  agent_tools.py    # Copilot tools
  __main__.py       # python -m gazzali
  api/              # ~65 FastAPI endpoints across 30 route files
    routes/         # Auth, projects, tasks, experiments, publications,
    |               # labs, grants, conferences, IRB, wiki, search, audit,
    |               # drafting, ai_tools, compute, peer_review, bibliography,
    |               # dashboard, copilot, supervision, ...
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
  db.py             # 26 tables, 7 migrations (path via GAZZALI_PM_DB or GAZZALI_DATA_DIR)
  models.py         # 25+ dataclasses
  notifications.py  # Email (EMAIL_SMTP_* env vars)
  oidc.py           # Microsoft O365 SSO (OIDC_* env vars)
  auth.py           # bcrypt + token auth
  storage.py        # S3-compatible object storage (GARAGE_* env vars)
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
| `/system/health` | Health check | AI models, keys configured, skills count |

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
| `POST /projects/{id}/experiments/{id}/generate-figures` | **direct LLM** | Publication-quality figures |
| `POST /publications/{id}/respond-to-reviewers` | runner | Reviewer response letter |
| `POST /publications/{id}/revise` | runner | Revise existing text |
| `POST /publications/{id}/generate-ai-review` | runner | AI peer review |

AI endpoints can load SKILL.md files (from `skills/` dirs) for guidance.
Direct LLM endpoints use `gazzali/_ai.py` (one OpenAI-compatible endpoint; NVIDIA by default).

### Runtime

Gazzali is a standalone package (it began as EvoScientist's PM module; the
EvoScientist core was removed). Production starts it with
`python -m gazzali --host 0.0.0.0`.

| Module | What it provides |
|---|---|
| `gazzali/settings.py` | Paths + all settings from env vars |
| `gazzali/_ai.py` | `ChatOpenAI` on one OpenAI-compatible endpoint: `PM_LLM_BASE_URL` (default NVIDIA `integrate.api.nvidia.com`), `PM_LLM_MODEL` (default `nvidia/nemotron-3-ultra-550b-a55b`, falls back to `PM_LLM_FALLBACK_MODELS`, default `nvidia/nemotron-3.5-lightning-30b-a3b`, on 404/410), `PM_LLM_API_KEY` (default `NVIDIA_API_KEY`); the free key allows ~40 requests/minute shared by everything |
| `gazzali/agent_tools.py` | Copilot tools (permission-checked) |
| `gazzali/__main__.py` | Entrypoint |

### AutoResearchClaw (computational experiments)

Plan: `plan/autoresearchclaw-integration.md` (arXiv:2605.20025). The `researchclaw`
compose service (`deploy/researchclaw/`, internal only, CPU, ARC pinned) runs
pipelines; `gazzali/research_claw.py` talks to it (`ARC_WORKER_URL`, `ARC_WORKER_TOKEN`).
Routes in `api/routes/research_runs.py`; table `research_runs` mirrors a run and is
refreshed whenever it is read. CoPilot is the default mode. Gates before stage 14 are
decided by the project owner/editor, from stage 14 on by a lab PI. Dataset runs need
an approved, unexpired IRB of the project. Finished runs import ARC's verified numbers
into `experiment_metrics` and lessons into the lab's `research_lessons`.

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
| `/health` | SystemHealthPage | AI models, skills, runner status |
| `/analytics` | AnalyticsPage | Cross-lab stats |
| `/admin` | AdminDashboard | System-wide admin |
| `/users` | UsersPage | User CRUD |
| `/profile` | ProfilePage | User settings |
| `/reports` | GlobalReportPage | Aggregate reports |

### PM Tools (Agent Access)

The copilot's tools live in `gazzali/agent_tools.py`: they read and (after user confirmation) create projects, tasks, experiments, entries, papers and labs, re-checking the signed-in user's permissions.

### Configuration

All PM configuration is read from environment variables in `gazzali/settings.py` (no config.yaml).

| Config Field | Env Var | Purpose |
|---|---|---|
| `pm_db_path` | `GAZZALI_PM_DB` | PM SQLite DB path |
| `pm_runner_url` | `PM_RUNNER_URL` | Agent runner URL (default: :8001) |
| `pm_base_url` | `PM_BASE_URL` | PM web UI base URL |
| `pm_smtp_from` | `PM_SMTP_FROM` | Notification sender address |
| `pm_max_upload_mb` | `PM_MAX_UPLOAD_MB` | Max attachment upload size |
| `pm_garage_*` | `GARAGE_*` | S3/Garage object storage |
| `pm_oidc_*` | `OIDC_*` | Microsoft 365 SSO |
| `pm_s2_db_path` | `S2_DB_PATH` | Semantic Scholar citation DB |
| `email_smtp_*` | `EMAIL_SMTP_HOST/PORT/USERNAME/PASSWORD/USE_TLS` | Notification e-mail |

### Deployment

Production server: `medaiadm@medai-prod` (Tailscale; the raw IP 10.150.145.10 times out on port 22) — domain `https://medai.medipol.edu.tr`
Uses Docker Compose on bare metal (no Swarm/K8s). Compose project `gazzali`; three containers: `gazzali`, `gazzali-garage`, `gazzali-nginx`.

**IMPORTANT — deploy ONLY via the deploy script. Never run ad-hoc Docker commands.**

```bash
# Deploy to production (syncs code → builds Docker → restarts container)
./deploy/deploy.sh medaiadm@medai-prod
```

The deploy script handles:
1. **Rsync** — syncs source code (excluding .git, node_modules, .venv, .env, etc.)
2. **SSL check** — verifies certs at `deploy/nginx/ssl/`
3. **Docker build** — builds `gazzali:prod` image (uses cache, no `--no-cache`)
4. **Deploy** — recreates the gazzali container (garage + nginx stay up), waits for healthy

**Services:**

| Container | Image | Ports |
|-----------|-------|-------|
| gazzali | gazzali:prod | 7860 (API + SPA), 8001 (runner) |
| gazzali-garage | dxflrs/garage:v1.0.1 | 3900 (S3) |
| gazzali-nginx | nginx:alpine | 80 → 443 → gazzali:7860 |

**Compose file:** `deploy/docker-compose.prod.yml` (single unified file)

**Data volumes:** `gazzali_gazzali-data` (/data with pm.db + workspaces), `gazzali_gazzali-home`, `gazzali_garage-data`

**Secrets:** `.env` at project root + `deploy/.env` (deploy overrides root). SSL certs at `deploy/nginx/ssl/`.

**OIDC / Microsoft SSO:** Azure App with Client ID `991f879e-3b91-4d8f-850d-0b2ad468c976`. Redirect URI must match `https://medai.medipol.edu.tr/api/v1/auth/oidc/callback`.

**Skills:** SKILL.md files under `skills/` on the server (and `~/.gazzali/skills` in the container).

**Troubleshooting:**
- Check health: `curl -sk https://medai.medipol.edu.tr/api/v1/health`
- View logs: `docker logs gazzali`
- DB query: `docker exec gazzali python3 -c "import sqlite3; c=sqlite3.connect('/data/pm.db')"`

### Adding a new entity

1. Add CREATE TABLE to `db.py` _SCHEMA + migration to _MIGRATIONS
2. Add @dataclass to `models.py`
3. Add Pydantic schemas to `api/schemas.py`
4. Create `crud/{entity}.py` with direct SQL functions (use explicit named params + `_row_to_*()` helpers)
5. Create `api/routes/{entity}.py` with FastAPI routes (use Pydantic schemas + `response_model=` + `log_action()`)
6. Wire in `api/app.py`
7. Create frontend page in `gazzali/frontend/src/pages/`
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
