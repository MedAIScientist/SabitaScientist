"""Pydantic request/response models for the PM API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..models import EXPERIMENT_ASSET_ROLES, EXPERIMENT_ASSET_TYPES, EXPERIMENT_STATUSES

AgentType = Literal["research", "code", "data_analysis", "writing"]

# Derived from the single vocabularies in models.py so the API, the CRUD
# validator and the DB CHECK constraint cannot drift apart again.
EXPERIMENT_STATUS_PATTERN = "^(" + "|".join(EXPERIMENT_STATUSES) + ")$"
EXPERIMENT_ASSET_TYPE_PATTERN = "^(" + "|".join(EXPERIMENT_ASSET_TYPES) + ")$"
EXPERIMENT_ASSET_ROLE_PATTERN = "^(" + "|".join(EXPERIMENT_ASSET_ROLES) + ")$"

# ── Auth ──────────────────────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user_id: str
    username: str
    is_admin: bool
    role: str = "student"


# ── Users ─────────────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6)
    email: str | None = None
    role: str = "student"
    is_admin: bool = False


class UserUpdate(BaseModel):
    username: str | None = None
    email: str | None = None
    is_admin: bool | None = None
    role: str | None = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str | None
    is_admin: bool
    created_at: str
    role: str = "student"


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


def _fold_critical(priority: str | None) -> str | None:
    """Task priority has three levels; the legacy "critical" level maps to "high"."""
    return "high" if priority == "critical" else priority


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    description: str | None = None
    assignee_id: str | None = None
    # Three levels (high/medium/low). "critical" is accepted from older clients and folded into "high".
    priority: str = Field(default="medium", pattern="^(critical|high|medium|low)$")
    deadline: str | None = None  # ISO date YYYY-MM-DD
    session_id: str | None = None

    @field_validator("priority")
    @classmethod
    def fold_priority(cls, v: str | None) -> str | None:
        return _fold_critical(v)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    assignee_id: str | None = None
    status: str | None = Field(default=None, pattern="^(todo|in_progress|done)$")
    priority: str | None = Field(default=None, pattern="^(critical|high|medium|low)$")
    deadline: str | None = None
    session_id: str | None = None

    @field_validator("priority")
    @classmethod
    def fold_priority(cls, v: str | None) -> str | None:
        return _fold_critical(v)


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
    linked_experiment_count: int = 0


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
    status: str = Field(default="planned", pattern=EXPERIMENT_STATUS_PATTERN)
    tags: list[str] = []
    deadline: str | None = None
    # Settable at creation so an experiment can start inside a project phase
    # instead of being created unassigned and then moved.
    phase_id: str | None = None


class ExperimentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    hypothesis: str | None = None
    protocol: str | None = None
    status: str | None = Field(default=None, pattern=EXPERIMENT_STATUS_PATTERN)
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
    linked_task_count: int = 0
    # How many data/imaging assets this experiment is traced to, for list badges.
    linked_asset_count: int = 0


class ExperimentAssetCreate(BaseModel):
    asset_type: str = Field(pattern=EXPERIMENT_ASSET_TYPE_PATTERN)
    asset_id: str = Field(min_length=1, max_length=64)
    role: str = Field(default="input", pattern=EXPERIMENT_ASSET_ROLE_PATTERN)
    note: str | None = Field(default=None, max_length=500)


class ExperimentAssetResponse(BaseModel):
    experiment_id: str
    asset_type: str
    asset_id: str
    role: str
    note: str | None
    linked_at: str
    linked_by: str
    # Resolved for display so the UI does not have to know each asset's table.
    label: str | None = None
    detail: str | None = None


class ProjectAssetLink(BaseModel):
    """One experiment's claim on one asset — the reverse of a lineage list."""

    experiment_id: str
    experiment_name: str
    asset_type: str
    asset_id: str
    role: str


class ExperimentEntryCreate(BaseModel):
    type: str = Field(pattern="^(note|result)$")
    title: str = Field(min_length=1, max_length=200)
    body: str = ""


class ExperimentEntryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None


class ExperimentMetricCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    value: float
    unit: str | None = Field(default=None, max_length=40)
    split: str | None = Field(default=None, max_length=120)
    n: int | None = Field(default=None, ge=0)
    stderr: float | None = Field(default=None, ge=0)


