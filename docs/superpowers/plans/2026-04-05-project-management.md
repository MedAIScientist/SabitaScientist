# Project Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collaboration layer (projects, members with roles, research-flavored tasks) to EvoScientist, accessible via a FastAPI REST API + React SPA dashboard and CLI slash commands.

**Architecture:** A new `EvoScientist/pm/` package owns all PM logic — SQLite DB (`~/.config/evoscientist/projects.db`), models, auth (opaque tokens + bcrypt), CRUD, and a FastAPI app. The React SPA is built to `pm/frontend/dist/` and served as static files. CLI slash commands call the REST API via `httpx`, auto-starting the server if needed.

**Tech Stack:** Python 3.11+, sqlite3 (stdlib), FastAPI, uvicorn, bcrypt, React 18, Vite, TanStack Query, httpx (already a dependency)

> **Note:** The spec lists shadcn/ui in the tech stack. This plan uses inline styles instead — shadcn/ui requires running its CLI scaffolding tool which adds significant setup overhead for a local tool. The UI can be migrated to shadcn/ui as a follow-on task without touching any backend code.

**Spec:** `docs/superpowers/specs/2026-04-05-project-management-design.md`

---

## File Map

### New files (backend)
| File | Responsibility |
|------|----------------|
| `EvoScientist/pm/__init__.py` | Package exports |
| `EvoScientist/pm/db.py` | SQLite connection, schema creation/migration |
| `EvoScientist/pm/models.py` | Dataclasses: User, Project, Member, Task, Comment |
| `EvoScientist/pm/auth.py` | bcrypt hashing, opaque token create/validate |
| `EvoScientist/pm/crud/__init__.py` | Empty |
| `EvoScientist/pm/crud/users.py` | User CRUD |
| `EvoScientist/pm/crud/projects.py` | Project + member CRUD |
| `EvoScientist/pm/crud/tasks.py` | Task + comment CRUD |
| `EvoScientist/pm/api/__init__.py` | Empty |
| `EvoScientist/pm/api/schemas.py` | Pydantic request/response models |
| `EvoScientist/pm/api/deps.py` | `get_current_user`, `require_role` dependencies |
| `EvoScientist/pm/api/app.py` | FastAPI app factory |
| `EvoScientist/pm/api/routes/__init__.py` | Empty |
| `EvoScientist/pm/api/routes/auth.py` | `/auth/login`, `/auth/logout` |
| `EvoScientist/pm/api/routes/users.py` | `/users` CRUD |
| `EvoScientist/pm/api/routes/projects.py` | `/projects` CRUD + members |
| `EvoScientist/pm/api/routes/tasks.py` | `/projects/{id}/tasks` + comments |

### New files (CLI + dashboard)
| File | Responsibility |
|------|----------------|
| `EvoScientist/commands/pm_commands.py` | `/project`, `/task`, `/user` slash commands |
| `EvoScientist/pm/server.py` | Auto-start server subprocess helper |

### New files (frontend)
| File | Responsibility |
|------|----------------|
| `EvoScientist/pm/frontend/package.json` | Node dependencies |
| `EvoScientist/pm/frontend/vite.config.ts` | Vite build config |
| `EvoScientist/pm/frontend/src/main.tsx` | React entry point |
| `EvoScientist/pm/frontend/src/api.ts` | Typed API client (fetch wrappers) |
| `EvoScientist/pm/frontend/src/auth.tsx` | Auth context provider |
| `EvoScientist/pm/frontend/src/pages/Login.tsx` | Login page |
| `EvoScientist/pm/frontend/src/pages/Projects.tsx` | Project list |
| `EvoScientist/pm/frontend/src/pages/Board.tsx` | Kanban board |
| `EvoScientist/pm/frontend/src/pages/TaskDetail.tsx` | Task detail drawer |

### Modified files
| File | Change |
|------|--------|
| `EvoScientist/cli/_app.py` | Add `dashboard_app` Typer subcommand group |
| `EvoScientist/cli/interactive.py` | Register `pm_commands` |
| `pyproject.toml` | Add `pm` optional dep group + package-data |

### New test files
| File | What it tests |
|------|---------------|
| `tests/pm/__init__.py` | Empty |
| `tests/pm/conftest.py` | Shared fixtures: temp DB, test client, seeded users |
| `tests/pm/test_db.py` | Schema creation, migration idempotency |
| `tests/pm/test_auth.py` | Password hashing, token create/validate/expire |
| `tests/pm/test_crud_users.py` | User CRUD happy path + uniqueness constraint |
| `tests/pm/test_crud_projects.py` | Project + member CRUD, role changes |
| `tests/pm/test_crud_tasks.py` | Task + comment CRUD, deadline/priority |
| `tests/pm/test_api_auth.py` | Login/logout, bad creds → 401 |
| `tests/pm/test_api_users.py` | User routes, admin-only enforcement |
| `tests/pm/test_api_projects.py` | Project routes, permission matrix |
| `tests/pm/test_api_tasks.py` | Task routes, comment routes, permission matrix |
| `tests/pm/test_pm_commands.py` | CLI slash commands with mocked httpx |

---

## Phase 1: Backend

---

### Task 1: pyproject.toml + package scaffold

**Files:**
- Modify: `pyproject.toml`
- Create: `EvoScientist/pm/__init__.py`
- Create: `EvoScientist/pm/crud/__init__.py`
- Create: `EvoScientist/pm/api/__init__.py`
- Create: `EvoScientist/pm/api/routes/__init__.py`

- [ ] **Step 1: Add `pm` optional dependency group to `pyproject.toml`**

Find the `[project.optional-dependencies]` section and add:

```toml
pm = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "bcrypt>=4.0",
]
```

Then add `pm/frontend/dist` to `[tool.setuptools.package-data]`:

```toml
[tool.setuptools.package-data]
EvoScientist = ["subagent.yaml", "skills/**/*", "pm/frontend/dist/**/*"]
```

- [ ] **Step 2: Create empty `__init__.py` files**

`EvoScientist/pm/__init__.py`:
```python
"""EvoScientist Project Management module."""
```

`EvoScientist/pm/crud/__init__.py` — empty file.

`EvoScientist/pm/api/__init__.py` — empty file.

`EvoScientist/pm/api/routes/__init__.py` — empty file.

- [ ] **Step 3: Install PM dependencies**

```bash
uv sync --dev
uv pip install ".[pm]"
```

Expected: no errors, `fastapi`, `uvicorn`, `bcrypt` importable.

- [ ] **Step 4: Verify imports work**

```bash
python -c "import fastapi, uvicorn, bcrypt; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml EvoScientist/pm/
git commit -m "feat(pm): scaffold pm package and add optional dependencies"
```

---

### Task 2: DB schema

**Files:**
- Create: `EvoScientist/pm/db.py`
- Create: `tests/pm/__init__.py`
- Create: `tests/pm/conftest.py`
- Create: `tests/pm/test_db.py`

- [ ] **Step 1: Write the failing tests**

`tests/pm/__init__.py` — empty file.

`tests/pm/conftest.py`:
```python
"""Shared fixtures for PM tests."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from EvoScientist.pm.db import create_schema, get_db


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Return path to a fresh temporary projects.db."""
    db_path = tmp_path / "projects.db"
    create_schema(db_path)
    return db_path


@pytest.fixture
def db_conn(tmp_db: Path):
    """Yield an open sqlite3 connection to a fresh DB."""
    conn = sqlite3.connect(tmp_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()
```

`tests/pm/test_db.py`:
```python
"""Tests for PM database schema creation."""
import sqlite3
from pathlib import Path

from EvoScientist.pm.db import create_schema


def test_create_schema_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cur.fetchall()}
    conn.close()

    assert tables == {"auth_tokens", "project_members", "projects", "task_comments", "tasks", "users"}


def test_create_schema_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    create_schema(db_path)  # second call must not raise

    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    assert len(cur.fetchall()) == 6
    conn.close()


def test_foreign_keys_enforced(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO projects (id, name, created_by, created_at) VALUES (?, ?, ?, ?)",
            ("p1", "Test", "nonexistent-user-id", "2026-01-01T00:00:00"),
        )
    conn.close()


import pytest
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/pm/test_db.py -v
```

Expected: `ModuleNotFoundError: No module named 'EvoScientist.pm.db'`

- [ ] **Step 3: Implement `EvoScientist/pm/db.py`**

```python
"""SQLite connection and schema management for the PM module."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    email         TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT,
    created_by    TEXT REFERENCES users(id),
    created_at    TEXT NOT NULL,
    archived_at   TEXT
);

CREATE TABLE IF NOT EXISTS project_members (
    project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role          TEXT NOT NULL CHECK(role IN ('owner', 'editor', 'viewer')),
    added_at      TEXT NOT NULL,
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id            TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    description   TEXT,
    assignee_id   TEXT REFERENCES users(id) ON DELETE SET NULL,
    status        TEXT NOT NULL DEFAULT 'todo'
                  CHECK(status IN ('todo', 'in_progress', 'done')),
    priority      TEXT NOT NULL DEFAULT 'medium'
                  CHECK(priority IN ('high', 'medium', 'low')),
    deadline      TEXT,
    session_id    TEXT,
    created_by    TEXT REFERENCES users(id),
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_comments (
    id            TEXT PRIMARY KEY,
    task_id       TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    author_id     TEXT REFERENCES users(id) ON DELETE SET NULL,
    body          TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token         TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at    TEXT NOT NULL
);
"""


def get_db_path() -> Path:
    """Return path to the PM SQLite database, creating parent dirs."""
    db_dir = Path.home() / ".config" / "evoscientist"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "projects.db"


def create_schema(db_path: Path | None = None) -> None:
    """Create all PM tables if they don't already exist (idempotent)."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db(db_path: Path | None = None):
    """Yield a sqlite3 connection with foreign keys enabled and Row factory set."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/pm/test_db.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/db.py tests/pm/
git commit -m "feat(pm): add SQLite schema and DB connection helpers"
```

---

### Task 3: Data models

**Files:**
- Create: `EvoScientist/pm/models.py`

- [ ] **Step 1: Create `EvoScientist/pm/models.py`**

No separate test file needed — models are plain dataclasses verified implicitly by CRUD tests.

```python
"""Dataclasses representing PM domain entities."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class User:
    id: str
    username: str
    password_hash: str
    is_admin: bool
    created_at: str
    email: str | None = None


@dataclass
class Project:
    id: str
    name: str
    created_by: str
    created_at: str
    description: str | None = None
    archived_at: str | None = None


@dataclass
class Member:
    project_id: str
    user_id: str
    role: str          # 'owner' | 'editor' | 'viewer'
    added_at: str


@dataclass
class Task:
    id: str
    project_id: str
    title: str
    created_by: str
    created_at: str
    updated_at: str
    description: str | None = None
    assignee_id: str | None = None
    status: str = "todo"           # 'todo' | 'in_progress' | 'done'
    priority: str = "medium"       # 'high' | 'medium' | 'low'
    deadline: str | None = None    # ISO date string
    session_id: str | None = None  # optional link to sessions.db thread_id


@dataclass
class Comment:
    id: str
    task_id: str
    body: str
    created_at: str
    author_id: str | None = None
```

- [ ] **Step 2: Commit**

```bash
git add EvoScientist/pm/models.py
git commit -m "feat(pm): add domain model dataclasses"
```

---

### Task 4: Auth utilities

**Files:**
- Create: `EvoScientist/pm/auth.py`
- Create: `tests/pm/test_auth.py`

- [ ] **Step 1: Write failing tests**

