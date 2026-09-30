"""Dataclasses representing PM domain entities."""

from __future__ import annotations

from dataclasses import dataclass

# Single source of truth for the experiment lifecycle. The CRUD validator and the
# Pydantic patterns derive from this list, and a test asserts db.py's CHECK
# constraint matches it — the three previously disagreed about 'abandoned', which
# the UI offered and the API rejected.
EXPERIMENT_STATUSES: tuple[str, ...] = ("planned", "running", "completed", "abandoned")


@dataclass
class User:
    id: str
    username: str
    password_hash: str
    is_admin: bool
    created_at: str
    email: str | None = None
    role: str = "student"  # 'admin' | 'professor' | 'student'


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
    agent_type: str  # 'research' | 'code' | 'data_analysis' | 'writing'
    prompt: str
    status: str  # 'pending' | 'running' | 'done' | 'failed' | 'cancelled'
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
    status: str  # one of EXPERIMENT_STATUSES
    tags: list[str]
    created_by: str
    created_at: str
    updated_at: str
    hypothesis: str | None = None
    protocol: str | None = None
    deadline: str | None = None
    phase_id: str | None = None


# Asset kinds an experiment can be traced to. Kept as a tuple for the same reason
# as EXPERIMENT_STATUSES: the DB CHECK, the validator and the schema share it.
EXPERIMENT_ASSET_TYPES: tuple[str, ...] = (
    "dataset",
    "pipeline_run",
    "cvat_project",
    "webknossos_dataset",
    "sandbox",
)

# What the asset is to the experiment: the cohort going in, the processing step,
# the artefact coming out, or supporting material.
EXPERIMENT_ASSET_ROLES: tuple[str, ...] = ("input", "processing", "output", "reference")


@dataclass
class ExperimentAsset:
    experiment_id: str
    asset_type: str
    asset_id: str
    role: str
    linked_at: str
    linked_by: str
    note: str | None = None
    # Resolved for display; None when the asset row is gone (see the cleanup in
    # the delete routes, which normally prevents that).
    label: str | None = None
    detail: str | None = None


@dataclass
class ExperimentEntry:
    id: str
    experiment_id: str
    type: str  # 'note' | 'result'
    title: str
    body: str
    created_at: str
    updated_at: str
    author_id: str | None = None


@dataclass
class ExperimentMetric:
    """A recorded numeric result. The only source of numbers for drafting."""

    id: str
    experiment_id: str
    name: str
    value: float
    created_at: str
    unit: str | None = None
    split: str | None = None
    n: int | None = None
    stderr: float | None = None
    source_attachment_id: str | None = None
    recorded_by: str | None = None


@dataclass
class ExperimentAssist:
    id: str
    experiment_id: str
    project_id: str
    prompt: str
    context_json: str
    status: str  # 'pending'|'running'|'done'|'failed'|'cancelled'
    created_by: str
    created_at: str
    output: str | None = None
    error: str | None = None
    agent_type: str = "writing"  # 'research'|'code'|'data_analysis'|'writing'
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
    classification: str = "unclassified"


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
    status: str  # draft|submitted|reviewing|accepted|published|rejected
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
    # Submission compliance statements — see the readiness gate in the paper workspace.
    reporting_guideline: str | None = None
    data_availability: str | None = None
    code_availability: str | None = None
    conflict_of_interest: str | None = None
    funding_statement: str | None = None


@dataclass
class PublicationVersion:
    id: str
    publication_id: str
    version: int
    notes: str | None
    created_by: str
    created_at: str
    file_path: str | None = None
    content: str | None = None
    section: str | None = None
    generated_by: str | None = None  # 'ai-agent' | 'ai-direct' | 'human'
    model: str | None = None  # None when the producing model is unknown
    prompt_hash: str | None = None


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
class Grant:
    id: str
    title: str
    funder: str
    status: str
    created_by: str
    created_at: str
    updated_at: str
    lab_id: str | None = None
    project_id: str | None = None
    amount_requested: float | None = None
    amount_awarded: float | None = None
    currency: str = "TRY"
    submitted_at: str | None = None
    awarded_at: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    pi_id: str | None = None
    # Joined for display — the id alone is unreadable in a UI.
    pi_username: str | None = None