class ExperimentMetricResponse(BaseModel):
    id: str
    experiment_id: str
    name: str
    value: float
    unit: str | None
    split: str | None
    n: int | None
    stderr: float | None
    source_attachment_id: str | None
    recorded_by: str | None
    created_at: str
    source: str | None = None


class MetricsCsvRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000_000)
    save: bool = False


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
    metrics_parsed: int = 0
    id: str
    entry_id: str
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by: str | None
    created_at: str
    classification: str = "unclassified"
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
    # Empty for a caller who is neither a member of this lab nor a platform admin
    # — a roster is who works where, not public information. Always a list, never
    # null: the live UI calls .find()/.length/.map() on it unguarded.
    members: list[LabMemberResponse] = []
    # Always the true size, so a client can show how big a lab is without being
    # told who is in it.
    member_count: int = 0
    # Whether this caller may use the lab's management controls — the same test
    # require_lab_role("pi", "admin") applies, so the UI can hide buttons that
    # would only come back 403.
    can_manage: bool = False


class AddLabMemberRequest(BaseModel):
    user_id: str
    role: str = Field(pattern="^(pi|postdoc|phd|ms|visitor)$")


class UpdateLabMemberRoleRequest(BaseModel):
    role: str = Field(pattern="^(pi|postdoc|phd|ms|visitor)$")


# ── Publications ────────────────────────────────────────────────────────────────


class PublicationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    project_id: str | None = None
    venue: str | None = None
    venue_type: str = Field(
        default="journal", pattern="^(journal|conference|preprint|other)$"
    )
    authors: list[dict] = []
    abstract: str | None = None
    doi: str | None = None
    url: str | None = None
    reporting_guideline: str | None = None
    data_availability: str | None = None
    code_availability: str | None = None
    conflict_of_interest: str | None = None
    funding_statement: str | None = None


class PublicationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    venue: str | None = None
    venue_type: str | None = Field(
        default=None, pattern="^(journal|conference|preprint|other)$"
    )
    authors: list[dict] | None = None
    abstract: str | None = None
    doi: str | None = None
    url: str | None = None
    status: str | None = Field(
        default=None,
        pattern="^(draft|submitted|reviewing|accepted|published|rejected)$",
    )
    reporting_guideline: str | None = None
    data_availability: str | None = None
    code_availability: str | None = None
    conflict_of_interest: str | None = None
    funding_statement: str | None = None


class PublicationResponse(BaseModel):
    id: str
    project_id: str | None
    project_name: str | None = None
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
    reporting_guideline: str | None
    data_availability: str | None
    code_availability: str | None
    conflict_of_interest: str | None
    funding_statement: str | None
    created_by: str
    created_at: str
    updated_at: str
    linked_experiments: list[dict] = []


class PublicationLinkExperimentRequest(BaseModel):
    experiment_id: str
    section: str | None = None


class VersionCreate(BaseModel):
    notes: str | None = None
    content: str | None = None
    section: str | None = None


class VersionResponse(BaseModel):
    id: str
    publication_id: str
    version: int
    file_path: str | None
    notes: str | None
    created_by: str
    created_at: str
    section: str | None = None
    generated_by: str | None = None
    model: str | None = None
    prompt_hash: str | None = None
    verification: dict | None = None
    content_length: int = 0
    # Populated only by the single-version endpoint; listing many full drafts
    # would make the versions payload unbounded.
    content: str | None = None


class AIDisclosureResponse(BaseModel):
    publication_id: str
    statement: str
    ai_version_count: int
    human_version_count: int
    models_used: list[str]
    sections: list[str]


class ReviewCreate(BaseModel):
    reviewer_name: str | None = None
    comments: str | None = None
    decision: str | None = Field(
        default=None, pattern="^(accept|minor_revision|major_revision|reject)$"
    )
    round: int = 1


class ReviewUpdate(BaseModel):
    reviewer_name: str | None = None
    comments: str | None = None
    decision: str | None = Field(
        default=None, pattern="^(accept|minor_revision|major_revision|reject)$"
    )


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
    section: str = Field(
        pattern="^(abstract|introduction|methods|results|discussion|conclusion)$"
    )
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
    depth: str = Field(
        default="comprehensive", pattern="^(quick|comprehensive|exhaustive)$"
    )


class ReviewAssignmentRequest(BaseModel):
    reviewer_id: str
    round: int = 1


class ComputeResourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    backend_type: str = Field(pattern="^(local|ssh|slurm)$")
    config: dict = {}