`tests/pm/test_auth.py`:
```python
"""Tests for PM auth utilities."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from EvoScientist.pm.auth import (
    create_token,
    hash_password,
    validate_token,
    verify_password,
)
from EvoScientist.pm.db import create_schema, get_db


def test_hash_password_returns_string() -> None:
    hashed = hash_password("mysecret")
    assert isinstance(hashed, str)
    assert hashed != "mysecret"


def test_verify_password_correct() -> None:
    hashed = hash_password("mysecret")
    assert verify_password("mysecret", hashed) is True


def test_verify_password_wrong() -> None:
    hashed = hash_password("mysecret")
    assert verify_password("wrongpassword", hashed) is False


def test_create_token_length() -> None:
    token = create_token()
    assert len(token) == 64  # 32 bytes hex = 64 chars


def test_create_token_unique() -> None:
    assert create_token() != create_token()


def test_validate_token_valid(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    # Insert a user and a valid token
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?, ?)",
            ("u1", "alice", "hash", 0, "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            ("tok123", "u1", future),
        )

    result = validate_token("tok123", db_path)
    assert result == "u1"


def test_validate_token_expired(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)

    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?, ?)",
            ("u1", "alice", "hash", 0, "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            ("tok_old", "u1", past),
        )

    assert validate_token("tok_old", db_path) is None


def test_validate_token_unknown(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    assert validate_token("doesnotexist", db_path) is None
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/pm/test_auth.py -v
```

Expected: `ModuleNotFoundError: No module named 'EvoScientist.pm.auth'`

- [ ] **Step 3: Implement `EvoScientist/pm/auth.py`**

```python
"""Authentication utilities: password hashing and opaque session tokens."""
from __future__ import annotations

import secrets
from datetime import UTC, datetime
from pathlib import Path

import bcrypt

from .db import get_db


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Return True if *password* matches *hashed*."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token() -> str:
    """Generate a cryptographically secure 64-char hex token."""
    return secrets.token_hex(32)


def validate_token(token: str, db_path: Path | None = None) -> str | None:
    """Return user_id if *token* exists and is not expired, else None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT user_id, expires_at FROM auth_tokens WHERE token = ?",
            (token,),
        ).fetchone()
    if not row:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if datetime.now(UTC) > expires_at:
        return None
    return row["user_id"]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/pm/test_auth.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/auth.py tests/pm/test_auth.py
git commit -m "feat(pm): add password hashing and opaque token auth"
```

---

### Task 5: User CRUD

**Files:**
- Create: `EvoScientist/pm/crud/users.py`
- Create: `tests/pm/test_crud_users.py`

- [ ] **Step 1: Write failing tests**

`tests/pm/test_crud_users.py`:
```python
"""Tests for user CRUD operations."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from EvoScientist.pm.crud.users import (
    create_user,
    delete_user,
    get_user_by_id,
    get_user_by_username,
    list_users,
    update_user_password,
)
from EvoScientist.pm.db import create_schema


@pytest.fixture
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    return db_path


def test_create_user_and_retrieve(db: Path) -> None:
    user = create_user(db, username="alice", password_hash="hash_a", is_admin=True)
    assert user.id is not None
    assert user.username == "alice"
    assert user.is_admin is True

    fetched = get_user_by_id(db, user.id)
    assert fetched is not None
    assert fetched.username == "alice"


def test_get_user_by_username(db: Path) -> None:
    create_user(db, username="bob", password_hash="hash_b")
    user = get_user_by_username(db, "bob")
    assert user is not None
    assert user.username == "bob"


def test_get_user_by_username_missing(db: Path) -> None:
    assert get_user_by_username(db, "ghost") is None


def test_duplicate_username_raises(db: Path) -> None:
    create_user(db, username="carol", password_hash="h")
    with pytest.raises(sqlite3.IntegrityError):
        create_user(db, username="carol", password_hash="h2")


def test_list_users(db: Path) -> None:
    create_user(db, username="u1", password_hash="h1")
    create_user(db, username="u2", password_hash="h2")
    users = list_users(db)
    assert len(users) == 2
    assert {u.username for u in users} == {"u1", "u2"}


def test_delete_user(db: Path) -> None:
    user = create_user(db, username="dave", password_hash="hd")
    assert delete_user(db, user.id) is True
    assert get_user_by_id(db, user.id) is None


def test_delete_nonexistent_user(db: Path) -> None:
    assert delete_user(db, "no-such-id") is False


def test_update_user_password(db: Path) -> None:
    user = create_user(db, username="eve", password_hash="old_hash")
    update_user_password(db, user.id, "new_hash")
    fetched = get_user_by_id(db, user.id)
    assert fetched.password_hash == "new_hash"
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/pm/test_crud_users.py -v
```

Expected: `ModuleNotFoundError: No module named 'EvoScientist.pm.crud.users'`

- [ ] **Step 3: Implement `EvoScientist/pm/crud/users.py`**

```python
"""CRUD operations for User entities."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import User


def create_user(
    db_path: Path,
    username: str,
    password_hash: str,
    email: str | None = None,
    is_admin: bool = False,
) -> User:
    """Insert a new user and return the created User."""
    user_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO users (id, username, email, password_hash, is_admin, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, email, password_hash, int(is_admin), now),
        )
    return User(
        id=user_id,
        username=username,
        email=email,
        password_hash=password_hash,
        is_admin=is_admin,
        created_at=now,
    )


def get_user_by_id(db_path: Path, user_id: str) -> User | None:
    """Return User by primary key, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id, username, email, password_hash, is_admin, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_username(db_path: Path, username: str) -> User | None:
    """Return User by username, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id, username, email, password_hash, is_admin, created_at FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return _row_to_user(row) if row else None


def list_users(db_path: Path) -> list[User]:
    """Return all users ordered by username."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, username, email, password_hash, is_admin, created_at FROM users ORDER BY username",
        ).fetchall()
    return [_row_to_user(r) for r in rows]


def delete_user(db_path: Path, user_id: str) -> bool:
    """Delete a user by id. Returns True if a row was deleted."""
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return cur.rowcount > 0


def update_user_password(db_path: Path, user_id: str, new_hash: str) -> None:
    """Update the password_hash for a user."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (new_hash, user_id),
        )


def _row_to_user(row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        is_admin=bool(row["is_admin"]),
        created_at=row["created_at"],
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/pm/test_crud_users.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/crud/users.py tests/pm/test_crud_users.py
git commit -m "feat(pm): add user CRUD"
```

---

### Task 6: Project + member CRUD

**Files:**
- Create: `EvoScientist/pm/crud/projects.py`
- Create: `tests/pm/test_crud_projects.py`

- [ ] **Step 1: Write failing tests**

`tests/pm/test_crud_projects.py`:
```python
"""Tests for project and member CRUD."""
from __future__ import annotations

from pathlib import Path

import pytest

from EvoScientist.pm.crud.projects import (
    add_member,
    create_project,
    delete_project,
    get_member_role,
    get_project,
    list_projects_for_user,
    remove_member,
    update_member_role,
    update_project,
)
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.db import create_schema


@pytest.fixture
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    return db_path


@pytest.fixture
def owner(db: Path):
    return create_user(db, username="owner", password_hash="h")


@pytest.fixture
def editor(db: Path):
    return create_user(db, username="editor", password_hash="h")


def test_create_and_get_project(db: Path, owner) -> None:
    project = create_project(db, name="Alpha", created_by=owner.id)
    assert project.id is not None
    assert project.name == "Alpha"

    fetched = get_project(db, project.id)
    assert fetched is not None
    assert fetched.name == "Alpha"


def test_get_project_missing(db: Path) -> None:
    assert get_project(db, "no-such-id") is None


def test_create_project_auto_adds_owner_member(db: Path, owner) -> None:
    project = create_project(db, name="Beta", created_by=owner.id)
    role = get_member_role(db, project.id, owner.id)
    assert role == "owner"


def test_list_projects_for_user(db: Path, owner, editor) -> None:
    p1 = create_project(db, name="P1", created_by=owner.id)
    p2 = create_project(db, name="P2", created_by=owner.id)
    add_member(db, project_id=p1.id, user_id=editor.id, role="editor")

    owner_projects = {p.id for p in list_projects_for_user(db, owner.id)}
    editor_projects = {p.id for p in list_projects_for_user(db, editor.id)}

    assert {p1.id, p2.id} == owner_projects
    assert editor_projects == {p1.id}


def test_add_and_remove_member(db: Path, owner, editor) -> None:
    project = create_project(db, name="Gamma", created_by=owner.id)
    add_member(db, project_id=project.id, user_id=editor.id, role="editor")
    assert get_member_role(db, project.id, editor.id) == "editor"

    remove_member(db, project_id=project.id, user_id=editor.id)
    assert get_member_role(db, project.id, editor.id) is None


def test_update_member_role(db: Path, owner, editor) -> None:
    project = create_project(db, name="Delta", created_by=owner.id)
    add_member(db, project_id=project.id, user_id=editor.id, role="editor")
    update_member_role(db, project_id=project.id, user_id=editor.id, role="viewer")
    assert get_member_role(db, project.id, editor.id) == "viewer"


def test_update_project(db: Path, owner) -> None:
    project = create_project(db, name="Epsilon", created_by=owner.id)
    updated = update_project(db, project.id, name="Epsilon v2", description="New desc")
    assert updated.name == "Epsilon v2"
    assert updated.description == "New desc"


def test_delete_project(db: Path, owner) -> None:
    project = create_project(db, name="Zeta", created_by=owner.id)
    assert delete_project(db, project.id) is True
    assert get_project(db, project.id) is None


def test_get_member_role_nonmember(db: Path, owner, editor) -> None:
    project = create_project(db, name="Eta", created_by=owner.id)
    assert get_member_role(db, project.id, editor.id) is None
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/pm/test_crud_projects.py -v
```

Expected: `ModuleNotFoundError: No module named 'EvoScientist.pm.crud.projects'`

- [ ] **Step 3: Implement `EvoScientist/pm/crud/projects.py`**

```python
"""CRUD operations for Project and Member entities."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Member, Project


def create_project(
    db_path: Path,
    name: str,
    created_by: str,
    description: str | None = None,
) -> Project:
    """Create a project and automatically add creator as owner."""
    project_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description, created_by, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, name, description, created_by, now),
        )
        conn.execute(
            "INSERT INTO project_members (project_id, user_id, role, added_at) VALUES (?, ?, ?, ?)",
            (project_id, created_by, "owner", now),
        )
    return Project(
        id=project_id,
        name=name,
        description=description,
        created_by=created_by,
        created_at=now,
    )


def get_project(db_path: Path, project_id: str) -> Project | None:
    """Return Project by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id, name, description, created_by, created_at, archived_at FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    return _row_to_project(row) if row else None


def list_projects_for_user(db_path: Path, user_id: str) -> list[Project]:
    """Return all non-archived projects the user is a member of."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT p.id, p.name, p.description, p.created_by, p.created_at, p.archived_at
               FROM projects p
               JOIN project_members pm ON p.id = pm.project_id
               WHERE pm.user_id = ? AND p.archived_at IS NULL
               ORDER BY p.created_at DESC""",
            (user_id,),
        ).fetchall()
    return [_row_to_project(r) for r in rows]


def add_member(db_path: Path, project_id: str, user_id: str, role: str) -> Member:
    """Add a user to a project with the given role."""
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO project_members (project_id, user_id, role, added_at) VALUES (?, ?, ?, ?)",
            (project_id, user_id, role, now),
        )
    return Member(project_id=project_id, user_id=user_id, role=role, added_at=now)


def remove_member(db_path: Path, project_id: str, user_id: str) -> bool:
    """Remove a user from a project. Returns True if removed."""
    with get_db(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        )
    return cur.rowcount > 0


def update_member_role(db_path: Path, project_id: str, user_id: str, role: str) -> None:
    """Change the role of an existing member."""
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE project_members SET role = ? WHERE project_id = ? AND user_id = ?",
            (role, project_id, user_id),
        )


def get_member_role(db_path: Path, project_id: str, user_id: str) -> str | None:
    """Return the role of user_id in project_id, or None if not a member."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        ).fetchone()
    return row["role"] if row else None


def update_project(
    db_path: Path,
    project_id: str,
    name: str | None = None,
    description: str | None = None,
    archived_at: str | None = None,
) -> Project:
    """Update project fields. Omitted fields are unchanged."""
    project = get_project(db_path, project_id)
    if project is None:
        raise ValueError(f"Project {project_id!r} not found")
    new_name = name if name is not None else project.name
    new_desc = description if description is not None else project.description
    new_archived = archived_at if archived_at is not None else project.archived_at
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE projects SET name = ?, description = ?, archived_at = ? WHERE id = ?",
            (new_name, new_desc, new_archived, project_id),
        )
    project.name = new_name
    project.description = new_desc
    project.archived_at = new_archived
    return project


def delete_project(db_path: Path, project_id: str) -> bool:
    """Delete a project and cascade to members/tasks. Returns True if deleted."""
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return cur.rowcount > 0


def _row_to_project(row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        archived_at=row["archived_at"],
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/pm/test_crud_projects.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/crud/projects.py tests/pm/test_crud_projects.py
git commit -m "feat(pm): add project and member CRUD"
```

