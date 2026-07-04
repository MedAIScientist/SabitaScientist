"""Dataclasses representing PM domain entities."""

from __future__ import annotations

from dataclasses import dataclass


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
    lab_id: str | None = None


@dataclass
class Member:
    project_id: str
    user_id: str
    role: str  # 'owner' | 'editor' | 'viewer'
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
    status: str = "todo"  # 'todo' | 'in_progress' | 'done'
    priority: str = "medium"  # 'high' | 'medium' | 'low'
    deadline: str | None = None  # ISO date string
    session_id: str | None = None  # optional link to sessions.db thread_id
    phase_id: str | None = None


@dataclass
class Comment:
    id: str
    task_id: str
    body: str
    created_at: str
    author_id: str | None = None


@dataclass
class Run:
    id: str
    task_id: str
    project_id: str
    agent_type: str       # 'research' | 'code' | 'data_analysis' | 'writing'
    prompt: str
    status: str           # 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
    created_by: str
    created_at: str
    output: str | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass
class Experiment:
    id: str
    project_id: str
    name: str
    status: str           # 'planned' | 'running' | 'completed'
    tags: list[str]
    created_by: str
    created_at: str
    updated_at: str
    hypothesis: str | None = None
    protocol: str | None = None
    deadline: str | None = None
    phase_id: str | None = None


@dataclass
class ExperimentEntry:
    id: str
    experiment_id: str
    type: str             # 'note' | 'result'
    title: str
    body: str
    created_at: str
    updated_at: str
    author_id: str | None = None


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
    agent_type: str = "writing"      # 'research'|'code'|'data_analysis'|'writing'
    target_field: str | None = None  # 'hypothesis'|'protocol'|'entry_body'|None
    finished_at: str | None = None


@dataclass
class ProjectPhase:
    id: str
    project_id: str
    name: str
    color: str
    position: int
    created_by: str
    created_at: str
    target_date: str | None = None


@dataclass
class TaskDependency:
    task_id: str
    depends_on_id: str
    dep_type: str
    created_by: str
    created_at: str


@dataclass
class Attachment:
    id: str
    entry_id: str
    filename: str
    s3_key: str
    content_type: str
    size_bytes: int
    created_at: str
    uploaded_by: str | None = None


@dataclass
class Lab:
    id: str
    name: str
    pi_id: str | None
    department: str
    university: str
    created_at: str
    updated_at: str


@dataclass
class LabMember:
    lab_id: str
    user_id: str
    role: str  # pi | postdoc | phd | ms | visitor
    joined_at: str


@dataclass
class Publication:
    id: str
    title: str
    status: str       # draft|submitted|reviewing|accepted|published|rejected
    authors: list[dict]
    created_by: str
    created_at: str
    updated_at: str
    project_id: str | None = None
    venue: str | None = None
    venue_type: str = "journal"
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    submitted_at: str | None = None
    accepted_at: str | None = None
    published_at: str | None = None


@dataclass
class PublicationVersion:
    id: str
    publication_id: str
    version: int
    notes: str | None
    created_by: str
    created_at: str
    file_path: str | None = None


@dataclass
class PublicationReview:
    id: str
    publication_id: str
    round: int
    created_at: str
    reviewer_name: str | None = None
    comments: str | None = None
    decision: str | None = None  # accept|minor_revision|major_revision|reject


@dataclass
class AuditLogEntry:
    id: str
    user_id: str | None
    action: str
    entity_type: str
    entity_id: str | None
    details: str | None
    ip_address: str | None
    created_at: str


@dataclass
class Admission:
    id: str
    applicant_name: str
    email: str
    service_areas: str
    modas_members: str
    imported_at: str
    created_at: str
    updated_at: str
    status: str = "submitted"  # submitted|reviewing|accepted|rejected
    form_submission_id: int | None = None
    supervisor: str | None = None
    phone: str | None = None
    university: str | None = None
    department: str | None = None
    grant_context: str | None = None
    comments: str | None = None
    reviewer_id: str | None = None
    review_notes: str | None = None
    reviewed_at: str | None = None
    created_project_id: str | None = None
    aid_percentage: float | None = None
    aid_notes: str | None = None
    aid_at: str | None = None