class GrantWriterRequest(BaseModel):
    grant_type: str = Field(
        default="general",
        pattern="^(tubitak_1001|tubitak_1003|tubitak_3501|tubitak_other|tuseb|nih_r01|nsf|erc|wellcome|general)$",
    )


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


# ── Grants ────────────────────────────────────────────────────────────────────

# Mirrors the grants.status CHECK constraint in db.py. The two drifted apart once
# already, which made 'under_review' and 'active' unusable through the API even
# though the UI offered them.
GRANT_STATUS_PATTERN = "^(draft|submitted|under_review|awarded|rejected|active|closed)$"


class GrantCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    funder: str = Field(min_length=1, max_length=256)
    lab_id: str | None = None
    project_id: str | None = None
    amount_requested: float | None = None
    amount_awarded: float | None = None
    currency: str = "TRY"
    status: str = Field(default="draft", pattern=GRANT_STATUS_PATTERN)
    submitted_at: str | None = None
    awarded_at: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    pi_id: str | None = None


class GrantUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    funder: str | None = Field(default=None, min_length=1, max_length=256)
    amount_requested: float | None = None
    amount_awarded: float | None = None
    currency: str | None = None
    status: str | None = Field(default=None, pattern=GRANT_STATUS_PATTERN)
    submitted_at: str | None = None
    awarded_at: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    pi_id: str | None = None
    lab_id: str | None = None
    project_id: str | None = None


class GrantResponse(BaseModel):
    id: str
    title: str
    funder: str
    amount_requested: float | None
    amount_awarded: float | None
    currency: str
    status: str
    submitted_at: str | None
    awarded_at: str | None
    start_date: str | None
    end_date: str | None
    description: str | None
    pi_id: str | None
    pi_username: str | None = None
    project_id: str | None
    lab_id: str | None
    created_by: str
    created_at: str
    updated_at: str
    # Whether this caller may change the grant — the UI hides edit affordances
    # instead of offering buttons that answer 403.
    can_manage: bool = False


# ── Grant plan: budget, milestones, team ──────────────────────────────────────


class GrantBudgetItemCreate(BaseModel):
    category: str = Field(
        default="other",
        pattern="^(personnel|equipment|consumables|travel|services|other)$",
    )
    description: str | None = None
    planned_amount: float = Field(default=0.0, ge=0)
    spent_amount: float = Field(default=0.0, ge=0)
    position: int = 0


class GrantBudgetItemUpdate(BaseModel):
    category: str | None = Field(
        default=None,
        pattern="^(personnel|equipment|consumables|travel|services|other)$",
    )
    description: str | None = None
    planned_amount: float | None = Field(default=None, ge=0)
    spent_amount: float | None = Field(default=None, ge=0)
    position: int | None = None


class GrantBudgetItemResponse(BaseModel):
    id: str
    grant_id: str
    category: str
    description: str | None
    planned_amount: float
    spent_amount: float
    position: int
    created_at: str
    updated_at: str


class GrantMilestoneCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    kind: str = Field(default="milestone", pattern="^(milestone|report|deliverable)$")
    due_date: str | None = None
    owner_id: str | None = None
    notes: str | None = None
    position: int = 0


class GrantMilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    kind: str | None = Field(default=None, pattern="^(milestone|report|deliverable)$")
    due_date: str | None = None
    # Toggling completion is the common edit, so it gets a boolean rather than
    # making every client build and clear an ISO timestamp.
    completed: bool | None = None
    completed_at: str | None = None
    owner_id: str | None = None
    notes: str | None = None
    position: int | None = None


class GrantMilestoneResponse(BaseModel):
    id: str
    grant_id: str
    title: str
    kind: str
    due_date: str | None
    completed_at: str | None
    owner_id: str | None
    notes: str | None
    position: int
    created_at: str
    updated_at: str


class GrantMemberCreate(BaseModel):
    user_id: str = Field(min_length=1)
    role: str = Field(
        default="researcher",
        pattern="^(pi|co_pi|researcher|assistant|advisor)$",
    )
    share_percent: float | None = Field(default=None, ge=0, le=100)


class GrantMemberUpdate(BaseModel):
    role: str | None = Field(
        default=None, pattern="^(pi|co_pi|researcher|assistant|advisor)$"
    )
    share_percent: float | None = Field(default=None, ge=0, le=100)


