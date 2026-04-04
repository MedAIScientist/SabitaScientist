# Project Management Feature — Design Spec

**Date:** 2026-04-05  
**Status:** Approved  
**Branch:** `feature/multi_project`

---

## 1. Summary

Add a pure collaboration layer to EvoScientist that lets teams sharing a local installation organize work into named **projects**, manage **members** with role-based permissions, and track **tasks** (with deadlines, priorities, and optional links to agent sessions). The feature does not change how the agent runs or where workspace files live.

Accessible via:
- A new **React SPA dashboard** served at `localhost:7860` via `EvoSci dashboard`
- New **CLI slash commands** (`/project`, `/task`, `/user`) that call the same REST API

---

## 2. Architecture

### New package: `EvoScientist/pm/`

```
EvoScientist/
├── pm/
│   ├── __init__.py
│   ├── db.py                  # SQLite connection, schema migrations (projects.db)
│   ├── models.py              # Dataclasses: User, Project, Member, Task, Comment
│   ├── auth.py                # bcrypt password hashing, JWT session tokens
│   ├── crud/
│   │   ├── users.py
│   │   ├── projects.py
│   │   └── tasks.py
│   ├── api/
│   │   ├── app.py             # FastAPI app factory
│   │   ├── deps.py            # current_user dependency, role permission guards
│   │   ├── schemas.py         # Pydantic request/response models
│   │   └── routes/
│   │       ├── auth.py        # POST /auth/login, POST /auth/logout
│   │       ├── users.py       # CRUD /users
│   │       ├── projects.py    # CRUD /projects + member management
│   │       └── tasks.py       # CRUD /projects/{id}/tasks + comments
│   └── frontend/
│       ├── src/               # React 18 + Vite source
│       └── dist/              # Built output — served as StaticFiles by FastAPI
```

### Existing files modified

| File | Change |
|------|--------|
| `EvoScientist/cli/_app.py` | Add `dashboard` Typer subcommand |
| `EvoScientist/commands/` | Add `ProjectCommand`, `TaskCommand`, `UserCommand` |
| `pyproject.toml` | Add `pm` optional dependency group; add `pm/frontend/dist` to package-data |

### Runtime flow

```
EvoSci dashboard
    └── starts uvicorn on localhost:7860
          ├── FastAPI serves React SPA at /
          └── FastAPI serves REST API at /api/v1

CLI slash commands (/project, /task, /user)
    └── httpx calls → REST API (localhost:7860)
          └── reads/writes ~/.config/evoscientist/projects.db
```

The CLI stores the auth token at `~/.config/evoscientist/pm_token` (mode 600). If absent or expired, the CLI prompts for credentials and retries once.

**CLI auto-start:** If a CLI slash command is run and the PM server is not detected on port 7860, the CLI automatically starts the server as a background subprocess (via `subprocess.Popen`) before executing the command. A `~/.config/evoscientist/pm.pid` file tracks the server PID.

**Bootstrap:** On first launch of `EvoSci dashboard` (no users in DB), the React app shows a one-time "Create Admin Account" setup page before the login screen. The first user created is automatically granted `is_admin = true`.

---

## 3. Data Model

Database: `~/.config/evoscientist/projects.db` (separate from `sessions.db`)

```sql
users (
  id            TEXT PRIMARY KEY,   -- uuid4
  username      TEXT UNIQUE NOT NULL,
  email         TEXT UNIQUE,
  password_hash TEXT NOT NULL,       -- bcrypt
  is_admin      BOOLEAN DEFAULT 0,  -- first user created becomes admin
  created_at    TEXT NOT NULL
)

projects (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  description   TEXT,
  created_by    TEXT REFERENCES users(id),
  created_at    TEXT NOT NULL,
  archived_at   TEXT                 -- NULL = active
)

project_members (
  project_id    TEXT REFERENCES projects(id) ON DELETE CASCADE,
  user_id       TEXT REFERENCES users(id) ON DELETE CASCADE,
  role          TEXT NOT NULL,       -- 'owner' | 'editor' | 'viewer'
  added_at      TEXT NOT NULL,
  PRIMARY KEY (project_id, user_id)
)

tasks (
  id            TEXT PRIMARY KEY,
  project_id    TEXT REFERENCES projects(id) ON DELETE CASCADE,
  title         TEXT NOT NULL,
  description   TEXT,
  assignee_id   TEXT REFERENCES users(id) ON DELETE SET NULL,
  status        TEXT NOT NULL DEFAULT 'todo',    -- 'todo' | 'in_progress' | 'done'
  priority      TEXT NOT NULL DEFAULT 'medium',  -- 'high' | 'medium' | 'low'
  deadline      TEXT,               -- ISO date string, nullable
  session_id    TEXT,               -- optional link to sessions.db thread_id
  created_by    TEXT REFERENCES users(id),
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
)

task_comments (
  id            TEXT PRIMARY KEY,
  task_id       TEXT REFERENCES tasks(id) ON DELETE CASCADE,
  author_id     TEXT REFERENCES users(id) ON DELETE SET NULL,
  body          TEXT NOT NULL,
  created_at    TEXT NOT NULL
)

auth_tokens (
  token         TEXT PRIMARY KEY,   -- opaque token (32-byte hex)
  user_id       TEXT REFERENCES users(id) ON DELETE CASCADE,
  expires_at    TEXT NOT NULL
)
```

