"""SQLite connection and schema management for the PM module."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from ..paths import DATA_DIR

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

CREATE TABLE IF NOT EXISTS researcher_pushes (
    -- The monotonic generation of each person's membership push to
    -- platform-control. It lives here rather than in a clock so that two
    -- pushes in the same second differ and a backwards clock changes nothing;
    -- platform-control refuses any generation it has already seen, which is
    -- what stops a delayed push from restoring a membership that ended.
    email      TEXT PRIMARY KEY,
    generation INTEGER NOT NULL
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
                  CHECK(priority IN ('critical', 'high', 'medium', 'low')),
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
                CHECK(status IN ('planned', 'running', 'completed', 'abandoned')),
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
    created_at    TEXT NOT NULL,
    classification TEXT NOT NULL DEFAULT 'unclassified'
);

CREATE INDEX IF NOT EXISTS idx_attachments_entry ON attachments(entry_id);

-- Structured experiment results. Paper drafting takes its numbers from here
-- and nowhere else, so an unrecorded number cannot reach a manuscript.
CREATE TABLE IF NOT EXISTS experiment_metrics (
    id            TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    value         REAL NOT NULL,
    unit          TEXT,
    split         TEXT,
    n             INTEGER,
    stderr        REAL,
    source_attachment_id TEXT REFERENCES attachments(id) ON DELETE SET NULL,
    recorded_by   TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_experiment_metrics_exp ON experiment_metrics(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_metrics_src
    ON experiment_metrics(source_attachment_id);

-- Data lineage for an experiment: the cohort it consumed, the pipeline run that
-- processed it, the annotation/segmentation it produced, and the sandbox it ran
-- in. Those assets are owned by projects (or, for datasets, by a lab with a grant
-- to a project), so a link table is what lets one experiment cite them without
-- moving ownership. asset_id carries no FK because the target table varies; the
-- link routes validate existence, and each asset's delete route clears its links.
CREATE TABLE IF NOT EXISTS experiment_assets (
    experiment_id TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    asset_type    TEXT NOT NULL
                  CHECK(asset_type IN ('dataset','pipeline_run','cvat_project',
                                       'webknossos_dataset','sandbox')),
    asset_id      TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'input'
                  CHECK(role IN ('input','processing','output','reference')),
    note          TEXT,
    linked_at     TEXT NOT NULL,
    linked_by     TEXT NOT NULL REFERENCES users(id),
    PRIMARY KEY (experiment_id, asset_type, asset_id)
);

CREATE INDEX IF NOT EXISTS idx_experiment_assets_exp ON experiment_assets(experiment_id);
CREATE INDEX IF NOT EXISTS idx_experiment_assets_asset
    ON experiment_assets(asset_type, asset_id);


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
    role      TEXT NOT NULL CHECK(role IN ('pi', 'postdoc', 'phd', 'ms', 'visitor', 'technician', 'admin')),
    joined_at TEXT NOT NULL,
    PRIMARY KEY (lab_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_labs_pi ON labs(pi_id);
CREATE INDEX IF NOT EXISTS idx_lab_members_user ON lab_members(user_id);

CREATE TABLE IF NOT EXISTS publications (
    id            TEXT PRIMARY KEY,
    project_id    TEXT REFERENCES projects(id) ON DELETE SET NULL,
    title         TEXT NOT NULL,
    venue         TEXT,
    venue_type    TEXT NOT NULL DEFAULT 'journal'
                  CHECK(venue_type IN ('journal', 'conference', 'preprint', 'other')),
    authors       TEXT NOT NULL DEFAULT '[]',
    status        TEXT NOT NULL DEFAULT 'draft'
                  CHECK(status IN ('draft', 'submitted', 'reviewing', 'accepted', 'published', 'rejected')),
    doi           TEXT,
    url           TEXT,
    abstract      TEXT,
    submitted_at  TEXT,
    accepted_at   TEXT,
    published_at  TEXT,
    created_by    TEXT NOT NULL REFERENCES users(id),
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publication_versions (
    id              TEXT PRIMARY KEY,
    publication_id  TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    file_path       TEXT,
    notes           TEXT,
    created_by      TEXT NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publication_reviews (
    id              TEXT PRIMARY KEY,
    publication_id  TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
    reviewer_name   TEXT,
    comments        TEXT,
    decision        TEXT CHECK(decision IN ('accept', 'minor_revision', 'major_revision', 'reject')),
    round           INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_publications_project ON publications(project_id);
CREATE INDEX IF NOT EXISTS idx_publications_status ON publications(status);
CREATE TABLE IF NOT EXISTS publication_experiments (
    publication_id  TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
    experiment_id   TEXT NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
    section         TEXT,
    linked_at       TEXT NOT NULL,
    PRIMARY KEY (publication_id, experiment_id)
);

CREATE INDEX IF NOT EXISTS idx_pub_exp_pub ON publication_experiments(publication_id);
CREATE INDEX IF NOT EXISTS idx_pub_exp_exp ON publication_experiments(experiment_id);

CREATE INDEX IF NOT EXISTS idx_pub_versions_pub ON publication_versions(publication_id);
CREATE INDEX IF NOT EXISTS idx_pub_reviews_pub ON publication_reviews(publication_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id           TEXT PRIMARY KEY,
    user_id      TEXT REFERENCES users(id) ON DELETE SET NULL,
    action       TEXT NOT NULL,
    entity_type  TEXT NOT NULL,
    entity_id    TEXT,
    details      TEXT,
    ip_address   TEXT,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);

CREATE TABLE IF NOT EXISTS grants (
    id              TEXT PRIMARY KEY,
    lab_id          TEXT REFERENCES labs(id) ON DELETE SET NULL,
    project_id      TEXT REFERENCES projects(id) ON DELETE SET NULL,
    title           TEXT NOT NULL,
    funder          TEXT NOT NULL,
    amount_requested REAL,
    amount_awarded  REAL,
    currency        TEXT NOT NULL DEFAULT 'TRY',
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK(status IN ('draft','submitted','under_review','awarded','rejected','active','closed')),
    submitted_at    TEXT,
    awarded_at      TEXT,
    start_date      TEXT,
    end_date        TEXT,
    description     TEXT,
    pi_id           TEXT REFERENCES users(id) ON DELETE SET NULL,
    created_by      TEXT NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_grants_lab ON grants(lab_id);
CREATE INDEX IF NOT EXISTS idx_grants_project ON grants(project_id);

CREATE TABLE IF NOT EXISTS grant_budget_items (
    id             TEXT PRIMARY KEY,
    grant_id       TEXT NOT NULL REFERENCES grants(id) ON DELETE CASCADE,
    category       TEXT NOT NULL DEFAULT 'other'
                   CHECK(category IN ('personnel','equipment','consumables','travel','services','other')),
    description    TEXT,
    planned_amount REAL NOT NULL DEFAULT 0,
    spent_amount   REAL NOT NULL DEFAULT 0,
    position       INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_grant_budget_grant ON grant_budget_items(grant_id);

CREATE TABLE IF NOT EXISTS grant_milestones (
    id           TEXT PRIMARY KEY,
    grant_id     TEXT NOT NULL REFERENCES grants(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'milestone'
                 CHECK(kind IN ('milestone','report','deliverable')),
    due_date     TEXT,
    completed_at TEXT,
    owner_id     TEXT REFERENCES users(id) ON DELETE SET NULL,
    notes        TEXT,
    position     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_grant_milestones_grant ON grant_milestones(grant_id);

CREATE TABLE IF NOT EXISTS grant_members (
    id            TEXT PRIMARY KEY,
    grant_id      TEXT NOT NULL REFERENCES grants(id) ON DELETE CASCADE,
    user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role          TEXT NOT NULL DEFAULT 'researcher'
                  CHECK(role IN ('pi','co_pi','researcher','assistant','advisor')),
    share_percent REAL,
    added_at      TEXT NOT NULL,
    UNIQUE(grant_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_grant_members_grant ON grant_members(grant_id);

CREATE TABLE IF NOT EXISTS conferences (
    id              TEXT PRIMARY KEY,
    project_id      TEXT REFERENCES projects(id) ON DELETE SET NULL,
    publication_id  TEXT REFERENCES publications(id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    venue           TEXT,
    location        TEXT,
    deadline        TEXT,
    submission_date TEXT,
    decision_date   TEXT,
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK(status IN ('draft','submitted','under_review','accepted','rejected','presented')),
    presentation_type TEXT DEFAULT 'poster'
                    CHECK(presentation_type IN ('poster','oral','spotlight','workshop','demo')),
    travel_funding  REAL,
    travel_notes    TEXT,
    url             TEXT,
    notes           TEXT,
    created_by      TEXT NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS irb_approvals (
    id              TEXT PRIMARY KEY,
    project_id      TEXT REFERENCES projects(id) ON DELETE CASCADE,
    institution     TEXT NOT NULL,
    protocol_number TEXT NOT NULL,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'draft'
                    CHECK(status IN ('draft','submitted','approved','rejected','expired','closed')),
    approval_date   TEXT,
    expiry_date     TEXT,
    renewal_date    TEXT,
    documents       TEXT DEFAULT '[]',
    notes           TEXT,
    created_by      TEXT NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lab_wiki_pages (
    id              TEXT PRIMARY KEY,
    lab_id          TEXT NOT NULL REFERENCES labs(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    slug            TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    tags            TEXT DEFAULT '[]',
    created_by      TEXT NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    UNIQUE(lab_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_grants_lab ON grants(lab_id);
CREATE INDEX IF NOT EXISTS idx_grants_status ON grants(status);
CREATE INDEX IF NOT EXISTS idx_conferences_project ON conferences(project_id);
CREATE INDEX IF NOT EXISTS idx_conferences_status ON conferences(status);
CREATE INDEX IF NOT EXISTS idx_irb_project ON irb_approvals(project_id);
CREATE INDEX IF NOT EXISTS idx_wiki_lab ON lab_wiki_pages(lab_id);

CREATE INDEX IF NOT EXISTS idx_admissions_status ON admissions(status);
CREATE INDEX IF NOT EXISTS idx_admissions_form_id ON admissions(form_submission_id);

-- De-identification pipelines
CREATE TABLE IF NOT EXISTS deid_pipelines (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    description     TEXT,
    pipeline_type   TEXT NOT NULL CHECK(pipeline_type IN ('dicom','ehr','text','image','generic')),
    config_json     TEXT NOT NULL DEFAULT '{}',
    created_by      TEXT NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deid_pipeline_runs (
    id              TEXT PRIMARY KEY,
    pipeline_id     TEXT NOT NULL REFERENCES deid_pipelines(id) ON DELETE CASCADE,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    irb_id          TEXT REFERENCES irb_approvals(id),
    input_location  TEXT NOT NULL,
    output_location TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','running','completed','failed','verified')),
    input_size_bytes    INTEGER,
    output_size_bytes   INTEGER,
    records_processed   INTEGER,
    phi_fields_removed  TEXT DEFAULT '[]',
    verification_status TEXT CHECK(verification_status IN ('pending','passed','failed')),
    verification_notes  TEXT,
    error           TEXT,
    started_at      TEXT,
    completed_at    TEXT,
    created_by      TEXT NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL
);

-- Sandboxes
CREATE TABLE IF NOT EXISTS sandboxes (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    irb_id          TEXT REFERENCES irb_approvals(id),
    name            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'provisioning'
                    CHECK(status IN ('provisioning','active','expiring','expired','terminated')),
    spec_json       TEXT NOT NULL DEFAULT '{}',
    network_rules_json  TEXT DEFAULT '[]',
    storage_quota_bytes INTEGER,
    access_url      TEXT,
    provisioned_at  TEXT,
    expires_at      TEXT,
    terminated_at   TEXT,
    created_by      TEXT NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- Export requests
CREATE TABLE IF NOT EXISTS export_requests (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    sandbox_id      TEXT REFERENCES sandboxes(id),
    requested_by    TEXT NOT NULL REFERENCES users(id),
    reviewed_by     TEXT REFERENCES users(id),
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','approved','rejected')),
    file_name       TEXT NOT NULL,
    file_type       TEXT NOT NULL CHECK(file_type IN ('model_weights','aggregate_figure','coefficient_table','annotation_stats','documentation','other')),
    file_size_bytes INTEGER,
    description     TEXT,
    justification   TEXT,
    reviewer_notes  TEXT,
    reviewed_at     TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_deid_pipeline_project ON deid_pipelines(project_id);
CREATE INDEX IF NOT EXISTS idx_deid_runs_pipeline ON deid_pipeline_runs(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_deid_runs_status ON deid_pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_sandboxes_project ON sandboxes(project_id);
CREATE INDEX IF NOT EXISTS idx_sandboxes_status ON sandboxes(status);
CREATE INDEX IF NOT EXISTS idx_sandboxes_irb ON sandboxes(irb_id);
CREATE INDEX IF NOT EXISTS idx_export_requests_project ON export_requests(project_id);
CREATE INDEX IF NOT EXISTS idx_export_requests_status ON export_requests(status);

-- Task history (audit trail for status changes)
CREATE TABLE IF NOT EXISTS task_history (
    id              TEXT PRIMARY KEY,
    task_id         TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    changed_by      TEXT REFERENCES users(id),
    from_status     TEXT,
    to_status       TEXT,
    change_type     TEXT NOT NULL DEFAULT 'status'
                    CHECK(change_type IN ('status', 'assignee', 'priority', 'phase', 'other')),
    comment         TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_task_history_task ON task_history(task_id);

-- CVAT project links
CREATE TABLE IF NOT EXISTS cvat_projects (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    cvat_id         INTEGER NOT NULL,
    name            TEXT NOT NULL,
    labels_json     TEXT DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'created'
                    CHECK(status IN ('created', 'importing', 'annotating', 'reviewing', 'exported', 'completed')),
    num_images      INTEGER DEFAULT 0,
    num_annotations INTEGER DEFAULT 0,
    export_format   TEXT DEFAULT 'COCO 1.0',
    export_key      TEXT,
    created_by      TEXT NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- WebKnossos dataset links
CREATE TABLE IF NOT EXISTS webknossos_datasets (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    wk_id           TEXT,
    name            TEXT NOT NULL,
    directory_name  TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'imported'
                    CHECK(status IN ('imported', 'segmenting', 'proofreading', 'completed', 'archived')),
    voxel_count     TEXT,
    segmentation_status TEXT DEFAULT 'pending',
    num_skeletons   INTEGER DEFAULT 0,
    num_volumes     INTEGER DEFAULT 0,
    created_by      TEXT NOT NULL REFERENCES users(id),
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cvat_project ON cvat_projects(project_id);
CREATE INDEX IF NOT EXISTS idx_webknossos_project ON webknossos_datasets(project_id);

-- ── Imaging datasets (v2 storage model, 20 Aug 2026) ──────────────────────────
-- A dataset is the governance record of ONE delivered imaging cohort. The row
-- exists BEFORE any bucket does; Curator refuses a C-MOVE without an 'approved'
-- dataset id, and the bucket manifest is a copy of this row. RESTRICT (not
-- CASCADE) everywhere: governance history must never vanish as a side effect.
CREATE TABLE IF NOT EXISTS datasets (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    purpose             TEXT NOT NULL,
    lab_id              TEXT NOT NULL REFERENCES labs(id) ON DELETE RESTRICT,
    requested_by        TEXT NOT NULL REFERENCES users(id),
    modality            TEXT,
    accession_list      TEXT NOT NULL DEFAULT '[]',
    estimated_bytes     INTEGER,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK(status IN ('draft','pi_approved','approved','delivering','sealed','expired','revoked')),
    pi_approved_by      TEXT REFERENCES users(id),
    pi_approved_at      TEXT,
    admin_approved_by   TEXT REFERENCES users(id),
    admin_approved_at   TEXT,
    retention_until     TEXT,
    pepper_generation   INTEGER NOT NULL DEFAULT 1,
    bucket              TEXT,
    sealed_at           TEXT,
    content_root_sha256 TEXT,
    generation          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_datasets_lab ON datasets(lab_id);

CREATE TABLE IF NOT EXISTS dataset_irbs (
    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE RESTRICT,
    irb_id     TEXT NOT NULL REFERENCES irb_approvals(id) ON DELETE RESTRICT,
    PRIMARY KEY (dataset_id, irb_id)
);

CREATE TABLE IF NOT EXISTS dataset_grants (
    id                TEXT PRIMARY KEY,
    dataset_id        TEXT NOT NULL REFERENCES datasets(id) ON DELETE RESTRICT,
    project_id        TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    granted_by        TEXT NOT NULL REFERENCES users(id),
    admin_approved_by TEXT REFERENCES users(id),
    admin_approved_at TEXT,
    granted_at        TEXT NOT NULL,
    expires_at        TEXT,
    revoked_at        TEXT,
    revoked_by        TEXT REFERENCES users(id),
    UNIQUE(dataset_id, project_id)
);
CREATE INDEX IF NOT EXISTS idx_dataset_grants_ds ON dataset_grants(dataset_id);

-- Per-IP rate-limit tracking (SQLite-backed for multi-worker support)
CREATE TABLE IF NOT EXISTS rate_limits (
    ip           TEXT NOT NULL,
    requested_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_limits_ip ON rate_limits(ip);
CREATE INDEX IF NOT EXISTS idx_rate_limits_time ON rate_limits(requested_at);
"""