class GrantMemberResponse(BaseModel):
    id: str
    grant_id: str
    user_id: str
    username: str | None
    role: str
    share_percent: float | None
    added_at: str


class GrantCurrencyTotal(BaseModel):
    currency: str
    requested: float
    awarded: float
    count: int


class GrantStatsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    totals_by_currency: list[GrantCurrencyTotal]
    decided: int
    won: int
    success_rate: float | None
    ending_soon: int
    overdue_milestones: int
    open_reports: int
    budget_planned: float
    budget_spent: float


# ── Conferences ───────────────────────────────────────────────────────────────


class ConferenceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    venue: str | None = None
    location: str | None = None
    deadline: str | None = None
    submission_date: str | None = None
    decision_date: str | None = None
    status: str = Field(
        default="draft", pattern="^(draft|submitted|accepted|rejected|presented)$"
    )
    presentation_type: str = Field(
        default="poster", pattern="^(poster|oral|spotlight|workshop|keynote)$"
    )
    travel_funding: float | None = None
    travel_notes: str | None = None
    url: str | None = None
    notes: str | None = None
    project_id: str | None = None
    publication_id: str | None = None


class ConferenceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    venue: str | None = None
    location: str | None = None
    deadline: str | None = None
    submission_date: str | None = None
    decision_date: str | None = None
    status: str | None = Field(
        default=None, pattern="^(draft|submitted|accepted|rejected|presented)$"
    )
    presentation_type: str | None = Field(
        default=None, pattern="^(poster|oral|spotlight|workshop|keynote)$"
    )
    travel_funding: float | None = None
    travel_notes: str | None = None
    url: str | None = None
    notes: str | None = None
    project_id: str | None = None
    publication_id: str | None = None


class ConferenceResponse(BaseModel):
    id: str
    name: str
    venue: str | None
    location: str | None
    deadline: str | None
    submission_date: str | None
    decision_date: str | None
    status: str
    presentation_type: str
    travel_funding: float | None
    travel_notes: str | None
    url: str | None
    notes: str | None
    project_id: str | None
    publication_id: str | None
    created_by: str
    created_at: str
    updated_at: str


# ── IRB Approvals ─────────────────────────────────────────────────────────────


class IRBCreate(BaseModel):
    project_id: str
    institution: str = Field(min_length=1, max_length=256)
    protocol_number: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=512)
    # Born draft or submitted ONLY: an IRB can never be created already decided —
    # 'approved' is an admin transition that records who approved (see routes/irb.py).
    status: str = Field(default="draft", pattern="^(draft|submitted)$")
    approval_date: str | None = None
    expiry_date: str | None = None
    renewal_date: str | None = None
    documents: list[str] = []
    notes: str | None = None


class IRBUpdate(BaseModel):
    status: str | None = Field(
        default=None,
        pattern="^(draft|submitted|approved|rejected|expired|closed)$",
    )
    approval_date: str | None = None
    expiry_date: str | None = None
    renewal_date: str | None = None
    documents: list[str] | None = None
    notes: str | None = None
    institution: str | None = None
    protocol_number: str | None = None


class IRBResponse(BaseModel):
    id: str
    project_id: str
    institution: str
    protocol_number: str
    title: str
    status: str
    approval_date: str | None
    expiry_date: str | None
    renewal_date: str | None
    documents: list[str]
    notes: str | None
    created_by: str
    created_at: str
    updated_at: str
    approved_by: str | None = None
    approved_at: str | None = None


# ── Imaging datasets ──────────────────────────────────────────────────────────


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    purpose: str = Field(min_length=1, max_length=2048)
    lab_id: str
    modality: str | None = Field(default=None, max_length=16)
    accession_list: list[str] = []
    estimated_bytes: int | None = Field(default=None, ge=0)
    irb_ids: list[str] = []
    # The project this data is requested for (optional; tracked through to delivery).
    project_id: str | None = None
    # Whether Curator derives viewing PNGs during delivery. A pure-ML cohort sets false and
    # never pays the render storage; annotation needs true (CVAT cannot read DICOM).
    renders: bool = True


class DatasetTransition(BaseModel):
    status: str | None = Field(
        default=None, pattern="^(delivering|sealed|expired|revoked)$"
    )
    retention_until: str | None = None
    content_root_sha256: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")


