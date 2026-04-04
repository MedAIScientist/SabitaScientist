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