_MIGRATIONS = [
    "ALTER TABLE tasks ADD COLUMN phase_id TEXT REFERENCES project_phases(id) ON DELETE SET NULL",
    "ALTER TABLE experiments ADD COLUMN phase_id TEXT REFERENCES project_phases(id) ON DELETE SET NULL",
    "ALTER TABLE admissions ADD COLUMN aid_percentage REAL",
    "ALTER TABLE admissions ADD COLUMN aid_notes TEXT",
    "ALTER TABLE admissions ADD COLUMN aid_at TEXT",
    "ALTER TABLE projects ADD COLUMN lab_id TEXT REFERENCES labs(id) ON DELETE SET NULL",
    "ALTER TABLE experiment_assists ADD COLUMN agent_type TEXT NOT NULL DEFAULT 'writing'",
    "ALTER TABLE attachments ADD COLUMN classification TEXT NOT NULL DEFAULT 'unclassified'",
    "ALTER TABLE sandboxes ADD COLUMN terminated_by TEXT REFERENCES users(id)",
    "ALTER TABLE irb_approvals ADD COLUMN sandbox_id TEXT REFERENCES sandboxes(id)",
    # Drafts live in the DB, not only as a server-local file path no client can read.
    "ALTER TABLE publication_versions ADD COLUMN content TEXT",
    "ALTER TABLE publication_versions ADD COLUMN section TEXT",
    # AI provenance — required to produce a truthful journal disclosure statement.
    "ALTER TABLE publication_versions ADD COLUMN generated_by TEXT",
    "ALTER TABLE publication_versions ADD COLUMN model TEXT",
    "ALTER TABLE publication_versions ADD COLUMN prompt_hash TEXT",
    # IRB decisions record WHO approved — the audit anchor for PHI releases.
    "ALTER TABLE irb_approvals ADD COLUMN approved_by TEXT REFERENCES users(id)",
    "ALTER TABLE irb_approvals ADD COLUMN approved_at TEXT",
    # Membership becomes a LIFECYCLE, not a row that vanishes: an ended membership must stay
    # computable so the cluster-side reconciler can REVOKE what it once granted (CVAT org
    # membership, bucket read). A deleted row is an absence nothing can act on.
    "ALTER TABLE lab_members ADD COLUMN ended_at TEXT",
    # v2 imaging: whether Curator derives viewing PNGs during delivery (a pure-ML cohort says no),
    # and per-grant annotation staging intent (requested by a human, converged by the platform).
    "ALTER TABLE datasets ADD COLUMN renders INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE dataset_grants ADD COLUMN cvat_project_id INTEGER",
    "ALTER TABLE dataset_grants ADD COLUMN task_size INTEGER",
]


def get_db_path() -> Path:
    """Return path to the PM SQLite database, creating parent dirs.

    Override with ``EVOSCIENTIST_PM_DB`` env var (e.g. ``/data/pm.db`` in Docker).
    Falls back to ``DATA_DIR / "projects.db"``.
    """
    env_path = os.environ.get("EVOSCIENTIST_PM_DB")
    if env_path:
        path = Path(env_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "projects.db"


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