class DatasetGrantCreate(BaseModel):
    project_id: str
    expires_at: str | None = None
    # Annotation staging (increment 4): stage this dataset as CVAT tasks in the target
    # project's provisioned CVAT project. task_size chunks images per task (0/None = one task
    # per accession+study). This is the HUMAN request; the platform only executes mechanics.
    annotate: bool = False
    task_size: int | None = Field(default=None, ge=1, le=500)


class DatasetGrantResponse(BaseModel):
    id: str
    dataset_id: str
    project_id: str
    granted_by: str
    admin_approved_by: str | None
    admin_approved_at: str | None
    granted_at: str
    expires_at: str | None
    revoked_at: str | None
    revoked_by: str | None
    active: bool
    cvat_project_id: int | None = None
    task_size: int | None = None


class DatasetResponse(BaseModel):
    id: str
    name: str
    purpose: str
    lab_id: str
    requested_by: str
    modality: str | None
    accession_list: list[str]
    estimated_bytes: int | None
    status: str
    pi_approved_by: str | None
    pi_approved_at: str | None
    admin_approved_by: str | None
    admin_approved_at: str | None
    retention_until: str | None
    bucket: str | None
    renders: bool = True
    sealed_at: str | None
    content_root_sha256: str | None
    generation: int
    created_at: str
    updated_at: str
    irb_ids: list[str] = []
    grants: list[DatasetGrantResponse] = []
    project_id: str | None = None


# ── Wiki Pages ────────────────────────────────────────────────────────────────


class WikiPageCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    content: str = ""
    tags: list[str] = []


class WikiPageUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    content: str | None = None
    tags: list[str] | None = None


class WikiPageResponse(BaseModel):
    id: str
    lab_id: str
    title: str
    slug: str
    content: str
    tags: list[str]
    created_by: str
    created_at: str
    updated_at: str


# ── Search ────────────────────────────────────────────────────────────────────


class SearchResultItem(BaseModel):
    id: str
    type: str
    title: str | None = None
    name: str | None = None
    description: str | None = None
    project_id: str | None = None
    venue: str | None = None


class SearchResults(BaseModel):
    projects: list[SearchResultItem] = []
    tasks: list[SearchResultItem] = []
    experiments: list[SearchResultItem] = []
    publications: list[SearchResultItem] = []


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


# ── De-identification Pipelines ──────────────────────────────────────────────


class PipelineCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    pipeline_type: str = Field(pattern=r"^(dicom|ehr|text|image|generic)$")
    config_json: str = "{}"


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config_json: str | None = None


class PipelineResponse(BaseModel):
    id: str
    project_id: str
    name: str
    description: str | None
    pipeline_type: str
    config_json: str
    created_by: str
    created_at: str
    updated_at: str


class PipelineRunCreate(BaseModel):
    pipeline_id: str
    irb_id: str | None = None
    input_location: str = Field(min_length=1)
    output_location: str = Field(min_length=1)


class PipelineRunUpdate(BaseModel):
    status: str | None = Field(
        default=None, pattern=r"^(pending|running|completed|failed|verified)$"
    )
    output_location: str | None = None
    input_size_bytes: int | None = None
    output_size_bytes: int | None = None
    records_processed: int | None = None
    phi_fields_removed: str | None = None
    verification_status: str | None = Field(
        default=None, pattern=r"^(pending|passed|failed)$"
    )
    verification_notes: str | None = None
    error: str | None = None


class PipelineRunResponse(BaseModel):
    id: str
    pipeline_id: str
    project_id: str
    input_location: str
    output_location: str
    status: str
    irb_id: str | None
    input_size_bytes: int | None
    output_size_bytes: int | None
    records_processed: int | None
    phi_fields_removed: str
    verification_status: str | None
    verification_notes: str | None
    error: str | None
    started_at: str | None
    completed_at: str | None
    created_by: str
    created_at: str


# ── Sandboxes ────────────────────────────────────────────────────────────────


class SandboxCreate(BaseModel):
    name: str = Field(min_length=1)
    irb_id: str | None = None
    spec_json: str = "{}"
    network_rules_json: str = "[]"
    storage_quota_bytes: int | None = None
    expires_at: str | None = None


class SandboxUpdate(BaseModel):
    status: str | None = Field(
        default=None,
        pattern=r"^(provisioning|active|expiring|expired|terminated)$",
    )
    access_url: str | None = None
    spec_json: str | None = None
    expires_at: str | None = None