---

### Task 7: Task + comment CRUD

**Files:**
- Create: `EvoScientist/pm/crud/tasks.py`
- Create: `tests/pm/test_crud_tasks.py`

- [ ] **Step 1: Write failing tests**

`tests/pm/test_crud_tasks.py`:
```python
"""Tests for task and comment CRUD."""
from __future__ import annotations

from pathlib import Path

import pytest

from EvoScientist.pm.crud.projects import create_project
from EvoScientist.pm.crud.tasks import (
    create_comment,
    create_task,
    delete_comment,
    delete_task,
    get_task,
    list_comments,
    list_tasks,
    update_task,
)
from EvoScientist.pm.crud.users import create_user
from EvoScientist.pm.db import create_schema


@pytest.fixture
def db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    create_schema(db_path)
    return db_path


@pytest.fixture
def setup(db: Path):
    user = create_user(db, username="u1", password_hash="h")
    project = create_project(db, name="TestProject", created_by=user.id)
    return db, user, project


def test_create_and_get_task(setup) -> None:
    db, user, project = setup
    task = create_task(db, project_id=project.id, title="Write paper", created_by=user.id)
    assert task.id is not None
    assert task.status == "todo"
    assert task.priority == "medium"

    fetched = get_task(db, task.id)
    assert fetched is not None
    assert fetched.title == "Write paper"


def test_create_task_with_all_fields(setup) -> None:
    db, user, project = setup
    task = create_task(
        db,
        project_id=project.id,
        title="Run experiment",
        created_by=user.id,
        description="Train baseline model",
        assignee_id=user.id,
        priority="high",
        deadline="2026-05-01",
        session_id="abc123",
    )
    assert task.priority == "high"
    assert task.deadline == "2026-05-01"
    assert task.session_id == "abc123"


def test_list_tasks_filter_by_status(setup) -> None:
    db, user, project = setup
    create_task(db, project_id=project.id, title="T1", created_by=user.id)
    t2 = create_task(db, project_id=project.id, title="T2", created_by=user.id)
    update_task(db, t2.id, status="in_progress")

    todo = list_tasks(db, project_id=project.id, status="todo")
    in_prog = list_tasks(db, project_id=project.id, status="in_progress")
    assert len(todo) == 1
    assert len(in_prog) == 1


def test_update_task(setup) -> None:
    db, user, project = setup
    task = create_task(db, project_id=project.id, title="Draft", created_by=user.id)
    updated = update_task(db, task.id, title="Final Draft", status="done", priority="low")
    assert updated.title == "Final Draft"
    assert updated.status == "done"
    assert updated.priority == "low"


def test_delete_task(setup) -> None:
    db, user, project = setup
    task = create_task(db, project_id=project.id, title="Temp", created_by=user.id)
    assert delete_task(db, task.id) is True
    assert get_task(db, task.id) is None


def test_create_and_list_comments(setup) -> None:
    db, user, project = setup
    task = create_task(db, project_id=project.id, title="T", created_by=user.id)
    c1 = create_comment(db, task_id=task.id, body="First comment", author_id=user.id)
    c2 = create_comment(db, task_id=task.id, body="Second comment", author_id=user.id)

    comments = list_comments(db, task.id)
    assert len(comments) == 2
    assert comments[0].body == "First comment"
    assert comments[1].body == "Second comment"


def test_delete_comment(setup) -> None:
    db, user, project = setup
    task = create_task(db, project_id=project.id, title="T", created_by=user.id)
    comment = create_comment(db, task_id=task.id, body="Delete me", author_id=user.id)
    assert delete_comment(db, comment.id) is True
    assert list_comments(db, task.id) == []
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/pm/test_crud_tasks.py -v
```

Expected: `ModuleNotFoundError: No module named 'EvoScientist.pm.crud.tasks'`

- [ ] **Step 3: Implement `EvoScientist/pm/crud/tasks.py`**

```python
"""CRUD operations for Task and Comment entities."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from ..db import get_db
from ..models import Comment, Task


def create_task(
    db_path: Path,
    project_id: str,
    title: str,
    created_by: str,
    description: str | None = None,
    assignee_id: str | None = None,
    priority: str = "medium",
    deadline: str | None = None,
    session_id: str | None = None,
) -> Task:
    """Create a task and return it."""
    task_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO tasks
               (id, project_id, title, description, assignee_id, status, priority,
                deadline, session_id, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'todo', ?, ?, ?, ?, ?, ?)""",
            (task_id, project_id, title, description, assignee_id, priority,
             deadline, session_id, created_by, now, now),
        )
    return Task(
        id=task_id,
        project_id=project_id,
        title=title,
        description=description,
        assignee_id=assignee_id,
        status="todo",
        priority=priority,
        deadline=deadline,
        session_id=session_id,
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )


def get_task(db_path: Path, task_id: str) -> Task | None:
    """Return Task by id, or None."""
    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return _row_to_task(row) if row else None


def list_tasks(
    db_path: Path,
    project_id: str,
    status: str | None = None,
    assignee_id: str | None = None,
    priority: str | None = None,
) -> list[Task]:
    """Return tasks for a project, with optional filters."""
    query = "SELECT * FROM tasks WHERE project_id = ?"
    params: list = [project_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    if assignee_id:
        query += " AND assignee_id = ?"
        params.append(assignee_id)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    query += " ORDER BY created_at ASC"
    with get_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_task(r) for r in rows]


def update_task(
    db_path: Path,
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    assignee_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    deadline: str | None = None,
    session_id: str | None = None,
) -> Task:
    """Update task fields. Omitted fields are unchanged."""
    task = get_task(db_path, task_id)
    if task is None:
        raise ValueError(f"Task {task_id!r} not found")
    now = datetime.now(UTC).isoformat()
    new = Task(
        id=task.id,
        project_id=task.project_id,
        title=title if title is not None else task.title,
        description=description if description is not None else task.description,
        assignee_id=assignee_id if assignee_id is not None else task.assignee_id,
        status=status if status is not None else task.status,
        priority=priority if priority is not None else task.priority,
        deadline=deadline if deadline is not None else task.deadline,
        session_id=session_id if session_id is not None else task.session_id,
        created_by=task.created_by,
        created_at=task.created_at,
        updated_at=now,
    )
    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE tasks SET title=?, description=?, assignee_id=?, status=?,
               priority=?, deadline=?, session_id=?, updated_at=? WHERE id=?""",
            (new.title, new.description, new.assignee_id, new.status,
             new.priority, new.deadline, new.session_id, now, task_id),
        )
    return new


def delete_task(db_path: Path, task_id: str) -> bool:
    """Delete a task and cascade to comments. Returns True if deleted."""
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return cur.rowcount > 0


def create_comment(
    db_path: Path, task_id: str, body: str, author_id: str | None = None
) -> Comment:
    """Add a comment to a task."""
    comment_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO task_comments (id, task_id, author_id, body, created_at) VALUES (?, ?, ?, ?, ?)",
            (comment_id, task_id, author_id, body, now),
        )
    return Comment(id=comment_id, task_id=task_id, author_id=author_id, body=body, created_at=now)


def list_comments(db_path: Path, task_id: str) -> list[Comment]:
    """Return comments for a task, oldest first."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, task_id, author_id, body, created_at FROM task_comments WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,),
        ).fetchall()
    return [Comment(id=r["id"], task_id=r["task_id"], author_id=r["author_id"], body=r["body"], created_at=r["created_at"]) for r in rows]


def delete_comment(db_path: Path, comment_id: str) -> bool:
    """Delete a comment by id. Returns True if deleted."""
    with get_db(db_path) as conn:
        cur = conn.execute("DELETE FROM task_comments WHERE id = ?", (comment_id,))
    return cur.rowcount > 0


def _row_to_task(row) -> Task:
    return Task(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        description=row["description"],
        assignee_id=row["assignee_id"],
        status=row["status"],
        priority=row["priority"],
        deadline=row["deadline"],
        session_id=row["session_id"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/pm/test_crud_tasks.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/crud/tasks.py tests/pm/test_crud_tasks.py
git commit -m "feat(pm): add task and comment CRUD"
```

---

### Task 8: Pydantic schemas + FastAPI app + permission deps

**Files:**
- Create: `EvoScientist/pm/api/schemas.py`
- Create: `EvoScientist/pm/api/deps.py`
- Create: `EvoScientist/pm/api/app.py`
- Create: `tests/pm/conftest.py` (update with API fixture)

- [ ] **Step 1: Create `EvoScientist/pm/api/schemas.py`**

```python
"""Pydantic request/response models for the PM API."""
from __future__ import annotations

from pydantic import BaseModel, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user_id: str
    username: str
    is_admin: bool


# ── Users ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6)
    email: str | None = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str | None
    is_admin: bool
    created_at: str


class UpdatePasswordRequest(BaseModel):
    new_password: str = Field(min_length=6)


# ── Projects ──────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    archive: bool = False


class MemberResponse(BaseModel):
    user_id: str
    username: str
    role: str
    added_at: str


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    created_by: str
    created_at: str
    archived_at: str | None
    members: list[MemberResponse] = []


class AddMemberRequest(BaseModel):
    user_id: str
    role: str = Field(pattern="^(owner|editor|viewer)$")


class UpdateMemberRoleRequest(BaseModel):
    role: str = Field(pattern="^(owner|editor|viewer)$")


# ── Tasks ─────────────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    description: str | None = None
    assignee_id: str | None = None
    priority: str = Field(default="medium", pattern="^(high|medium|low)$")
    deadline: str | None = None    # ISO date YYYY-MM-DD
    session_id: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    assignee_id: str | None = None
    status: str | None = Field(default=None, pattern="^(todo|in_progress|done)$")
    priority: str | None = Field(default=None, pattern="^(high|medium|low)$")
    deadline: str | None = None
    session_id: str | None = None


class TaskResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: str | None
    assignee_id: str | None
    status: str
    priority: str
    deadline: str | None
    session_id: str | None
    created_by: str
    created_at: str
    updated_at: str


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)


class CommentResponse(BaseModel):
    id: str
    task_id: str
    author_id: str | None
    body: str
    created_at: str


# ── Errors ────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
    status: int
    type: str = "about:blank"
```

- [ ] **Step 2: Create `EvoScientist/pm/api/deps.py`**

```python
"""FastAPI dependencies for authentication and role-based access control."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from ..auth import validate_token
from ..crud.projects import get_member_role
from ..crud.users import get_user_by_id
from ..db import get_db_path
from ..models import User


def _extract_token(authorization: str = Header(...)) -> str:
    """Parse Bearer token from Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    return authorization.removeprefix("Bearer ").strip()


def get_current_user(token: str = Depends(_extract_token)) -> User:
    """Resolve the current user from the Bearer token. Raises 401 if invalid."""
    user_id = validate_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = get_user_by_id(get_db_path(), user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Raises 403 if current user is not admin."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_project_role(*allowed_roles: str):
    """Return a dependency that checks the caller's role in a project."""
    def _dep(project_id: str, current_user: User = Depends(get_current_user)) -> User:
        role = get_member_role(get_db_path(), project_id, current_user.id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
        if role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{role}' not permitted here")
        return current_user
    return _dep
```

