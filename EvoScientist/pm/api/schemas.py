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


class UserSearchResult(BaseModel):
    id: str
    username: str


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
    deadline: str | None = None  # ISO date YYYY-MM-DD
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
    phase_id: str | None = None
    blocked_by: list[str] = []


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)


class CommentResponse(BaseModel):
    id: str
    task_id: str
    author_id: str | None
    body: str
    created_at: str


# ── Runs ──────────────────────────────────────────────────────────────────────


class RunCreate(BaseModel):
    agent_type: str = Field(pattern="^(research|code|data_analysis|writing)$")
    prompt: str = Field(min_length=1, max_length=4096)


class RunResponse(BaseModel):
    id: str
    task_id: str
    project_id: str
    agent_type: str
    prompt: str
    status: str
    output: str | None
    error: str | None
    started_at: str | None
    finished_at: str | None
    created_by: str
    created_at: str


# ── Experiments ───────────────────────────────────────────────────────────────


class ExperimentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hypothesis: str | None = None
    protocol: str | None = None
    status: str = Field(default="planned", pattern="^(planned|running|completed)$")
    tags: list[str] = []
    deadline: str | None = None


class ExperimentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    hypothesis: str | None = None
    protocol: str | None = None
    status: str | None = Field(default=None, pattern="^(planned|running|completed)$")
    tags: list[str] | None = None
    deadline: str | None = None
    phase_id: str | None = None


class ExperimentResponse(BaseModel):
    id: str
    project_id: str
    name: str
    hypothesis: str | None
    protocol: str | None
    status: str
    tags: list[str]
    deadline: str | None
    created_by: str
    created_at: str
    updated_at: str
    phase_id: str | None = None


class ExperimentEntryCreate(BaseModel):
    type: str = Field(pattern="^(note|result)$")
    title: str = Field(min_length=1, max_length=200)
    body: str = ""


class ExperimentEntryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None


class ExperimentEntryResponse(BaseModel):
    id: str
    experiment_id: str
    type: str
    title: str
    body: str
    author_id: str | None
    created_at: str
    updated_at: str


# ── Attachments ───────────────────────────────────────────────────────────────


class AttachmentResponse(BaseModel):
    id: str
    entry_id: str
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by: str | None
    created_at: str
    download_url: str  # presigned S3 URL


# ── Errors ────────────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    detail: str
    status: int
    type: str = "about:blank"


# ── Assists ───────────────────────────────────────────────────────────────────


class AssistCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=4096)
    target_field: str | None = Field(
        default=None,
        pattern="^(hypothesis|protocol|entry_body)$",
    )


class AssistResponse(BaseModel):
    id: str
    experiment_id: str
    project_id: str
    prompt: str
    status: str
    output: str | None
    error: str | None
    target_field: str | None
    created_by: str
    created_at: str
    finished_at: str | None


# ── Phases ────────────────────────────────────────────────────────────────────


class PhaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str = Field(default="#6366f1", pattern=r"^#[0-9a-fA-F]{6}$")
    position: int = Field(default=0, ge=0)
    target_date: str | None = Field(default=None)  # ISO date string YYYY-MM-DD or None


class PhaseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    position: int | None = Field(default=None, ge=0)
    target_date: str | None = Field(default=None)


class PhaseResponse(BaseModel):
    id: str
    project_id: str
    name: str
    color: str
    position: int
    target_date: str | None
    created_by: str
    created_at: str


class AssignPhaseRequest(BaseModel):
    task_id: str


# ── Dependencies ──────────────────────────────────────────────────────────────


class DependencyCreate(BaseModel):
    depends_on_id: str
    dep_type: str = Field(default="hard", pattern=r"^(hard|soft)$")


class DependencyResponse(BaseModel):
    task_id: str
    depends_on_id: str
    dep_type: str
    created_by: str
    created_at: str


class DependenciesListResponse(BaseModel):
    dependencies: list[DependencyResponse]
    dependents: list[DependencyResponse]