class SandboxResponse(BaseModel):
    id: str
    project_id: str
    name: str
    status: str
    spec_json: str
    network_rules_json: str
    irb_id: str | None
    storage_quota_bytes: int | None
    access_url: str | None
    provisioned_at: str | None
    expires_at: str | None
    terminated_at: str | None
    created_by: str
    created_at: str
    updated_at: str


# ── Export Requests ──────────────────────────────────────────────────────────


class ExportRequestCreate(BaseModel):
    file_name: str = Field(min_length=1)
    file_type: str = Field(
        pattern=r"^(model_weights|aggregate_figure|coefficient_table|annotation_stats|documentation|other)$"
    )
    file_size_bytes: int | None = None
    description: str | None = None
    justification: str | None = None


class ExportRequestReview(BaseModel):
    status: str = Field(pattern=r"^(approved|rejected)$")
    reviewer_notes: str | None = None


class ExportRequestResponse(BaseModel):
    id: str
    project_id: str
    sandbox_id: str | None
    requested_by: str
    reviewed_by: str | None
    status: str
    file_name: str
    file_type: str
    file_size_bytes: int | None
    description: str | None
    justification: str | None
    reviewer_notes: str | None
    reviewed_at: str | None
    created_at: str


# ── Attachment Classification ────────────────────────────────────────────────


class AttachmentClassifyRequest(BaseModel):
    classification: str = Field(
        pattern=r"^(unclassified|raw_phi|de_identified|aggregate|model_weights|public)$"
    )


# ── Companion applications ────────────────────────────────────────────────────


class IntegrationStatus(BaseModel):
    key: str
    name: str
    path: str
    kind: str
    description: str
    up: bool
    http_status: int | None
    latency_ms: int


# ── Academic supervision ─────────────────────────────────────────────────────


class SupervisorAssignRequest(BaseModel):
    student_id: str
    professor_id: str
    active_from: str | None = None


class SupervisorAssignmentResponse(BaseModel):
    id: str
    student_id: str
    professor_id: str
    # Names, because professors may not list users and the pages showed raw ids.
    student_name: str | None = None
    professor_name: str | None = None
    lab_id: str | None = None
    lab_name: str | None = None
    active_from: str
    active_until: str | None
    created_at: str


class MeetingSettingRequest(BaseModel):
    weekday: int = Field(ge=0, le=6)
    time_local: str | None = None
    timezone: str | None = None
    effective_from: str | None = None


class MeetingSettingResponse(BaseModel):
    id: str
    professor_id: str
    weekday: int
    time_local: str | None
    timezone: str | None
    effective_from: str
    created_at: str


class ReportSummaryRequest(BaseModel):
    accomplished: str | None = None
    next_focus: str | None = None
    support_requested: str | None = None


class ReportItemRequest(BaseModel):
    item_id: str | None = None
    item_title: str = Field(min_length=1, max_length=256)
    task_id: str | None = None
    publication_id: str | None = None
    experiment_id: str | None = None
    item_kind: str | None = None
    progress_pct: int = Field(default=0, ge=0, le=100)
    status: str | None = None
    blocker: str | None = None
    needs_help: bool = False
    what_changed: str | None = None
    next_step: str | None = None
    risk_level: str = "low"
    next_deadline: str | None = None
    sort_order: int = 0


class ReportItemResponse(BaseModel):
    id: str
    report_id: str
    task_id: str | None
    publication_id: str | None
    experiment_id: str | None
    item_title: str
    item_kind: str | None
    progress_pct: int
    status: str | None
    blocker: str | None
    needs_help: bool
    what_changed: str | None
    next_step: str | None
    risk_level: str
    next_deadline: str | None
    sort_order: int


class WeeklyReportResponse(BaseModel):
    id: str
    student_id: str
    # The supervisor needs a name, and professors may not read the full user list.
    student_name: str | None = None
    week_start: str
    status: str
    review_status: str
    risk_level: str
    risk_override: str | None
    accomplished: str | None
    next_focus: str | None
    support_requested: str | None
    submitted_at: str | None
    reviewed_at: str | None
    reviewed_by: str | None
    feedback: str | None
    created_at: str
    updated_at: str
    items: list[ReportItemResponse] = []