- [ ] **Step 3: Create `EvoScientist/pm/api/app.py`**

```python
"""FastAPI application factory for the PM API."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..db import create_schema
from .routes import auth, projects, tasks, users

_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


def create_app(db_path: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    create_schema(db_path)  # idempotent — safe to call on every startup

    app = FastAPI(
        title="EvoScientist PM API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:7860", "http://127.0.0.1:7860"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
    app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
    app.include_router(tasks.router, prefix="/api/v1/projects", tags=["tasks"])

    # Serve React SPA — only if the dist folder exists (i.e., frontend has been built)
    if _FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            return FileResponse(str(_FRONTEND_DIST / "index.html"))

    return app
```

- [ ] **Step 4: Update `tests/pm/conftest.py` with API client fixture**

Append to the existing `tests/pm/conftest.py`:

```python
# Add these imports at the top of the existing file:
# from httpx import AsyncClient, ASGITransport
# from EvoScientist.pm.api.app import create_app

# Add this fixture at the bottom:
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from EvoScientist.pm.api.app import create_app


@pytest.fixture
def app(tmp_db: Path):
    """Return a FastAPI test app backed by a temp DB."""
    import EvoScientist.pm.api.deps as deps_mod
    import EvoScientist.pm.auth as auth_mod
    import EvoScientist.pm.crud.users as users_mod
    import EvoScientist.pm.crud.projects as projects_mod
    import EvoScientist.pm.crud.tasks as tasks_mod

    # Patch all DB path lookups to use the temp DB
    monkeypatch_db(tmp_db, deps_mod, auth_mod, users_mod, projects_mod, tasks_mod)
    return create_app(tmp_db)


def monkeypatch_db(db_path, *modules):
    """Replace get_db_path() in each module to return db_path."""
    for mod in modules:
        if hasattr(mod, "get_db_path"):
            mod.get_db_path = lambda: db_path


@pytest.fixture
def client(app):
    """Synchronous TestClient for the FastAPI app."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def admin_user(tmp_db: Path):
    """Create and return an admin user in the temp DB."""
    from EvoScientist.pm.crud.users import create_user
    from EvoScientist.pm.auth import hash_password
    return create_user(tmp_db, username="admin", password_hash=hash_password("adminpass"), is_admin=True)


@pytest.fixture
def admin_token(tmp_db: Path, admin_user, client):
    """Log in as admin and return the auth token."""
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "adminpass"})
    return resp.json()["token"]
```

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/api/ tests/pm/conftest.py
git commit -m "feat(pm): add Pydantic schemas, FastAPI app, and auth deps"
```

---

### Task 9: API routes

**Files:**
- Create: `EvoScientist/pm/api/routes/auth.py`
- Create: `EvoScientist/pm/api/routes/users.py`
- Create: `EvoScientist/pm/api/routes/projects.py`
- Create: `EvoScientist/pm/api/routes/tasks.py`
- Create: `tests/pm/test_api_auth.py`
- Create: `tests/pm/test_api_projects.py`
- Create: `tests/pm/test_api_tasks.py`

- [ ] **Step 1: Write failing API tests**

`tests/pm/test_api_auth.py`:
```python
"""Tests for /auth routes."""
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.users import create_user