@dataclass
class GrantBudgetItem:
    id: str
    grant_id: str
    category: str
    planned_amount: float
    spent_amount: float
    created_at: str
    updated_at: str
    description: str | None = None
    position: int = 0


@dataclass
class GrantMilestone:
    id: str
    grant_id: str
    title: str
    kind: str
    created_at: str
    updated_at: str
    due_date: str | None = None
    completed_at: str | None = None
    owner_id: str | None = None
    notes: str | None = None
    position: int = 0


@dataclass
class GrantMember:
    id: str
    grant_id: str
    user_id: str
    role: str
    added_at: str
    share_percent: float | None = None
    username: str | None = None


@dataclass
class Conference:
    id: str
    name: str
    status: str
    presentation_type: str
    created_by: str
    created_at: str
    updated_at: str
    project_id: str | None = None
    publication_id: str | None = None
    venue: str | None = None
    location: str | None = None
    deadline: str | None = None
    submission_date: str | None = None
    decision_date: str | None = None
    travel_funding: float | None = None
    travel_notes: str | None = None
    url: str | None = None
    notes: str | None = None


@dataclass
class IRBApproval:
    id: str
    project_id: str
    institution: str
    protocol_number: str
    title: str
    status: str
    created_by: str
    created_at: str
    updated_at: str
    approval_date: str | None = None
    expiry_date: str | None = None
    renewal_date: str | None = None
    documents: list[str] | None = None
    notes: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None


@dataclass
class Dataset:
    """Governance record of one delivered imaging cohort (v2 storage model)."""

    id: str
    name: str
    purpose: str
    lab_id: str
    requested_by: str
    status: str
    generation: int
    created_at: str
    updated_at: str
    modality: str | None = None
    accession_list: list[str] | None = None
    estimated_bytes: int | None = None
    pi_approved_by: str | None = None
    pi_approved_at: str | None = None
    admin_approved_by: str | None = None
    admin_approved_at: str | None = None
    retention_until: str | None = None
    pepper_generation: int = 1
    bucket: str | None = None
    sealed_at: str | None = None
    content_root_sha256: str | None = None
    renders: bool = True


@dataclass
class DatasetGrant:
    """A dataset shared with one project — pending until an admin approves."""

    id: str
    dataset_id: str
    project_id: str
    granted_by: str
    granted_at: str
    admin_approved_by: str | None = None
    admin_approved_at: str | None = None
    expires_at: str | None = None
    revoked_at: str | None = None
    revoked_by: str | None = None
    # Annotation staging intent (increment 4): a HUMAN asked for this dataset to appear as
    # CVAT tasks in this project; the platform converges the mechanics. None = data-only grant.
    cvat_project_id: int | None = None
    task_size: int | None = None


@dataclass
class LabWikiPage:
    id: str
    lab_id: str
    title: str
    slug: str
    content: str
    created_by: str
    created_at: str
    updated_at: str
    tags: list[str] | None = None


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


@dataclass
class DeIDPipeline:
    id: str
    project_id: str
    name: str
    pipeline_type: str  # dicom, ehr, text, image, generic
    config_json: str
    created_by: str
    created_at: str
    updated_at: str
    description: str | None = None


@dataclass
class DeIDPipelineRun:
    id: str
    pipeline_id: str
    project_id: str
    input_location: str
    output_location: str
    status: str  # pending, running, completed, failed, verified
    created_by: str
    created_at: str
    irb_id: str | None = None
    input_size_bytes: int | None = None
    output_size_bytes: int | None = None
    records_processed: int | None = None
    phi_fields_removed: str | None = None  # JSON list
    verification_status: str | None = None  # pending, passed, failed
    verification_notes: str | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


@dataclass
class Sandbox:
    id: str
    project_id: str
    name: str
    status: str  # provisioning, active, expiring, expired, terminated
    spec_json: str
    network_rules_json: str
    created_by: str
    created_at: str
    updated_at: str
    irb_id: str | None = None
    storage_quota_bytes: int | None = None
    access_url: str | None = None
    provisioned_at: str | None = None
    expires_at: str | None = None
    terminated_at: str | None = None


@dataclass
class ExportRequest:
    id: str
    project_id: str
    requested_by: str
    file_name: str
    file_type: str  # model_weights, aggregate_figure, coefficient_table, annotation_stats, documentation, other
    status: str  # pending, approved, rejected
    created_at: str
    sandbox_id: str | None = None
    reviewed_by: str | None = None
    file_size_bytes: int | None = None
    description: str | None = None
    justification: str | None = None
    reviewer_notes: str | None = None
    reviewed_at: str | None = None