class FollowupItem(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    due_date: str | None = None  # YYYY-MM-DD


class ReviewRequest(BaseModel):
    review_status: str = "reviewed"
    feedback: str | None = None
    risk_override: str | None = None
    # Requests that carry forward into the student's next weekly updates until closed.
    followups: list[FollowupItem] = []


class AttendanceRequest(BaseModel):
    status: str = "not_set"
    joined_mode: str | None = None
    note: str | None = None


class AttendanceResponse(BaseModel):
    id: str
    professor_id: str
    student_id: str
    week_start: str
    status: str
    joined_mode: str | None
    note: str | None
    recorded_at: str


class ExtensionRequest(BaseModel):
    new_deadline: str
    reason: str | None = None


class ExtensionResponse(BaseModel):
    id: str
    student_id: str
    professor_id: str
    week_start: str
    new_deadline: str
    reason: str | None
    created_at: str
    report_id: str | None


class JourneyRequest(BaseModel):
    level: str = "MSc"
    status: str = "planned"
    programme: str | None = None
    university: str | None = None
    department: str | None = None
    start_year: int | None = None
    start_date: str | None = None
    expected_end: str | None = None
    thesis_title: str | None = None


class JourneyResponse(BaseModel):
    id: str
    student_id: str
    level: str
    status: str
    programme: str | None
    university: str | None
    department: str | None
    start_year: int | None
    start_date: str | None
    expected_end: str | None
    thesis_title: str | None
    created_at: str
    updated_at: str


class RequirementRequest(BaseModel):
    level: str = "BSc"
    title: str = Field(min_length=1, max_length=128)
    req_type: str = "research_item"
    description: str | None = None
    research_item_type: str | None = None
    min_stage: str | None = None
    target_value: float = 1
    unit: str | None = None
    required: bool = True
    student_id: str | None = None  # None = all my students at this level


class RequirementResponse(BaseModel):
    id: str
    level: str
    title: str
    description: str | None
    req_type: str
    research_item_type: str | None
    min_stage: str | None
    target_value: float
    unit: str | None
    required: bool
    active: bool
    created_at: str
    professor_id: str | None = None
    student_id: str | None = None
    student_name: str | None = None


# ── AI usage accounting ──────────────────────────────────────────────────────


class AiUsageTokens(BaseModel):
    """Token totals. ``provider_reported`` and ``estimated`` never get summed."""

    provider_reported: int
    estimated: int
    prompt: int
    completion: int


class AiUsageBreakdown(BaseModel):
    label: str
    calls: int
    provider_tokens: int
    estimated_tokens: int


class AiUsageSummary(BaseModel):
    window_days: int | None
    calls: int
    tokens: AiUsageTokens
    avg_duration_ms: int | None
    by_task: list[AiUsageBreakdown]
    by_model: list[AiUsageBreakdown]


class AiUsageRecord(BaseModel):
    id: str
    task: str
    source: str
    token_source: str
    model: str | None
    user_id: str | None
    project_id: str | None
    publication_id: str | None
    run_id: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    duration_ms: int | None
    created_at: str


class AiUsageRecords(BaseModel):
    records: list[AiUsageRecord]


class AiJobResponse(BaseModel):
    id: str
    kind: str
    title: str
    project_id: str | None = None
    publication_id: str | None = None
    status: Literal["running", "done", "failed"]
    result_path: str | None = None
    error: str | None = None
    created_at: str
    finished_at: str | None = None


class WeeklyTaskResponse(BaseModel):
    """An assigned project task as it appears in a week's update."""

    id: str
    title: str
    status: str
    priority: str
    deadline: str | None
    project_id: str
    project_name: str
    # Present once the task has been mirrored into that week's report.
    item_id: str | None = None
    item_status: str | None = None
    item_progress_pct: int | None = None
    item_needs_help: bool | None = None
    report_id: str | None = None
    report_status: str | None = None


class WeeklyTasksResponse(BaseModel):
    week_start: str
    report_id: str | None
    report_status: str | None
    tasks: list[WeeklyTaskResponse]


class WeeklyTaskUpdateRequest(BaseModel):
    """Update a task and its weekly item in one action.

    ``status`` moves the task — the same vocabulary the board uses. The remaining
    fields are narrative and belong to the student's report, so they are written to
    the item only.
    """

    status: str | None = Field(default=None, pattern="^(todo|in_progress|done)$")
    needs_help: bool | None = None
    what_changed: str | None = None
    next_step: str | None = None
    blocker: str | None = None


class WeeklyTaskUpdateResponse(BaseModel):
    task: WeeklyTaskResponse
    # True when the week's report was already submitted, so only the task moved and
    # the record of that week was deliberately left untouched.
    report_locked: bool
