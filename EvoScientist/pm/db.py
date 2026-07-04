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

CREATE TABLE IF NOT EXISTS runs (
    id           TEXT PRIMARY KEY,
    task_id      TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
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

CREATE TABLE IF NOT EXISTS experiments (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    hypothesis  TEXT,
    protocol    TEXT,
    status      TEXT NOT NULL DEFAULT 'planned'
                CHECK(status IN ('planned', 'running', 'completed')),
    tags        TEXT NOT NULL DEFAULT '[]',
    deadline    TEXT,
    created_by  TEXT NOT NULL REFERENCES users(id),
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_tasks (
    experiment_id  TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    task_id        TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    linked_at      TEXT NOT NULL,
    linked_by      TEXT NOT NULL REFERENCES users(id),
    PRIMARY KEY (experiment_id, task_id)
);

CREATE TABLE IF NOT EXISTS experiment_entries (
    id             TEXT PRIMARY KEY,
    experiment_id  TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    type           TEXT NOT NULL CHECK(type IN ('note', 'result')),
    title          TEXT NOT NULL,
    body           TEXT NOT NULL DEFAULT '',
    author_id      TEXT REFERENCES users(id),
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

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

CREATE TABLE IF NOT EXISTS project_phases (
    id          TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    color       TEXT NOT NULL DEFAULT '#6366f1',
    position    INTEGER NOT NULL DEFAULT 0,
    target_date TEXT,
    created_by  TEXT NOT NULL REFERENCES users(id),
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_phases_project ON project_phases(project_id);

CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id       TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    depends_on_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    dep_type      TEXT NOT NULL DEFAULT 'hard'
                  CHECK(dep_type IN ('hard', 'soft')),
    created_by    TEXT NOT NULL REFERENCES users(id),
    created_at    TEXT NOT NULL,
    PRIMARY KEY (task_id, depends_on_id)
);

CREATE TABLE IF NOT EXISTS attachments (
    id            TEXT PRIMARY KEY,
    entry_id      TEXT NOT NULL REFERENCES experiment_entries(id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    s3_key        TEXT NOT NULL,
    content_type  TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    uploaded_by   TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attachments_entry ON attachments(entry_id);

CREATE TABLE IF NOT EXISTS admissions (
    id                 TEXT PRIMARY KEY,
    form_submission_id INTEGER,
    applicant_name     TEXT NOT NULL,
    supervisor         TEXT,
    email              TEXT NOT NULL,
    phone              TEXT,
    university         TEXT,
    department         TEXT,
    service_areas      TEXT NOT NULL DEFAULT '',
    modas_members      TEXT NOT NULL DEFAULT '',
    grant_context      TEXT,
    comments           TEXT,
    status             TEXT NOT NULL DEFAULT 'submitted'
                       CHECK(status IN ('submitted', 'reviewing', 'accepted', 'rejected')),
    reviewer_id        TEXT REFERENCES users(id) ON DELETE SET NULL,
    review_notes       TEXT,
    reviewed_at        TEXT,
    created_project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
    aid_percentage    REAL
                      CHECK(aid_percentage IS NULL OR (aid_percentage >= 0 AND aid_percentage <= 100)),
    aid_notes         TEXT,
    aid_at            TEXT,
    imported_at        TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS labs (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    pi_id         TEXT REFERENCES users(id) ON DELETE SET NULL,
    department    TEXT NOT NULL DEFAULT '',
    university    TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lab_members (
    lab_id    TEXT NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    user_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role      TEXT NOT NULL CHECK(role IN ('pi', 'postdoc', 'phd', 'ms', 'visitor')),
    joined_at TEXT NOT NULL,
    PRIMARY KEY (lab_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_labs_pi ON labs(pi_id);
CREATE INDEX IF NOT EXISTS idx_lab_members_user ON lab_members(user_id);

CREATE INDEX IF NOT EXISTS idx_admissions_status ON admissions(status);
CREATE INDEX IF NOT EXISTS idx_admissions_form_id ON admissions(form_submission_id);
"""

_MIGRATIONS = [
    "ALTER TABLE tasks ADD COLUMN phase_id TEXT REFERENCES project_phases(id) ON DELETE SET NULL",
    "ALTER TABLE experiments ADD COLUMN phase_id TEXT REFERENCES project_phases(id) ON DELETE SET NULL",
    "ALTER TABLE admissions ADD COLUMN aid_percentage REAL",
    "ALTER TABLE admissions ADD COLUMN aid_notes TEXT",
    "ALTER TABLE admissions ADD COLUMN aid_at TEXT",
    "ALTER TABLE projects ADD COLUMN lab_id TEXT REFERENCES labs(id) ON DELETE SET NULL",
]


def get_db_path() -> Path:
    """Return path to the PM SQLite database, creating parent dirs.

    Override with ``EVOSCIENTIST_PM_DB`` env var (e.g. ``/data/pm.db`` in Docker).
    """
    import os
    env_path = os.environ.get("EVOSCIENTIST_PM_DB")
    if env_path:
        path = Path(env_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    db_dir = Path.home() / ".config" / "evoscientist"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "projects.db"


def create_schema(db_path: Path | None = None) -> None:
    """Create all PM tables if they don't already exist (idempotent)."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(_SCHEMA)
        for migration in _MIGRATIONS:
            try:
                conn.execute(migration)
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise
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