### Permission matrix

| Action | Owner | Editor | Viewer |
|--------|-------|--------|--------|
| View project & tasks | ✅ | ✅ | ✅ |
| Create / edit / delete tasks | ✅ | ✅ | ❌ |
| Add / delete comments | ✅ | ✅ | ❌ |
| Invite / remove members | ✅ | ❌ | ❌ |
| Change member roles | ✅ | ❌ | ❌ |
| Rename / archive / delete project | ✅ | ❌ | ❌ |

Non-members receive HTTP 403 on all project routes. Only admins can create or delete users.

---

## 4. REST API

Base path: `/api/v1`  
Auth: Bearer token in `Authorization` header (all routes except `/auth/login`).

### Auth
```
POST   /auth/login               body: { username, password } → { token, user }
POST   /auth/logout
```

### Users
```
GET    /users                    admin only — list all users
POST   /users                    admin only — create { username, email, password }
GET    /users/me                 current user profile
PUT    /users/me                 update own password or email
DELETE /users/{id}               admin only
```

### Projects
```
GET    /projects                 projects the caller is a member of
POST   /projects                 create { name, description }
GET    /projects/{id}            project detail + member list
PUT    /projects/{id}            owner only: rename, re-describe, archive
DELETE /projects/{id}            owner only
POST   /projects/{id}/members             owner only: { user_id, role }
PUT    /projects/{id}/members/{user_id}   owner only: change role
DELETE /projects/{id}/members/{user_id}  owner only: remove member
```

### Tasks
```
GET    /projects/{id}/tasks                query: status, assignee_id, priority
POST   /projects/{id}/tasks                owner/editor: create task
GET    /projects/{id}/tasks/{tid}
PUT    /projects/{id}/tasks/{tid}          owner/editor
DELETE /projects/{id}/tasks/{tid}          owner/editor
GET    /projects/{id}/tasks/{tid}/comments
POST   /projects/{id}/tasks/{tid}/comments  owner/editor
DELETE /projects/{id}/tasks/{tid}/comments/{cid}  author or owner
```

All errors return RFC 7807 JSON: `{ detail, status, type }`.

---

## 5. CLI Slash Commands

```
/project list
/project create <name>
/project switch <id|name>        sets active project for the session
/project info
/project invite <username> [--role editor|viewer]

/task list                       tasks in active project
/task add <title> [--assignee <user>] [--deadline YYYY-MM-DD] [--priority high|medium|low]
/task done <id>
/task show <id>

/user list                       admin only
/user create <username>          admin only, prompts for password
```

---

## 6. Frontend (React SPA)

**Stack:** React 18, Vite, TanStack Query, React Router, shadcn/ui  
**Build output:** `EvoScientist/pm/frontend/dist/` (served as FastAPI `StaticFiles`)

### Views

| Route | Description |
|-------|-------------|
| `/login` | Username/password form; stores token in memory + httpOnly cookie |
| `/projects` | Project list cards; "New Project" button |
| `/projects/:id` | Kanban board — 3 columns (Todo / In Progress / Done); tasks are draggable cards showing assignee avatar, priority badge, deadline; sidebar shows member list with roles and "Invite" button (owner only) |
| `/projects/:id/tasks/:tid` | Task detail drawer — description, comments thread, inline edit form; if `session_id` is set, shows a read-only "Linked Session" chip displaying the thread ID with a copy button (no in-browser session replay — the link is informational, pointing the user to resume that session in the CLI) |

---

## 7. Error Handling

- **401** → frontend redirects to `/login`; CLI re-prompts and retries once
- **403** → shown as a permission error, no redirect
- **Network errors (CLI)** → human-readable message, no stack trace exposed
- **DB errors** → logged at `ERROR` level, API returns HTTP 500 with a generic message (no internals leaked)

---

## 8. Testing

- **Backend unit tests** — pytest, test CRUD functions directly against an in-memory SQLite DB; no HTTP layer
- **Backend integration tests** — `httpx.AsyncClient` against the FastAPI app with a temp DB; covers all routes and permission rules
- **Frontend** — Vitest + React Testing Library; component-level only
- **CLI commands** — `httpx` responses mocked with `pytest-mock`; follows existing channel test patterns
- All tests runnable with `uv run pytest`; no API keys needed

---

## 9. New Dependencies

| Dependency | Purpose | Optional group |
|------------|---------|----------------|
| `fastapi>=0.115` | REST API framework | `pm` |
| `uvicorn[standard]>=0.30` | ASGI server for dashboard | `pm` |
| `bcrypt>=4.0` | Password hashing | `pm` |
| `pyjwt>=2.8` | JWT tokens | `pm` |
| Node.js + npm | Frontend build (dev only, not shipped) | — |

Install PM extras: `uv pip install "EvoScientist[pm]"`

---

## 10. Out of Scope

- Email notifications for deadlines or assignments
- OAuth / SSO login
- Real-time updates (WebSocket) — polling via TanStack Query is sufficient
- Mobile channel integration for PM commands
- Self-registration (admin creates all accounts)
