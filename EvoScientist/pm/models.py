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