@dataclass
class TaskHistoryEntry:
    id: str
    task_id: str
    change_type: str
    created_at: str
    changed_by: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    comment: str | None = None


@dataclass
class CVATProject:
    id: str
    project_id: str
    cvat_id: int
    name: str
    status: str
    created_by: str
    created_at: str
    updated_at: str
    labels_json: str = "[]"
    num_images: int = 0
    num_annotations: int = 0
    export_format: str = "COCO 1.0"
    export_key: str | None = None


@dataclass
class WebKnossosDataset:
    id: str
    project_id: str
    name: str
    directory_name: str
    status: str
    created_by: str
    created_at: str
    updated_at: str
    wk_id: str | None = None
    voxel_count: str | None = None
    segmentation_status: str = "pending"
    num_skeletons: int = 0
    num_volumes: int = 0


# ── Academic supervision ─────────────────────────────────────────────────────


@dataclass
class SupervisorAssignment:
    id: str
    student_id: str
    professor_id: str
    active_from: str
    created_at: str
    active_until: str | None = None


@dataclass
class WeeklyMeetingSetting:
    id: str
    professor_id: str
    weekday: int
    effective_from: str
    created_at: str
    time_local: str | None = None
    timezone: str | None = None


@dataclass
class WeeklyReport:
    id: str
    student_id: str
    week_start: str
    status: str
    review_status: str
    risk_level: str
    created_at: str
    updated_at: str
    risk_override: str | None = None
    accomplished: str | None = None
    next_focus: str | None = None
    support_requested: str | None = None
    submitted_at: str | None = None
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    feedback: str | None = None


@dataclass
class WeeklyReportItem:
    id: str
    report_id: str
    item_title: str
    progress_pct: int
    risk_level: str
    needs_help: bool
    sort_order: int
    task_id: str | None = None
    publication_id: str | None = None
    experiment_id: str | None = None
    item_kind: str | None = None
    status: str | None = None
    blocker: str | None = None
    what_changed: str | None = None
    next_step: str | None = None
    next_deadline: str | None = None


@dataclass
class MeetingAttendance:
    id: str
    professor_id: str
    student_id: str
    week_start: str
    status: str
    recorded_at: str
    joined_mode: str | None = None
    note: str | None = None


@dataclass
class ReportExtension:
    id: str
    student_id: str
    professor_id: str
    week_start: str
    new_deadline: str
    created_at: str
    report_id: str | None = None
    reason: str | None = None


@dataclass
class AcademicJourney:
    id: str
    student_id: str
    level: str
    status: str
    created_at: str
    updated_at: str
    programme: str | None = None
    university: str | None = None
    department: str | None = None
    start_year: int | None = None
    start_date: str | None = None
    expected_end: str | None = None
    thesis_title: str | None = None


@dataclass
class GraduationRequirement:
    id: str
    level: str
    title: str
    req_type: str
    target_value: float
    created_at: str
    description: str | None = None
    research_item_type: str | None = None
    min_stage: str | None = None
    unit: str | None = None
    required: bool = True
    active: bool = True


# Where AI usage is attributed. ``DIRECT`` is pm/_ai.py's in-process call;
# ``AGENT`` is a run dispatched to the agent runner service.
AI_USAGE_SOURCES = ("direct", "agent")
# ``provider`` means the model API reported the counts; ``estimated`` means we
# derived them from character counts. Never blur the two in a report.
AI_USAGE_TOKEN_SOURCES = ("provider", "estimated")


@dataclass
class AiUsage:
    id: str
    task: str
    source: str
    token_source: str
    created_at: str
    user_id: str | None = None
    project_id: str | None = None
    publication_id: str | None = None
    run_id: str | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    prompt_chars: int | None = None
    output_chars: int | None = None
    duration_ms: int | None = None


@dataclass(frozen=True)
class AiJob:
    """A background AI job and where its result landed (``result_path`` is a UI route)."""

    id: str
    kind: str
    title: str
    user_id: str | None
    project_id: str | None
    publication_id: str | None
    status: str
    result_path: str | None
    error: str | None
    created_at: str
    finished_at: str | None