def test_login_success(client, tmp_db) -> None:
    create_user(tmp_db, username="alice", password_hash=hash_password("pass123"))
    resp = client.post("/api/v1/auth/login", json={"username": "alice", "password": "pass123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["username"] == "alice"


def test_login_wrong_password(client, tmp_db) -> None:
    create_user(tmp_db, username="bob", password_hash=hash_password("correct"))
    resp = client.post("/api/v1/auth/login", json={"username": "bob", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_user(client) -> None:
    resp = client.post("/api/v1/auth/login", json={"username": "ghost", "password": "x"})
    assert resp.status_code == 401


def test_protected_route_without_token(client) -> None:
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 422  # missing header


def test_protected_route_invalid_token(client) -> None:
    resp = client.get("/api/v1/users/me", headers={"Authorization": "Bearer badtoken"})
    assert resp.status_code == 401
```

`tests/pm/test_api_projects.py`:
```python
"""Tests for /projects routes and permission enforcement."""


def test_create_project(client, admin_token) -> None:
    resp = client.post(
        "/api/v1/projects",
        json={"name": "My Project"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Project"
    assert any(m["role"] == "owner" for m in data["members"])


def test_list_projects_only_own(client, tmp_db, admin_token) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user
    other = create_user(tmp_db, username="other", password_hash=hash_password("p"))

    # Admin creates a project; other user should NOT see it
    client.post("/api/v1/projects", json={"name": "Secret"}, headers={"Authorization": f"Bearer {admin_token}"})

    other_token = client.post("/api/v1/auth/login", json={"username": "other", "password": "p"}).json()["token"]
    resp = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {other_token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_viewer_cannot_delete_project(client, tmp_db, admin_token) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user
    from EvoScientist.pm.crud.projects import add_member

    viewer = create_user(tmp_db, username="viewer", password_hash=hash_password("vp"))
    create_resp = client.post("/api/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {admin_token}"})
    project_id = create_resp.json()["id"]

    add_member(tmp_db, project_id=project_id, user_id=viewer.id, role="viewer")
    viewer_token = client.post("/api/v1/auth/login", json={"username": "viewer", "password": "vp"}).json()["token"]

    resp = client.delete(f"/api/v1/projects/{project_id}", headers={"Authorization": f"Bearer {viewer_token}"})
    assert resp.status_code == 403


def test_nonmember_gets_403(client, tmp_db, admin_token) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user

    create_user(tmp_db, username="outsider", password_hash=hash_password("op"))
    create_resp = client.post("/api/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {admin_token}"})
    project_id = create_resp.json()["id"]

    outsider_token = client.post("/api/v1/auth/login", json={"username": "outsider", "password": "op"}).json()["token"]
    resp = client.get(f"/api/v1/projects/{project_id}", headers={"Authorization": f"Bearer {outsider_token}"})
    assert resp.status_code == 403
```

`tests/pm/test_api_tasks.py`:
```python
"""Tests for task and comment routes."""


def _make_project(client, token):
    resp = client.post("/api/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {token}"})
    return resp.json()["id"]


def test_create_and_list_tasks(client, admin_token) -> None:
    pid = _make_project(client, admin_token)
    client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T1"}, headers={"Authorization": f"Bearer {admin_token}"})
    client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T2", "priority": "high"}, headers={"Authorization": f"Bearer {admin_token}"})

    resp = client.get(f"/api/v1/projects/{pid}/tasks", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_task_status(client, admin_token) -> None:
    pid = _make_project(client, admin_token)
    task_id = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T"}, headers={"Authorization": f"Bearer {admin_token}"}).json()["id"]

    resp = client.put(f"/api/v1/projects/{pid}/tasks/{task_id}", json={"status": "done"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


def test_viewer_cannot_create_task(client, tmp_db, admin_token) -> None:
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user
    from EvoScientist.pm.crud.projects import add_member

    viewer = create_user(tmp_db, username="v2", password_hash=hash_password("p"))
    pid = _make_project(client, admin_token)
    add_member(tmp_db, project_id=pid, user_id=viewer.id, role="viewer")
    viewer_token = client.post("/api/v1/auth/login", json={"username": "v2", "password": "p"}).json()["token"]

    resp = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T"}, headers={"Authorization": f"Bearer {viewer_token}"})
    assert resp.status_code == 403


def test_create_and_delete_comment(client, admin_token) -> None:
    pid = _make_project(client, admin_token)
    task_id = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T"}, headers={"Authorization": f"Bearer {admin_token}"}).json()["id"]

    cid = client.post(f"/api/v1/projects/{pid}/tasks/{task_id}/comments", json={"body": "Note"}, headers={"Authorization": f"Bearer {admin_token}"}).json()["id"]
    del_resp = client.delete(f"/api/v1/projects/{pid}/tasks/{task_id}/comments/{cid}", headers={"Authorization": f"Bearer {admin_token}"})
    assert del_resp.status_code == 204

    comments = client.get(f"/api/v1/projects/{pid}/tasks/{task_id}/comments", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert comments == []
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/pm/test_api_auth.py tests/pm/test_api_projects.py tests/pm/test_api_tasks.py -v
```

Expected: import errors for missing route modules.

- [ ] **Step 3: Implement `EvoScientist/pm/api/routes/auth.py`**

```python
"""Auth routes: login and logout."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth import create_token, verify_password
from ...crud.users import get_user_by_username
from ...db import get_db_path
from ..deps import get_current_user
from ..schemas import LoginRequest, TokenResponse
from ...db import get_db

router = APIRouter()
_TOKEN_TTL_HOURS = 24


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = get_user_by_username(get_db_path(), body.username)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_token()
    expires_at = (datetime.now(UTC) + timedelta(hours=_TOKEN_TTL_HOURS)).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user.id, expires_at),
        )
    return TokenResponse(token=token, user_id=user.id, username=user.username, is_admin=user.is_admin)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user=Depends(get_current_user), authorization: str = ""):
    # Delete all tokens for this user (simple full logout)
    with get_db() as conn:
        conn.execute("DELETE FROM auth_tokens WHERE user_id = ?", (current_user.id,))
```

- [ ] **Step 4: Implement `EvoScientist/pm/api/routes/users.py`**

```python
"""User management routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth import hash_password
from ...crud.users import (
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    update_user_password,
)
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_admin
from ..schemas import UpdatePasswordRequest, UserCreate, UserResponse

router = APIRouter()


def _to_response(u: User) -> UserResponse:
    return UserResponse(id=u.id, username=u.username, email=u.email, is_admin=u.is_admin, created_at=u.created_at)


@router.get("", response_model=list[UserResponse])
def list_all_users(_admin: User = Depends(require_admin)):
    return [_to_response(u) for u in list_users(get_db_path())]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_new_user(body: UserCreate, _admin: User = Depends(require_admin)):
    try:
        user = create_user(get_db_path(), username=body.username, password_hash=hash_password(body.password), email=body.email)
    except Exception:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    return _to_response(user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return _to_response(current_user)


@router.put("/me", response_model=UserResponse)
def update_me(body: UpdatePasswordRequest, current_user: User = Depends(get_current_user)):
    update_user_password(get_db_path(), current_user.id, hash_password(body.new_password))
    updated = get_user_by_id(get_db_path(), current_user.id)
    return _to_response(updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_user(user_id: str, _admin: User = Depends(require_admin)):
    if not delete_user(get_db_path(), user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
```

- [ ] **Step 5: Implement `EvoScientist/pm/api/routes/projects.py`**

```python
"""Project and member management routes."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status

from ...crud.projects import (
    add_member,
    create_project,
    delete_project,
    get_member_role,
    get_project,
    list_projects_for_user,
    remove_member,
    update_member_role,
    update_project,
)
from ...crud.users import get_user_by_id, list_users
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role
from ..schemas import (
    AddMemberRequest,
    MemberResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    UpdateMemberRoleRequest,
)

router = APIRouter()


def _project_to_response(project, db_path) -> ProjectResponse:
    from ...db import get_db
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT pm.user_id, pm.role, pm.added_at, u.username
               FROM project_members pm JOIN users u ON pm.user_id = u.id
               WHERE pm.project_id = ?""",
            (project.id,),
        ).fetchall()
    members = [MemberResponse(user_id=r["user_id"], username=r["username"], role=r["role"], added_at=r["added_at"]) for r in rows]
    return ProjectResponse(
        id=project.id, name=project.name, description=project.description,
        created_by=project.created_by, created_at=project.created_at,
        archived_at=project.archived_at, members=members,
    )


@router.get("", response_model=list[ProjectResponse])
def list_my_projects(current_user: User = Depends(get_current_user)):
    db = get_db_path()
    projects = list_projects_for_user(db, current_user.id)
    return [_project_to_response(p, db) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_new_project(body: ProjectCreate, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    project = create_project(db, name=body.name, description=body.description, created_by=current_user.id)
    return _project_to_response(project, db)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_detail(project_id: str, current_user: User = Depends(require_project_role("owner", "editor", "viewer"))):
    db = get_db_path()
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(project, db)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_existing_project(
    project_id: str,
    body: ProjectUpdate,
    current_user: User = Depends(require_project_role("owner")),
):
    db = get_db_path()
    archived_at = datetime.now(UTC).isoformat() if body.archive else None
    project = update_project(db, project_id, name=body.name, description=body.description, archived_at=archived_at)
    return _project_to_response(project, db)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_project(project_id: str, current_user: User = Depends(require_project_role("owner"))):
    delete_project(get_db_path(), project_id)


@router.post("/{project_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_project_member(
    project_id: str,
    body: AddMemberRequest,
    current_user: User = Depends(require_project_role("owner")),
):
    db = get_db_path()
    user = get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    member = add_member(db, project_id=project_id, user_id=body.user_id, role=body.role)
    return MemberResponse(user_id=member.user_id, username=user.username, role=member.role, added_at=member.added_at)


@router.put("/{project_id}/members/{user_id}", response_model=MemberResponse)
def change_member_role(
    project_id: str,
    user_id: str,
    body: UpdateMemberRoleRequest,
    current_user: User = Depends(require_project_role("owner")),
):
    db = get_db_path()
    update_member_role(db, project_id=project_id, user_id=user_id, role=body.role)
    user = get_user_by_id(db, user_id)
    from ...db import get_db as _get_db
    with _get_db(db) as conn:
        row = conn.execute("SELECT added_at FROM project_members WHERE project_id=? AND user_id=?", (project_id, user_id)).fetchone()
    return MemberResponse(user_id=user_id, username=user.username if user else user_id, role=body.role, added_at=row["added_at"])


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(
    project_id: str,
    user_id: str,
    current_user: User = Depends(require_project_role("owner")),
):
    remove_member(get_db_path(), project_id=project_id, user_id=user_id)
```

- [ ] **Step 6: Implement `EvoScientist/pm/api/routes/tasks.py`**

```python
"""Task and comment routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...crud.tasks import (
    create_comment,
    create_task,
    delete_comment,
    delete_task,
    get_task,
    list_comments,
    list_tasks,
    update_task,
)
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role
from ..schemas import (
    CommentCreate,
    CommentResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)

router = APIRouter()


def _task_to_response(t) -> TaskResponse:
    return TaskResponse(
        id=t.id, project_id=t.project_id, title=t.title, description=t.description,
        assignee_id=t.assignee_id, status=t.status, priority=t.priority,
        deadline=t.deadline, session_id=t.session_id,
        created_by=t.created_by, created_at=t.created_at, updated_at=t.updated_at,
    )


@router.get("/{project_id}/tasks", response_model=list[TaskResponse])
def list_project_tasks(
    project_id: str,
    status_filter: str | None = None,
    assignee_id: str | None = None,
    priority: str | None = None,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    tasks = list_tasks(get_db_path(), project_id, status=status_filter, assignee_id=assignee_id, priority=priority)
    return [_task_to_response(t) for t in tasks]


@router.post("/{project_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_new_task(
    project_id: str,
    body: TaskCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    task = create_task(
        get_db_path(), project_id=project_id, title=body.title, created_by=current_user.id,
        description=body.description, assignee_id=body.assignee_id,
        priority=body.priority, deadline=body.deadline, session_id=body.session_id,
    )
    return _task_to_response(task)


@router.get("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
def get_task_detail(
    project_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_response(task)


@router.put("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
def update_existing_task(
    project_id: str,
    task_id: str,
    body: TaskUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    updated = update_task(
        get_db_path(), task_id, title=body.title, description=body.description,
        assignee_id=body.assignee_id, status=body.status, priority=body.priority,
        deadline=body.deadline, session_id=body.session_id,
    )
    return _task_to_response(updated)


@router.delete("/{project_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_task(
    project_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    delete_task(get_db_path(), task_id)


@router.get("/{project_id}/tasks/{task_id}/comments", response_model=list[CommentResponse])
def get_comments(
    project_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    return [CommentResponse(id=c.id, task_id=c.task_id, author_id=c.author_id, body=c.body, created_at=c.created_at) for c in list_comments(get_db_path(), task_id)]


@router.post("/{project_id}/tasks/{task_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def add_comment(
    project_id: str,
    task_id: str,
    body: CommentCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    comment = create_comment(get_db_path(), task_id=task_id, body=body.body, author_id=current_user.id)
    return CommentResponse(id=comment.id, task_id=comment.task_id, author_id=comment.author_id, body=comment.body, created_at=comment.created_at)


@router.delete("/{project_id}/tasks/{task_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_comment(
    project_id: str,
    task_id: str,
    comment_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    delete_comment(get_db_path(), comment_id)
```

- [ ] **Step 7: Run all API tests**

```bash
uv run pytest tests/pm/test_api_auth.py tests/pm/test_api_projects.py tests/pm/test_api_tasks.py -v
```

Expected: all pass (failures mean the conftest patching needs adjustment — check that `monkeypatch_db` patches the right module-level `get_db_path` references in each route module).

- [ ] **Step 8: Run full PM test suite**

```bash
uv run pytest tests/pm/ -v
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add EvoScientist/pm/api/routes/ tests/pm/
git commit -m "feat(pm): add all REST API routes with permission enforcement"
```

---

## Phase 2: CLI + Dashboard

---

### Task 10: Dashboard CLI command

**Files:**
- Modify: `EvoScientist/cli/_app.py`
- Create: `EvoScientist/pm/server.py`

- [ ] **Step 1: Create `EvoScientist/pm/server.py`**

```python
"""Helpers to start and stop the PM server as a background subprocess."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

_PORT = 7860
_PID_FILE = Path.home() / ".config" / "evoscientist" / "pm.pid"


def is_server_running() -> bool:
    """Return True if the PM server is reachable on localhost:{_PORT}."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", _PORT)) == 0


def start_server_background() -> None:
    """Start the PM server as a background subprocess. No-op if already running."""
    if is_server_running():
        return
    proc = subprocess.Popen(
        [sys.executable, "-m", "EvoScientist.pm._run_server"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(proc.pid))
    # Wait up to 3 seconds for the server to start
    for _ in range(12):
        if is_server_running():
            return
        time.sleep(0.25)


def stop_server() -> None:
    """Stop the background PM server if running."""
    if _PID_FILE.exists():
        try:
            pid = int(_PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, ValueError):
            pass
        _PID_FILE.unlink(missing_ok=True)
```

- [ ] **Step 2: Create `EvoScientist/pm/_run_server.py`** (the module invoked by `-m`)

```python
"""Entry point for running the PM server: python -m EvoScientist.pm._run_server"""
import uvicorn
from .api.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=7860, log_level="warning")
```

- [ ] **Step 3: Add `dashboard` command to `EvoScientist/cli/_app.py`**

Open `EvoScientist/cli/_app.py` and append after the last `app.add_typer(...)` call:

```python
# Dashboard subcommand
dashboard_app = typer.Typer(help="Start the PM dashboard server")
app.add_typer(dashboard_app, name="dashboard")
```

Then open `EvoScientist/cli/interactive.py` (or wherever the main CLI commands are registered) and find where `EvoSci serve` or similar subcommands are invoked. Add:

```python
@dashboard_app.callback(invoke_without_command=True)
def dashboard(
    port: int = typer.Option(7860, help="Port to listen on"),
    host: str = typer.Option("127.0.0.1", help="Host to bind"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="Open browser on start"),
):
    """Start the project management dashboard at http://localhost:7860."""
    import webbrowser
    import uvicorn
    from EvoScientist.pm.api.app import create_app

    app_instance = create_app()
    if open_browser:
        webbrowser.open(f"http://{host}:{port}")
    uvicorn.run(app_instance, host=host, port=port)
```

Add the import at the top of `_app.py`:
```python
from .cli._app import dashboard_app
```

- [ ] **Step 4: Verify the command is registered**

```bash
uv run EvoSci dashboard --help
```

Expected output includes:
```
Usage: EvoSci dashboard [OPTIONS]
  Start the project management dashboard at http://localhost:7860.
```

- [ ] **Step 5: Commit**

```bash
git add EvoScientist/pm/server.py EvoScientist/pm/_run_server.py EvoScientist/cli/_app.py
git commit -m "feat(pm): add EvoSci dashboard CLI command and background server helper"
```

---

### Task 11: CLI slash commands

**Files:**
- Create: `EvoScientist/commands/pm_commands.py`
- Modify: CLI registration (where other commands are registered)
- Create: `tests/pm/test_pm_commands.py`

- [ ] **Step 1: Write failing tests**

`tests/pm/test_pm_commands.py`:
```python
"""Tests for PM slash commands with mocked httpx."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from EvoScientist.commands.pm_commands import ProjectCommand, TaskCommand


@pytest.fixture
def ctx():
    ui = MagicMock()
    ui.append_system = MagicMock()
    ui.flush = AsyncMock()
    return MagicMock(ui=ui)


@pytest.fixture
def mock_server_running():
    with patch("EvoScientist.commands.pm_commands._ensure_server") as m:
        m.return_value = None
        yield m


@pytest.mark.asyncio
async def test_project_list_calls_api(ctx, mock_server_running) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"id": "p1", "name": "Alpha", "archived_at": None}]

    with patch("EvoScientist.commands.pm_commands._get", return_value=mock_response):
        cmd = ProjectCommand()
        await cmd.execute(ctx, ["list"])

    ctx.ui.append_system.assert_called()
    call_args = ctx.ui.append_system.call_args[0][0]
    assert "Alpha" in call_args


@pytest.mark.asyncio
async def test_task_list_no_active_project(ctx, mock_server_running) -> None:
    cmd = TaskCommand()
    # When no active project is set, should show an error
    with patch("EvoScientist.commands.pm_commands._active_project_id", None):
        await cmd.execute(ctx, ["list"])
    ctx.ui.append_system.assert_called()
    msg = ctx.ui.append_system.call_args[0][0]
    assert "project" in msg.lower()


@pytest.mark.asyncio
async def test_task_add_requires_title(ctx, mock_server_running) -> None:
    cmd = TaskCommand()
    with patch("EvoScientist.commands.pm_commands._active_project_id", "p1"):
        await cmd.execute(ctx, ["add"])  # no title
    ctx.ui.append_system.assert_called()
    msg = ctx.ui.append_system.call_args[0][0]
    assert "title" in msg.lower()
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/pm/test_pm_commands.py -v
```

Expected: `ModuleNotFoundError: No module named 'EvoScientist.commands.pm_commands'`

- [ ] **Step 3: Implement `EvoScientist/commands/pm_commands.py`**

```python
"""Slash commands for project management: /project, /task, /user."""
from __future__ import annotations

import getpass
import json
from pathlib import Path
from typing import Any

import httpx

from .base import Command, CommandContext

_BASE_URL = "http://127.0.0.1:7860/api/v1"
_TOKEN_FILE = Path.home() / ".config" / "evoscientist" / "pm_token"
_active_project_id: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_server() -> None:
    from EvoScientist.pm.server import start_server_background
    start_server_background()


def _load_token() -> str | None:
    if _TOKEN_FILE.exists():
        return _TOKEN_FILE.read_text().strip() or None
    return None


def _save_token(token: str) -> None:
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(token)
    _TOKEN_FILE.chmod(0o600)


def _headers() -> dict[str, str]:
    token = _load_token()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def _get(path: str) -> httpx.Response:
    return httpx.get(f"{_BASE_URL}{path}", headers=_headers(), timeout=5)


def _post(path: str, data: dict) -> httpx.Response:
    return httpx.post(f"{_BASE_URL}{path}", json=data, headers=_headers(), timeout=5)


def _put(path: str, data: dict) -> httpx.Response:
    return httpx.put(f"{_BASE_URL}{path}", json=data, headers=_headers(), timeout=5)


def _delete(path: str) -> httpx.Response:
    return httpx.delete(f"{_BASE_URL}{path}", headers=_headers(), timeout=5)


def _maybe_login(ctx: CommandContext) -> bool:
    """Prompt for login if no valid token. Returns True if authenticated."""
    resp = _get("/users/me")
    if resp.status_code == 200:
        return True
    ctx.ui.append_system("Not logged in. Enter credentials:")
    username = input("  Username: ")
    password = getpass.getpass("  Password: ")
    login_resp = httpx.post(f"{_BASE_URL}/auth/login", json={"username": username, "password": password}, timeout=5)
    if login_resp.status_code == 200:
        _save_token(login_resp.json()["token"])
        return True
    ctx.ui.append_system("Login failed.", style="red")
    return False


# ── /project command ──────────────────────────────────────────────────────────

class ProjectCommand(Command):
    name = "/project"
    alias = ["/proj"]
    description = "Manage projects: list, create, switch, info, invite"

    async def execute(self, ctx: CommandContext, args: list[str]) -> None:
        global _active_project_id
        _ensure_server()
        if not _maybe_login(ctx):
            return
        sub = args[0] if args else "list"

        if sub == "list":
            resp = _get("/projects")
            if resp.status_code != 200:
                ctx.ui.append_system(f"Error: {resp.status_code}", style="red")
                return
            projects = resp.json()
            if not projects:
                ctx.ui.append_system("No projects. Create one with /project create <name>")
                return
            lines = ["Projects:"]
            for p in projects:
                active_marker = " ← active" if p["id"] == _active_project_id else ""
                lines.append(f"  [{p['id'][:8]}] {p['name']}{active_marker}")
            ctx.ui.append_system("\n".join(lines))

        elif sub == "create":
            if len(args) < 2:
                ctx.ui.append_system("Usage: /project create <name>", style="yellow")
                return
            name = " ".join(args[1:])
            resp = _post("/projects", {"name": name})
            if resp.status_code == 201:
                p = resp.json()
                _active_project_id = p["id"]
                ctx.ui.append_system(f"Created project '{p['name']}' [{p['id'][:8]}] (now active)")
            else:
                ctx.ui.append_system(f"Error: {resp.json().get('detail', resp.status_code)}", style="red")

        elif sub == "switch":
            if len(args) < 2:
                ctx.ui.append_system("Usage: /project switch <id|name>", style="yellow")
                return
            query = args[1]
            resp = _get("/projects")
            matches = [p for p in resp.json() if p["id"].startswith(query) or query.lower() in p["name"].lower()]
            if not matches:
                ctx.ui.append_system(f"No project matching '{query}'", style="yellow")
                return
            _active_project_id = matches[0]["id"]
            ctx.ui.append_system(f"Active project: {matches[0]['name']} [{matches[0]['id'][:8]}]")

        elif sub == "info":
            if not _active_project_id:
                ctx.ui.append_system("No active project. Use /project switch <name>", style="yellow")
                return
            resp = _get(f"/projects/{_active_project_id}")
            if resp.status_code != 200:
                ctx.ui.append_system(f"Error: {resp.status_code}", style="red")
                return
            p = resp.json()
            members = ", ".join(f"{m['username']}({m['role']})" for m in p.get("members", []))
            ctx.ui.append_system(f"Project: {p['name']}\nDescription: {p.get('description') or '—'}\nMembers: {members}")

        elif sub == "invite":
            if len(args) < 2:
                ctx.ui.append_system("Usage: /project invite <username> [--role editor|viewer]", style="yellow")
                return
            if not _active_project_id:
                ctx.ui.append_system("No active project.", style="yellow")
                return
            username = args[1]
            role = "editor"
            if "--role" in args:
                idx = args.index("--role")
                role = args[idx + 1] if idx + 1 < len(args) else "editor"
            # Look up user id
            users_resp = _get("/users")
            user = next((u for u in users_resp.json() if u["username"] == username), None)
            if not user:
                ctx.ui.append_system(f"User '{username}' not found.", style="yellow")
                return
            resp = _post(f"/projects/{_active_project_id}/members", {"user_id": user["id"], "role": role})
            if resp.status_code == 201:
                ctx.ui.append_system(f"Invited {username} as {role}.")
            else:
                ctx.ui.append_system(f"Error: {resp.json().get('detail', resp.status_code)}", style="red")
        else:
            ctx.ui.append_system("Subcommands: list, create, switch, info, invite")


# ── /task command ─────────────────────────────────────────────────────────────

class TaskCommand(Command):
    name = "/task"
    description = "Manage tasks in the active project: list, add, done, show"

    async def execute(self, ctx: CommandContext, args: list[str]) -> None:
        _ensure_server()
        if not _maybe_login(ctx):
            return
        sub = args[0] if args else "list"

        if not _active_project_id and sub not in ("help",):
            ctx.ui.append_system("No active project. Use /project switch <name>", style="yellow")
            return

        if sub == "list":
            resp = _get(f"/projects/{_active_project_id}/tasks")
            tasks = resp.json()
            if not tasks:
                ctx.ui.append_system("No tasks in this project.")
                return
            groups: dict[str, list] = {"todo": [], "in_progress": [], "done": []}
            for t in tasks:
                groups[t["status"]].append(t)
            lines = []
            for status, items in groups.items():
                if items:
                    lines.append(f"{status.upper()}:")
                    for t in items:
                        deadline = f" [due {t['deadline']}]" if t.get("deadline") else ""
                        lines.append(f"  [{t['id'][:8]}] {t['title']} ({t['priority']}){deadline}")
            ctx.ui.append_system("\n".join(lines))

        elif sub == "add":
            # parse: /task add <title> [--assignee <user>] [--deadline YYYY-MM-DD] [--priority high|medium|low]
            if len(args) < 2:
                ctx.ui.append_system("Usage: /task add <title> [--deadline YYYY-MM-DD] [--priority high|medium|low]", style="yellow")
                return
            # Extract flags
            remaining = args[1:]
            deadline = None
            priority = "medium"
            assignee_id = None
            title_parts = []
            i = 0
            while i < len(remaining):
                if remaining[i] == "--deadline" and i + 1 < len(remaining):
                    deadline = remaining[i + 1]; i += 2
                elif remaining[i] == "--priority" and i + 1 < len(remaining):
                    priority = remaining[i + 1]; i += 2
                elif remaining[i] == "--assignee" and i + 1 < len(remaining):
                    # Resolve username to id
                    uname = remaining[i + 1]; i += 2
                    users_resp = _get("/users")
                    user = next((u for u in users_resp.json() if u["username"] == uname), None)
                    assignee_id = user["id"] if user else None
                else:
                    title_parts.append(remaining[i]); i += 1
            title = " ".join(title_parts)
            if not title:
                ctx.ui.append_system("Task title is required.", style="yellow")
                return
            resp = _post(f"/projects/{_active_project_id}/tasks", {
                "title": title, "priority": priority,
                "deadline": deadline, "assignee_id": assignee_id,
            })
            if resp.status_code == 201:
                t = resp.json()
                ctx.ui.append_system(f"Created task [{t['id'][:8]}]: {t['title']}")
            else:
                ctx.ui.append_system(f"Error: {resp.json().get('detail', resp.status_code)}", style="red")

        elif sub == "done":
            if len(args) < 2:
                ctx.ui.append_system("Usage: /task done <id>", style="yellow")
                return
            task_id_prefix = args[1]
            # Resolve partial id
            resp = _get(f"/projects/{_active_project_id}/tasks")
            task = next((t for t in resp.json() if t["id"].startswith(task_id_prefix)), None)
            if not task:
                ctx.ui.append_system(f"Task '{task_id_prefix}' not found.", style="yellow")
                return
            _put(f"/projects/{_active_project_id}/tasks/{task['id']}", {"status": "done"})
            ctx.ui.append_system(f"Marked '{task['title']}' as done.")

        elif sub == "show":
            if len(args) < 2:
                ctx.ui.append_system("Usage: /task show <id>", style="yellow")
                return
            task_id_prefix = args[1]
            tasks_resp = _get(f"/projects/{_active_project_id}/tasks")
            task = next((t for t in tasks_resp.json() if t["id"].startswith(task_id_prefix)), None)
            if not task:
                ctx.ui.append_system(f"Task '{task_id_prefix}' not found.", style="yellow")
                return
            lines = [
                f"Title:    {task['title']}",
                f"Status:   {task['status']}",
                f"Priority: {task['priority']}",
                f"Deadline: {task.get('deadline') or '—'}",
                f"Session:  {task.get('session_id') or '—'}",
                f"Desc:     {task.get('description') or '—'}",
            ]
            comments_resp = _get(f"/projects/{_active_project_id}/tasks/{task['id']}/comments")
            if comments_resp.status_code == 200 and comments_resp.json():
                lines.append("Comments:")
                for c in comments_resp.json():
                    lines.append(f"  [{c['created_at'][:10]}] {c['body']}")
            ctx.ui.append_system("\n".join(lines))
        else:
            ctx.ui.append_system("Subcommands: list, add, done, show")


# ── /user command (admin only) ────────────────────────────────────────────────

class UserCommand(Command):
    name = "/user"
    description = "Manage users (admin only): list, create"

    async def execute(self, ctx: CommandContext, args: list[str]) -> None:
        _ensure_server()
        if not _maybe_login(ctx):
            return
        sub = args[0] if args else "list"

        if sub == "list":
            resp = _get("/users")
            if resp.status_code == 403:
                ctx.ui.append_system("Admin access required.", style="red")
                return
            users = resp.json()
            lines = ["Users:"]
            for u in users:
                admin_tag = " [admin]" if u.get("is_admin") else ""
                lines.append(f"  {u['username']}{admin_tag}")
            ctx.ui.append_system("\n".join(lines))

        elif sub == "create":
            if len(args) < 2:
                ctx.ui.append_system("Usage: /user create <username>", style="yellow")
                return
            username = args[1]
            password = getpass.getpass(f"  Password for {username}: ")
            resp = _post("/users", {"username": username, "password": password})
            if resp.status_code == 201:
                ctx.ui.append_system(f"Created user '{username}'.")
            else:
                ctx.ui.append_system(f"Error: {resp.json().get('detail', resp.status_code)}", style="red")
        else:
            ctx.ui.append_system("Subcommands: list, create")
```

- [ ] **Step 4: Register commands**

Find where other commands are registered in the CLI startup (search for where `manager.register(` is called). Add:

```python
from EvoScientist.commands.pm_commands import ProjectCommand, TaskCommand, UserCommand

manager.register(ProjectCommand())
manager.register(TaskCommand())
manager.register(UserCommand())
```

- [ ] **Step 5: Install pytest-asyncio**

```bash
uv add pytest-asyncio --dev
```

Add to `pyproject.toml` `[tool.pytest.ini_options]`:
```toml
asyncio_mode = "auto"
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/pm/test_pm_commands.py -v
```

Expected: 3 passed.

- [ ] **Step 7: Run full suite to check no regressions**

```bash
uv run pytest -v --timeout=30
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add EvoScientist/commands/pm_commands.py tests/pm/test_pm_commands.py pyproject.toml
git commit -m "feat(pm): add /project, /task, /user slash commands"
```

---

## Phase 3: React Frontend

---

### Task 12: Frontend scaffold

**Files:**
- Create: `EvoScientist/pm/frontend/package.json`
- Create: `EvoScientist/pm/frontend/vite.config.ts`
- Create: `EvoScientist/pm/frontend/tsconfig.json`
- Create: `EvoScientist/pm/frontend/index.html`
- Create: `EvoScientist/pm/frontend/src/main.tsx`

> **Prerequisite:** Node.js 18+ and npm must be installed.

- [ ] **Step 1: Create `EvoScientist/pm/frontend/package.json`**

```json
{
  "name": "evoscientist-pm",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "@tanstack/react-query": "^5.62.0",
    "@dnd-kit/core": "^6.3.1",
    "@dnd-kit/sortable": "^8.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^5.4.11",
    "vitest": "^2.1.8",
    "@testing-library/react": "^16.1.0",
    "@testing-library/jest-dom": "^6.6.3",
    "jsdom": "^25.0.1"
  }
}
```

- [ ] **Step 2: Create `EvoScientist/pm/frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:7860',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
})
```

- [ ] **Step 3: Create `EvoScientist/pm/frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create `EvoScientist/pm/frontend/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>EvoScientist PM</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `EvoScientist/pm/frontend/src/main.tsx`**

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import { Login } from './pages/Login'
import { Projects } from './pages/Projects'
import { Board } from './pages/Board'

const queryClient = new QueryClient()

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/projects" element={<PrivateRoute><Projects /></PrivateRoute>} />
        <Route path="/projects/:id" element={<PrivateRoute><Board /></PrivateRoute>} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
)
```

- [ ] **Step 6: Create `EvoScientist/pm/frontend/src/test-setup.ts`**

```typescript
import '@testing-library/jest-dom'
```

- [ ] **Step 7: Install dependencies**

```bash
cd EvoScientist/pm/frontend && npm install
```

Expected: `node_modules/` created, no errors.

- [ ] **Step 8: Commit**

```bash
cd ../../../  # back to repo root
git add EvoScientist/pm/frontend/
git commit -m "feat(pm): scaffold React frontend with Vite and TanStack Query"
```

---

### Task 13: Auth context + API client + Login page

**Files:**
- Create: `EvoScientist/pm/frontend/src/api.ts`
- Create: `EvoScientist/pm/frontend/src/auth.tsx`
- Create: `EvoScientist/pm/frontend/src/pages/Login.tsx`

- [ ] **Step 1: Create `EvoScientist/pm/frontend/src/api.ts`**

```typescript
const BASE = '/api/v1'

function getToken(): string | null {
  return sessionStorage.getItem('pm_token')
}

function authHeaders(): HeadersInit {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    method,
    headers: authHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (resp.status === 401) {
    sessionStorage.removeItem('pm_token')
    window.location.href = '/login'
  }
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(err.detail ?? resp.statusText)
  }
  if (resp.status === 204) return undefined as T
  return resp.json() as Promise<T>
}

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string; user_id: string; username: string; is_admin: boolean }>(
      'POST', '/auth/login', { username, password }
    ),
  me: () => request<{ id: string; username: string; is_admin: boolean }>('GET', '/users/me'),
  listProjects: () => request<Project[]>('GET', '/projects'),
  createProject: (name: string, description?: string) => request<Project>('POST', '/projects', { name, description }),
  getProject: (id: string) => request<Project>('GET', `/projects/${id}`),
  addMember: (projectId: string, userId: string, role: string) =>
    request('POST', `/projects/${projectId}/members`, { user_id: userId, role }),
  listTasks: (projectId: string) => request<Task[]>('GET', `/projects/${projectId}/tasks`),
  createTask: (projectId: string, data: Partial<Task>) => request<Task>('POST', `/projects/${projectId}/tasks`, data),
  updateTask: (projectId: string, taskId: string, data: Partial<Task>) =>
    request<Task>('PUT', `/projects/${projectId}/tasks/${taskId}`, data),
  deleteTask: (projectId: string, taskId: string) =>
    request<void>('DELETE', `/projects/${projectId}/tasks/${taskId}`),
  listComments: (projectId: string, taskId: string) =>
    request<Comment[]>('GET', `/projects/${projectId}/tasks/${taskId}/comments`),
  addComment: (projectId: string, taskId: string, body: string) =>
    request<Comment>('POST', `/projects/${projectId}/tasks/${taskId}/comments`, { body }),
}

export interface Project {
  id: string; name: string; description: string | null
  created_by: string; created_at: string; archived_at: string | null
  members: Member[]
}
export interface Member { user_id: string; username: string; role: string; added_at: string }
export interface Task {
  id: string; project_id: string; title: string; description: string | null
  assignee_id: string | null; status: 'todo' | 'in_progress' | 'done'
  priority: 'high' | 'medium' | 'low'; deadline: string | null
  session_id: string | null; created_by: string; created_at: string; updated_at: string
}
export interface Comment { id: string; task_id: string; author_id: string | null; body: string; created_at: string }
```

- [ ] **Step 2: Create `EvoScientist/pm/frontend/src/auth.tsx`**

```tsx
import React, { createContext, useContext, useState } from 'react'
import { api } from './api'

interface AuthCtx {
  token: string | null
  username: string | null
  isAdmin: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(sessionStorage.getItem('pm_token'))
  const [username, setUsername] = useState<string | null>(sessionStorage.getItem('pm_username'))
  const [isAdmin, setIsAdmin] = useState(sessionStorage.getItem('pm_admin') === 'true')

  async function login(u: string, p: string) {
    const data = await api.login(u, p)
    sessionStorage.setItem('pm_token', data.token)
    sessionStorage.setItem('pm_username', data.username)
    sessionStorage.setItem('pm_admin', String(data.is_admin))
    setToken(data.token)
    setUsername(data.username)
    setIsAdmin(data.is_admin)
  }

  function logout() {
    sessionStorage.clear()
    setToken(null)
    setUsername(null)
    setIsAdmin(false)
  }

  return <AuthContext.Provider value={{ token, username, isAdmin, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthCtx {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
```

- [ ] **Step 3: Create `EvoScientist/pm/frontend/src/pages/Login.tsx`**

```tsx
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(username, password)
      navigate('/projects')
    } catch (err: any) {
      setError(err.message ?? 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', fontFamily: 'system-ui' }}>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12, width: 300 }}>
        <h1 style={{ margin: 0 }}>EvoScientist PM</h1>
        {error && <p style={{ color: 'red', margin: 0 }}>{error}</p>}
        <input
          placeholder="Username" value={username} onChange={e => setUsername(e.target.value)}
          required style={{ padding: 8, fontSize: 14 }}
        />
        <input
          type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)}
          required style={{ padding: 8, fontSize: 14 }}
        />
        <button type="submit" disabled={loading} style={{ padding: 10, fontSize: 14, cursor: 'pointer' }}>
          {loading ? 'Logging in…' : 'Log in'}
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 4: Build to verify no TypeScript errors**

```bash
cd EvoScientist/pm/frontend && npm run build
```

Expected: `dist/` created, no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
cd ../../../
git add EvoScientist/pm/frontend/src/
git commit -m "feat(pm): add API client, auth context, and login page"
```

---

### Task 14: Projects list page

**Files:**
- Create: `EvoScientist/pm/frontend/src/pages/Projects.tsx`

- [ ] **Step 1: Create `EvoScientist/pm/frontend/src/pages/Projects.tsx`**

```tsx
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Project } from '../api'
import { useAuth } from '../auth'

export function Projects() {
  const { username, logout } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [newName, setNewName] = useState('')
  const [creating, setCreating] = useState(false)

  const { data: projects = [], isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: api.listProjects,
    refetchInterval: 30_000,
  })

  const createMutation = useMutation({
    mutationFn: (name: string) => api.createProject(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setNewName('')
      setCreating(false)
    },
  })

  if (isLoading) return <p style={{ padding: 24 }}>Loading…</p>

  return (
    <div style={{ padding: 24, fontFamily: 'system-ui', maxWidth: 800, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>Projects</h1>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span style={{ color: '#666' }}>{username}</span>
          <button onClick={logout} style={{ cursor: 'pointer' }}>Log out</button>
        </div>
      </div>

      <div style={{ display: 'grid', gap: 12, marginBottom: 24 }}>
        {projects.map((p: Project) => (
          <div
            key={p.id}
            onClick={() => navigate(`/projects/${p.id}`)}
            style={{ padding: 16, border: '1px solid #ddd', borderRadius: 8, cursor: 'pointer' }}
          >
            <strong>{p.name}</strong>
            {p.description && <p style={{ margin: '4px 0 0', color: '#666', fontSize: 14 }}>{p.description}</p>}
            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#999' }}>
              {p.members.length} member{p.members.length !== 1 ? 's' : ''}
            </p>
          </div>
        ))}
        {projects.length === 0 && <p style={{ color: '#666' }}>No projects yet.</p>}
      </div>

      {creating ? (
        <form onSubmit={e => { e.preventDefault(); createMutation.mutate(newName) }} style={{ display: 'flex', gap: 8 }}>
          <input
            autoFocus value={newName} onChange={e => setNewName(e.target.value)}
            placeholder="Project name" required style={{ flex: 1, padding: 8 }}
          />
          <button type="submit" disabled={createMutation.isPending}>Create</button>
          <button type="button" onClick={() => setCreating(false)}>Cancel</button>
        </form>
      ) : (
        <button onClick={() => setCreating(true)} style={{ padding: '8px 16px', cursor: 'pointer' }}>
          + New Project
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Build**

```bash
cd EvoScientist/pm/frontend && npm run build
```

Expected: success.

- [ ] **Step 3: Commit**

```bash
cd ../../../
git add EvoScientist/pm/frontend/src/pages/Projects.tsx
git commit -m "feat(pm): add projects list page"
```

---

### Task 15: First-launch bootstrap page

**Files:**
- Create: `EvoScientist/pm/frontend/src/pages/Setup.tsx`
- Modify: `EvoScientist/pm/frontend/src/main.tsx`
- Modify: `EvoScientist/pm/api/routes/users.py` (add unauthenticated setup endpoint)

The spec requires: "On first launch of `EvoSci dashboard` (no users in DB), the React app shows a one-time 'Create Admin Account' setup page before the login screen."

- [ ] **Step 1: Add `GET /api/v1/setup/status` endpoint to `EvoScientist/pm/api/routes/users.py`**

Append to `users.py` (no auth required):

```python
@router.get("/setup/status")
def setup_status():
    """Return whether the system has been bootstrapped (any users exist)."""
    users = list_users(get_db_path())
    return {"needs_setup": len(users) == 0}

@router.post("/setup/admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_admin(body: UserCreate):
    """Create the first admin account. Returns 409 if any users already exist."""
    if list_users(get_db_path()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System already bootstrapped")
    user = create_user(get_db_path(), username=body.username, password_hash=hash_password(body.password), email=body.email, is_admin=True)
    return _to_response(user)
```

Also add the `/setup` prefix to the router mount in `app.py`:
```python
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
# The setup routes are mounted under /api/v1/users/setup/status and /api/v1/users/setup/admin
```

- [ ] **Step 2: Add `api.ts` methods**

In `src/api.ts`, add to the `api` object:

```typescript
  setupStatus: () => request<{ needs_setup: boolean }>('GET', '/users/setup/status'),
  createAdmin: (username: string, password: string, email?: string) =>
    request<{ id: string; username: string }>('POST', '/users/setup/admin', { username, password, email }),
```

- [ ] **Step 3: Create `EvoScientist/pm/frontend/src/pages/Setup.tsx`**

```tsx
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

export function Setup() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await api.createAdmin(username, password)
      await login(username, password)
      navigate('/projects')
    } catch (err: any) {
      setError(err.message ?? 'Setup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', fontFamily: 'system-ui' }}>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12, width: 320 }}>
        <h1 style={{ margin: 0 }}>Welcome to EvoScientist PM</h1>
        <p style={{ color: '#666', margin: 0 }}>Create the first admin account to get started.</p>
        {error && <p style={{ color: 'red', margin: 0 }}>{error}</p>}
        <input
          placeholder="Admin username" value={username} onChange={e => setUsername(e.target.value)}
          required style={{ padding: 8, fontSize: 14 }}
        />
        <input
          type="password" placeholder="Password (min 6 chars)" value={password} onChange={e => setPassword(e.target.value)}
          required minLength={6} style={{ padding: 8, fontSize: 14 }}
        />
        <button type="submit" disabled={loading} style={{ padding: 10, fontSize: 14, cursor: 'pointer' }}>
          {loading ? 'Creating…' : 'Create admin account'}
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 4: Update `src/main.tsx` to check setup status on load**

Replace the `App` function in `main.tsx` with:

```tsx
import { useEffect, useState } from 'react'
import { Setup } from './pages/Setup'

function App() {
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null)

  useEffect(() => {
    api.setupStatus().then(r => setNeedsSetup(r.needs_setup)).catch(() => setNeedsSetup(false))
  }, [])

  if (needsSetup === null) return <p style={{ padding: 24 }}>Loading…</p>

  return (
    <BrowserRouter>
      <Routes>
        {needsSetup && <Route path="*" element={<Setup />} />}
        <Route path="/login" element={<Login />} />
        <Route path="/projects" element={<PrivateRoute><Projects /></PrivateRoute>} />
        <Route path="/projects/:id" element={<PrivateRoute><Board /></PrivateRoute>} />
        {!needsSetup && <Route path="*" element={<Navigate to="/projects" replace />} />}
      </Routes>
    </BrowserRouter>
  )
}
```

Also add the `api` import:
```tsx
import { api } from './api'
```

- [ ] **Step 5: Build**

```bash
cd EvoScientist/pm/frontend && npm run build
```

Expected: success.

- [ ] **Step 6: Commit**

```bash
cd ../../../
git add EvoScientist/pm/api/routes/users.py EvoScientist/pm/frontend/src/
git commit -m "feat(pm): add first-launch admin setup page and bootstrap API endpoints"
```

---

### Task 16: Kanban board + Task detail

**Files:**
- Create: `EvoScientist/pm/frontend/src/pages/Board.tsx`
- Create: `EvoScientist/pm/frontend/src/pages/TaskDetail.tsx`

- [ ] **Step 1: Create `EvoScientist/pm/frontend/src/pages/TaskDetail.tsx`**

```tsx
import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task } from '../api'

interface Props {
  task: Task
  projectId: string
  onClose: () => void
}

export function TaskDetail({ task, projectId, onClose }: Props) {
  const queryClient = useQueryClient()
  const [commentBody, setCommentBody] = useState('')

  const { data: comments = [] } = useQuery({
    queryKey: ['comments', task.id],
    queryFn: () => api.listComments(projectId, task.id),
  })

  const addComment = useMutation({
    mutationFn: (body: string) => api.addComment(projectId, task.id, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comments', task.id] })
      setCommentBody('')
    },
  })

  const priorityColors = { high: '#ef4444', medium: '#f97316', low: '#22c55e' }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', justifyContent: 'flex-end' }} onClick={onClose}>
      <div style={{ background: '#fff', width: 480, height: '100%', overflowY: 'auto', padding: 24 }} onClick={e => e.stopPropagation()}>
        <button onClick={onClose} style={{ float: 'right', cursor: 'pointer', background: 'none', border: 'none', fontSize: 18 }}>✕</button>
        <h2 style={{ margin: '0 0 8px' }}>{task.title}</h2>

        <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
          <span style={{ padding: '2px 8px', borderRadius: 4, background: '#f3f4f6', fontSize: 13 }}>{task.status}</span>
          <span style={{ padding: '2px 8px', borderRadius: 4, background: priorityColors[task.priority], color: '#fff', fontSize: 13 }}>
            {task.priority}
          </span>
          {task.deadline && <span style={{ fontSize: 13, color: '#666' }}>Due {task.deadline}</span>}
        </div>

        {task.description && <p style={{ color: '#444', marginBottom: 16 }}>{task.description}</p>}

        {task.session_id && (
          <div style={{ background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: 6, padding: 10, marginBottom: 16 }}>
            <strong style={{ fontSize: 13 }}>Linked Session</strong>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              <code style={{ fontSize: 12, flex: 1 }}>{task.session_id}</code>
              <button onClick={() => navigator.clipboard.writeText(task.session_id!)} style={{ fontSize: 12, cursor: 'pointer' }}>
                Copy
              </button>
            </div>
            <p style={{ fontSize: 12, color: '#666', margin: '4px 0 0' }}>
              Resume in CLI: <code>EvoSci --resume {task.session_id}</code>
            </p>
          </div>
        )}

        <h3 style={{ marginBottom: 8 }}>Comments</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
          {comments.map(c => (
            <div key={c.id} style={{ background: '#f9fafb', borderRadius: 6, padding: 10 }}>
              <p style={{ margin: 0, fontSize: 14 }}>{c.body}</p>
              <p style={{ margin: '4px 0 0', fontSize: 12, color: '#999' }}>{c.created_at.slice(0, 10)}</p>
            </div>
          ))}
          {comments.length === 0 && <p style={{ color: '#999', fontSize: 14 }}>No comments yet.</p>}
        </div>

        <form onSubmit={e => { e.preventDefault(); addComment.mutate(commentBody) }} style={{ display: 'flex', gap: 8 }}>
          <input
            value={commentBody} onChange={e => setCommentBody(e.target.value)}
            placeholder="Add a comment…" style={{ flex: 1, padding: 8 }} required
          />
          <button type="submit" disabled={addComment.isPending}>Post</button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Create `EvoScientist/pm/frontend/src/pages/Board.tsx`**

```tsx
import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, Task } from '../api'
import { TaskDetail } from './TaskDetail'

const COLUMNS: { key: Task['status']; label: string }[] = [
  { key: 'todo', label: 'Todo' },
  { key: 'in_progress', label: 'In Progress' },
  { key: 'done', label: 'Done' },
]

const PRIORITY_DOT = { high: '#ef4444', medium: '#f97316', low: '#22c55e' }

export function Board() {
  const { id: projectId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [addingToCol, setAddingToCol] = useState<Task['status'] | null>(null)

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId!),
  })

  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => api.listTasks(projectId!),
    refetchInterval: 15_000,
  })

  const updateTask = useMutation({
    mutationFn: ({ taskId, data }: { taskId: string; data: Partial<Task> }) =>
      api.updateTask(projectId!, taskId, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks', projectId] }),
  })

  const createTask = useMutation({
    mutationFn: (title: string) => api.createTask(projectId!, { title, status: addingToCol ?? 'todo' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] })
      setNewTaskTitle('')
      setAddingToCol(null)
    },
  })

  return (
    <div style={{ fontFamily: 'system-ui', height: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '12px 24px', borderBottom: '1px solid #e5e7eb', display: 'flex', alignItems: 'center', gap: 16 }}>
        <button onClick={() => navigate('/projects')} style={{ cursor: 'pointer', background: 'none', border: 'none', fontSize: 20 }}>←</button>
        <h1 style={{ margin: 0, fontSize: 20 }}>{project?.name ?? '…'}</h1>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {project?.members.map(m => (
            <span key={m.user_id} title={`${m.username} (${m.role})`}
              style={{ width: 32, height: 32, borderRadius: '50%', background: '#6366f1', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, cursor: 'default' }}>
              {m.username[0].toUpperCase()}
            </span>
          ))}
        </div>
      </div>

      {/* Kanban columns */}
      <div style={{ display: 'flex', flex: 1, gap: 0, overflowX: 'auto', padding: 24, gap: 16 }}>
        {COLUMNS.map(col => {
          const colTasks = tasks.filter(t => t.status === col.key)
          return (
            <div key={col.key} style={{ flex: '0 0 300px', background: '#f3f4f6', borderRadius: 10, padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <strong>{col.label}</strong>
                <span style={{ fontSize: 13, color: '#666' }}>{colTasks.length}</span>
              </div>

              {colTasks.map(task => (
                <div key={task.id} onClick={() => setSelectedTask(task)}
                  style={{ background: '#fff', borderRadius: 8, padding: 12, cursor: 'pointer', boxShadow: '0 1px 3px rgba(0,0,0,.1)' }}>
                  <p style={{ margin: 0, fontWeight: 500 }}>{task.title}</p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: PRIORITY_DOT[task.priority] }} />
                    <span style={{ fontSize: 12, color: '#666' }}>{task.priority}</span>
                    {task.deadline && <span style={{ fontSize: 12, color: '#999', marginLeft: 'auto' }}>{task.deadline}</span>}
                  </div>
                </div>
              ))}

              {addingToCol === col.key ? (
                <form onSubmit={e => { e.preventDefault(); createTask.mutate(newTaskTitle) }}>
                  <input autoFocus value={newTaskTitle} onChange={e => setNewTaskTitle(e.target.value)}
                    placeholder="Task title" required style={{ width: '100%', padding: 8, boxSizing: 'border-box', marginBottom: 4 }} />
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button type="submit" style={{ flex: 1 }}>Add</button>
                    <button type="button" onClick={() => setAddingToCol(null)}>✕</button>
                  </div>
                </form>
              ) : (
                <button onClick={() => setAddingToCol(col.key)}
                  style={{ background: 'none', border: '1px dashed #d1d5db', borderRadius: 6, padding: 8, cursor: 'pointer', color: '#6b7280' }}>
                  + Add task
                </button>
              )}
            </div>
          )
        })}
      </div>

      {selectedTask && (
        <TaskDetail
          task={selectedTask}
          projectId={projectId!}
          onClose={() => setSelectedTask(null)}
        />
      )}
    </div>
  )
}
```

- [ ] **Step 3: Build the full frontend**

```bash
cd EvoScientist/pm/frontend && npm run build
```

Expected: `dist/` built successfully, no TypeScript errors.

- [ ] **Step 4: Verify the dashboard serves the SPA**

Start the server in one terminal:
```bash
uv run python -m EvoScientist.pm._run_server
```

In another terminal:
```bash
curl -s http://localhost:7860/ | grep -c "EvoScientist PM"
```

Expected: `1`

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest -v --timeout=30
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add EvoScientist/pm/frontend/src/pages/
git commit -m "feat(pm): add kanban board and task detail drawer"
```

---

### Task 16: Final integration and lint

- [ ] **Step 1: Run ruff**

```bash
uv run ruff check EvoScientist/pm/ EvoScientist/commands/pm_commands.py
```

Fix any issues reported. Common fixes:
- Remove unused imports
- Add `from __future__ import annotations` to any file missing it
- Fix f-string formatting

- [ ] **Step 2: Run ruff format**

```bash
uv run ruff format EvoScientist/pm/ EvoScientist/commands/pm_commands.py
```

- [ ] **Step 3: Run full test suite one final time**

```bash
uv run pytest -v --timeout=30
```

Expected: all tests pass.

- [ ] **Step 4: Final commit**

```bash
git add -u
git commit -m "chore(pm): fix lint issues and finalize project management feature"
```

- [ ] **Step 5: Verify end-to-end manually**

```bash
# Terminal 1 — start dashboard
uv run EvoSci dashboard --no-open

# Terminal 2 — bootstrap admin and smoke test
curl -s -X POST http://localhost:7860/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
# Should return 403 (no admin yet — first user is created via bootstrap)
# Open browser at http://localhost:7860 to complete setup
```

---

## Summary of deliverables

| Phase | What you get |
|-------|-------------|
| Phase 1 (Tasks 1–9) | Fully tested backend: DB, auth, CRUD, REST API with permission enforcement |
| Phase 2 (Tasks 10–11) | `EvoSci dashboard` command + `/project`, `/task`, `/user` CLI slash commands |
| Phase 3 (Tasks 12–16) | React SPA with login, project list, kanban board, task detail drawer |
