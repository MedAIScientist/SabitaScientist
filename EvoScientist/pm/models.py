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
    target_field: str | None = None   # 'hypothesis'|'protocol'|'entry_body'|None
    finished_at: str | None = None
