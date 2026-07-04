"""Pydantic request/response models for the PM API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgentType = Literal["research", "code", "data_analysis", "writing"]

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
    lab_id: str | None = None


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
    lab_id: str | None = None
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


# ── Admissions ─────────────────────────────────────────────────────────────────


class AdmissionUpdate(BaseModel):
    reviewer_id: str | None = None
    review_notes: str | None = None


class AdmissionAcceptRequest(BaseModel):
    notes: str | None = None


class AdmissionRejectRequest(BaseModel):
    notes: str = Field(min_length=1, max_length=4096)


class FinancialAidRequest(BaseModel):
    aid_percentage: float = Field(ge=0, le=100)
    notes: str | None = None


class AdmissionResponse(BaseModel):
    id: str
    form_submission_id: int | None
    applicant_name: str
    supervisor: str | None
    email: str
    phone: str | None
    university: str | None
    department: str | None
    service_areas: str
    modas_members: str
    grant_context: str | None
    comments: str | None
    status: str
    reviewer_id: str | None
    review_notes: str | None
    reviewed_at: str | None
    created_project_id: str | None
    aid_percentage: float | None
    aid_notes: str | None
    aid_at: str | None
    imported_at: str
    created_at: str
    updated_at: str


class AdmissionImportResponse(BaseModel):
    imported: int
    skipped: int
    admission_ids: list[str]


# ── Labs ──────────────────────────────────────────────────────────────────────


class LabCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    department: str = ""
    university: str = ""


class LabUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    pi_id: str | None = None
    department: str | None = None
    university: str | None = None


class LabMemberResponse(BaseModel):
    user_id: str
    username: str
    role: str
    joined_at: str


class LabResponse(BaseModel):
    id: str
    name: str
    pi_id: str | None
    department: str
    university: str
    created_at: str
    updated_at: str
    members: list[LabMemberResponse] = []


class AddLabMemberRequest(BaseModel):
    user_id: str
    role: str = Field(pattern="^(pi|postdoc|phd|ms|visitor)$")


# ── Publications ────────────────────────────────────────────────────────────────


class PublicationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    project_id: str | None = None
    venue: str | None = None
    venue_type: str = Field(default="journal", pattern="^(journal|conference|preprint|other)$")
    authors: list[dict] = []
    abstract: str | None = None
    doi: str | None = None
    url: str | None = None


class PublicationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    venue: str | None = None
    venue_type: str | None = Field(default=None, pattern="^(journal|conference|preprint|other)$")
    authors: list[dict] | None = None
    abstract: str | None = None
    doi: str | None = None
    url: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|submitted|reviewing|accepted|published|rejected)$")


class PublicationResponse(BaseModel):
    id: str
    project_id: str | None
    title: str
    venue: str | None
    venue_type: str
    authors: list[dict]
    status: str
    doi: str | None
    url: str | None
    abstract: str | None
    submitted_at: str | None
    accepted_at: str | None
    published_at: str | None
    created_by: str
    created_at: str
    updated_at: str


class VersionCreate(BaseModel):
    notes: str | None = None


class VersionResponse(BaseModel):
    id: str
    publication_id: str
    version: int
    file_path: str | None
    notes: str | None
    created_by: str
    created_at: str


class ReviewCreate(BaseModel):
    reviewer_name: str | None = None
    comments: str | None = None
    decision: str | None = Field(default=None, pattern="^(accept|minor_revision|major_revision|reject)$")
    round: int = 1


class ReviewUpdate(BaseModel):
    reviewer_name: str | None = None
    comments: str | None = None
    decision: str | None = Field(default=None, pattern="^(accept|minor_revision|major_revision|reject)$")


class ReviewResponse(BaseModel):
    id: str
    publication_id: str
    reviewer_name: str | None
    comments: str | None
    decision: str | None
    round: int
    created_at: str


# ── AI Drafting ────────────────────────────────────────────────────────────────


class DraftSectionRequest(BaseModel):
    section: str = Field(pattern="^(abstract|introduction|methods|results|discussion|conclusion)$")
    style: str = Field(default="standard", pattern="^(standard|concise|detailed|lay)$")


class ReviseRequest(BaseModel):
    text: str | None = None
    instructions: str = Field(min_length=1, max_length=2048)


class ReviewResponseRequest(BaseModel):
    reviewer_comments: str = Field(min_length=1, max_length=32768)


class HypothesisRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=1024)
    context: str | None = Field(default=None, max_length=4096)


class ResearchIdeationRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=1024)
    focus_area: str | None = Field(default=None, max_length=1024)
    count: int = Field(default=5, ge=1, le=20)


class MethodologyValidationRequest(BaseModel):
    proposed_methods: str = Field(min_length=1, max_length=16384)


class CitationVerificationRequest(BaseModel):
    citations: str = Field(min_length=1, max_length=32768)


class BibliographyImportRequest(BaseModel):
    text: str = Field(min_length=1, max_length=65536)
    project_id: str | None = None


class LiteratureReviewRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=1024)
    focus_area: str | None = Field(default=None, max_length=1024)
    depth: str = Field(default="comprehensive", pattern="^(quick|comprehensive|exhaustive)$")


class ReviewAssignmentRequest(BaseModel):
    reviewer_id: str
    round: int = 1


class ComputeResourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    backend_type: str = Field(pattern="^(local|ssh|slurm)$")
    config: dict = {}


class GrantWriterRequest(BaseModel):
    grant_type: str = Field(default="general", pattern="^(tubitak_1001|tubitak_1003|tubitak_3501|tubitak_other|tuseb|nih_r01|nsf|erc|wellcome|general)$")


class ComputeRunRequest(BaseModel):
    resource_id: str
    project_id: str
    experiment_id: str | None = None
    command: str = Field(min_length=1, max_length=4096)
    work_dir: str | None = None
    env: dict[str, str] | None = None


# ── Templates ──────────────────────────────────────────────────────────────────


class TemplatePhase(BaseModel):
    name: str
    color: str
    position: int


class TemplateExperimentType(BaseModel):
    name: str
    description: str


class TemplateTask(BaseModel):
    title: str
    description: str
    phase: str
    priority: str


class TemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    domain: str
    icon: str
    phases: list[TemplatePhase]
    experiment_types: list[TemplateExperimentType]
    tasks: list[TemplateTask]


class ProjectFromTemplateRequest(BaseModel):
    template_id: str
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    lab_id: str | None = None


# ── Errors ────────────────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    detail: str
    status: int
    type: str = "about:blank"


# ── Assists ───────────────────────────────────────────────────────────────────


class AssistCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=4096)
    agent_type: AgentType = "writing"
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
    agent_type: str = "writing"
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
