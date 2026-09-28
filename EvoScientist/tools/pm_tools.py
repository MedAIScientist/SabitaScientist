"""Agent tools for reading and writing PM entities — uses caller's user_id."""

from __future__ import annotations
from contextvars import ContextVar

from langchain_core.tools import tool

from EvoScientist.pm.crud.experiment_entries import create_entry, list_entries
from EvoScientist.pm.crud.experiments import create_experiment, list_experiments
from EvoScientist.pm.crud.projects import (
    create_project,
    get_project,
    list_projects_for_user,
)
from EvoScientist.pm.crud.tasks import create_task, list_tasks
from EvoScientist.pm.db import get_db_path
from EvoScientist.pm.models import Project, Task, Experiment

current_user_id: ContextVar[str] = ContextVar("current_user_id", default="")


def _uid() -> str:
    uid = current_user_id.get()
    if not uid:
        raise RuntimeError("current_user_id not set — tools require an authenticated user")
    return uid


# ── Projects ──────────────────────────────────────────────────────────────


@tool
def pm_create_project(name: str, description: str = "", lab_id: str = "", template_id: str = "") -> str:
    """Create a new research project. Optionally specify a template to pre-populate phases and tasks.

    Available template_id values: ml-research (ML/AI Research), life-science (Life Science), medical (Medical Research).
    Omit template_id for a blank project.
    Only include lab_id if the user explicitly names a lab.

    Args:
        name: Project name (required)
        description: Optional description
        lab_id: Only if user mentions a specific lab
        template_id: One of: ml-research, life-science, medical

    Returns:
        Result message
    """
    if not name or not name.strip():
        return "Error: project name is required."

    pid = lab_id.strip().lower()
    if pid in ("", "none", "null", "default_lab", "default"):
        pid = None
    if pid:
        from EvoScientist.pm.crud.labs import get_lab
        if get_lab(get_db_path(), pid) is None:
            pid = None

    tid = template_id.strip().lower() if template_id else ""
    known = {"ml-research", "life-science", "medical"}
    if tid not in known:
        # Auto-detect template from project name
        nl = name.lower()
        if any(w in nl for w in ("ml", "machine learning", "ai", "deep learning", "neural", "model", "training", "optimization", "algorithm", "network", "learning", "classification", "regression", "transformer", "waveform", "ofdm", "ris", "6g", "foundation")):
            tid = "ml-research"
        elif any(w in nl for w in ("clinical", "trial", "patient", "medical", "drug", "health", "disease", "diagnosis", "therapy")):
            tid = "medical"
        elif any(w in nl for w in ("cell", "gene", "dna", "rna", "protein", "biology", "seq", "genome", "omics")):
            tid = "life-science"
        else:
            tid = None

    uid = _uid()
    db = get_db_path()

    project = create_project(
        db, name=name.strip(), description=description or None, created_by=uid, lab_id=pid,
    )

    if tid:
        from EvoScientist.pm.templates import get_template
        from EvoScientist.pm.crud.phases import assign_task_phase, create_phase
        from EvoScientist.pm.crud.tasks import create_task

        t = get_template(tid)
        if t:
            phase_map = {}
            for pt in t.phases:
                phase = create_phase(db, project_id=project.id, name=pt.name, color=pt.color, position=pt.position, target_date=None, created_by=uid)
                phase_map[pt.name] = phase.id
            for task_t in t.tasks:
                phase_id = phase_map.get(task_t.phase)
                task = create_task(db, project_id=project.id, title=task_t.title, created_by=uid, description=task_t.description, priority=task_t.priority)
                if phase_id and task.id:
                    assign_task_phase(db, task.id, phase_id)
            phase_names = ", ".join(p.name for p in t.phases)
            return f"Created project '{project.name}' with id={project.id} using '{t.name}' template. Phases: {phase_names}"

    return f"Created project '{project.name}' with id={project.id}"


@tool
def pm_list_projects() -> str:
    """List all projects the current user has access to.

    Returns:
        Formatted list of projects with IDs, names, and task counts
    """
    db = get_db_path()
    projects = list_projects_for_user(db, _uid())
    if not projects:
        return "No projects found."
    lines = ["Projects:"]
    for p in projects:
        lines.append(f"  [{p.id}] {p.name} — created {p.created_at[:10]}")
    return "\n".join(lines)


@tool
def pm_get_project(project_id: str) -> str:
    """Get detailed information about a project including description and dates.

    Args:
        project_id: ID of the project

    Returns:
        Project details as formatted text
    """
    db = get_db_path()
    project = get_project(db, project_id)
    if not project:
        return f"Project {project_id} not found."
    return (
        f"Project: {project.name}\n"
        f"Description: {project.description or '(none)'}\n"
        f"Created: {project.created_at[:10]}\n"
        f"Archived: {project.archived_at or 'No'}"
    )


# ── Tasks ─────────────────────────────────────────────────────────────────


@tool
def pm_create_task(project_id: str, title: str, description: str = "", priority: str = "medium") -> str:
    """Create a task in a project.

    Args:
        project_id: ID of the project
        title: Task title
        description: Optional task description
        priority: Priority - high, medium, or low

    Returns:
        Task ID and title on success
    """
    db = get_db_path()
    task = create_task(
        db,
        project_id=project_id,
        title=title,
        created_by=_uid(),
        description=description or None,
        priority=priority,
    )
    return f"Created task '{task.title}' with id={task.id}"


@tool
def pm_list_tasks(project_id: str) -> str:
    """List all tasks in a project.

    Args:
        project_id: ID of the project

    Returns:
        Formatted list of tasks with status and priority
    """
    db = get_db_path()
    tasks = list_tasks(db, project_id)
    if not tasks:
        return "No tasks found in this project."
    lines = [f"Tasks for project {project_id}:"]
    for t in tasks:
        lines.append(f"  [{t.id}] {t.title} — status={t.status}, priority={t.priority}")
    return "\n".join(lines)


# ── Experiments ───────────────────────────────────────────────────────────


@tool
def pm_create_experiment(project_id: str, name: str, hypothesis: str = "", protocol: str = "") -> str:
    """Create an experiment in a project.

    Args:
        project_id: ID of the project
        name: Experiment name
        hypothesis: Scientific hypothesis
        protocol: Experiment protocol description

    Returns:
        Experiment ID on success
    """
    db = get_db_path()
    exp = create_experiment(
        db,
        project_id=project_id,
        name=name,
        created_by=_uid(),
        hypothesis=hypothesis or None,
        protocol=protocol or None,
    )
    return f"Created experiment '{exp.name}' with id={exp.id}"


@tool
def pm_list_experiments(project_id: str) -> str:
    """List all experiments in a project.

    Args:
        project_id: ID of the project

    Returns:
        Formatted list of experiments
    """
    db = get_db_path()
    experiments = list_experiments(db, project_id)
    if not experiments:
        return "No experiments found in this project."
    lines = [f"Experiments for project {project_id}:"]
    for e in experiments:
        lines.append(f"  [{e.id}] {e.name} — status={e.status}")
    return "\n".join(lines)


@tool
def pm_add_experiment_entry(experiment_id: str, entry_type: str, title: str, body: str = "") -> str:
    """Add a note or result entry to an experiment.

    Args:
        experiment_id: ID of the experiment
        entry_type: 'note' for observations or 'result' for experimental results
        title: Entry title
        body: Entry content (markdown supported)

    Returns:
        Entry ID on success
    """
    db = get_db_path()
    entry = create_entry(
        db,
        experiment_id=experiment_id,
        type=entry_type,
        title=title,
        body=body,
        author_id=_uid(),
    )
    return f"Added {entry_type} '{entry.title}' with id={entry.id}"


@tool
def pm_list_experiment_entries(experiment_id: str) -> str:
    """List all entries (notes and results) for an experiment.

    Args:
        experiment_id: ID of the experiment

    Returns:
        Formatted list of entries
    """
    db = get_db_path()
    entries = list_entries(db, experiment_id)
    if not entries:
        return "No entries found for this experiment."
    lines = [f"Entries for experiment {experiment_id}:"]
    for e in entries:
        snippet = (e.body or "")[:80].replace("\n", " ")
        lines.append(f"  [{e.id}] ({e.type}) {e.title}: {snippet}{'...' if len(e.body or '') > 80 else ''}")
    return "\n".join(lines)


# ── Publications ──────────────────────────────────────────────────────────


@tool
def pm_list_publications(project_id: str = "", status: str = "") -> str:
    """List publications.

    Args:
        project_id: Optional project ID to filter by
        status: Optional status filter

    Returns:
        Formatted list of publications
    """
    from EvoScientist.pm.crud.publications import list_publications
    db = get_db_path()
    pubs = list_publications(db, project_id=project_id or None, status=status or None)
    if not pubs:
        return "No publications found."
    lines = ["Publications:"]
    for p in pubs:
        lines.append(f"  [{p.id}] {p.title} — status={p.status}, venue={p.venue or '—'}")
    return "\n".join(lines)


@tool
def pm_get_publication(publication_id: str) -> str:
    """Get details of a publication.

    Args:
        publication_id: ID of the publication

    Returns:
        Publication details
    """
    from EvoScientist.pm.crud.publications import get_publication
    db = get_db_path()
    pub = get_publication(db, publication_id)
    if not pub:
        return f"Publication {publication_id} not found."
    authors = ", ".join(a.get("name", "") for a in (pub.authors or []))
    return (
        f"Title: {pub.title}\n"
        f"Status: {pub.status}\n"
        f"Venue: {pub.venue or '—'}\n"
        f"Authors: {authors or '—'}\n"
        f"Abstract: {(pub.abstract or '')[:200]}"
    )


@tool
def pm_create_publication(title: str, project_id: str = "", venue: str = "", venue_type: str = "journal", abstract: str = "") -> str:
    """Create a publication record.

    Args:
        title: Publication title
        project_id: Optional project ID to associate
        venue: Target venue name
        venue_type: Type (journal, conference, preprint)
        abstract: Optional abstract text

    Returns:
        Publication ID on success
    """
    from EvoScientist.pm.crud.publications import create_publication
    db = get_db_path()
    pub = create_publication(
        db,
        title=title,
        project_id=project_id or None,
        venue=venue or None,
        venue_type=venue_type,
        abstract=abstract or None,
        created_by=_uid(),
    )
    return f"Created publication '{pub.title}' with id={pub.id}"


# ── Labs ──────────────────────────────────────────────────────────────────


@tool
def pm_list_labs() -> str:
    """List all labs in the system.

    Returns:
        Formatted list of labs
    """
    from EvoScientist.pm.crud.labs import list_labs
    db = get_db_path()
    labs = list_labs(db)
    if not labs:
        return "No labs found."
    lines = ["Labs:"]
    for l in labs:
        lines.append(f"  [{l.id}] {l.name} — {l.department}, {l.university}")
    return "\n".join(lines)


@tool
def pm_get_lab(lab_id: str) -> str:
    """Get details of a lab including members.

    Args:
        lab_id: ID of the lab

    Returns:
        Lab details
    """
    from EvoScientist.pm.crud.labs import get_lab
    db = get_db_path()
    lab = get_lab(db, lab_id)
    if not lab:
        return f"Lab {lab_id} not found."
    members = ", ".join(f"{m.username} ({m.role})" for m in (lab.members or []))
    return (
        f"Lab: {lab.name}\n"
        f"Department: {lab.department}\n"
        f"University: {lab.university}\n"
        f"Members: {members or 'none'}"
    )


@tool
def pm_create_lab(name: str, department: str = "", university: str = "") -> str:
    """Create a new research lab. Use when the user explicitly asks to create/found a new lab; the current user becomes its PI.

    The current user is set as the lab's principal investigator (pi_id) and
    added to the lab's members with the 'pi' role.

    Args:
        name: Lab name (required)
        department: Optional department name
        university: Optional university name

    Returns:
        Result message
    """
    if not name or not name.strip():
        return "Error: lab name is required."
    from EvoScientist.pm.crud.labs import add_member, create_lab
    uid = _uid()
    db = get_db_path()
    lab = create_lab(
        db, name=name.strip(), pi_id=uid, department=department, university=university,
    )
    add_member(db, lab.id, uid, "pi")
    return f"Created lab '{lab.name}' with id={lab.id}. You are its PI."


# ── Grants ────────────────────────────────────────────────────────────────


@tool
def pm_list_grants(lab_id: str = "") -> str:
    """List grants.

    Args:
        lab_id: Optional lab ID to filter by

    Returns:
        Formatted list of grants
    """
    from EvoScientist.pm.crud.grants import list_grants
    db = get_db_path()
    grants = list_grants(db, lab_id=lab_id or None)
    if not grants:
        return "No grants found."
    lines = ["Grants:"]
    for g in grants:
        lines.append(f"  [{g.id}] {g.title} — {g.funder}, status={g.status}")
    return "\n".join(lines)


# ── Conferences ───────────────────────────────────────────────────────────


@tool
def pm_list_conferences(status: str = "") -> str:
    """List conferences.

    Args:
        status: Optional status filter

    Returns:
        Formatted list of conferences
    """
    from EvoScientist.pm.crud.conferences import list_conferences
    db = get_db_path()
    confs = list_conferences(db, status=status or None)
    if not confs:
        return "No conferences found."
    lines = ["Conferences:"]
    for c in confs:
        lines.append(f"  [{c.id}] {c.name} — deadline={c.deadline or '—'}, status={c.status}")
    return "\n".join(lines)


# ── IRB / Ethics ──────────────────────────────────────────────────────────


@tool
def pm_list_irbs(project_id: str = "") -> str:
    """List IRB / ethics approvals.

    Args:
        project_id: Optional project ID to filter by

    Returns:
        Formatted list of IRB records
    """
    from EvoScientist.pm.crud.irb import list_irbs
    db = get_db_path()
    irbs = list_irbs(db, project_id=project_id or None)
    if not irbs:
        return "No IRB records found."
    lines = ["IRB Approvals:"]
    for i in irbs:
        lines.append(f"  [{i.id}] {i.title} — {i.institution}, status={i.status}")
    return "\n".join(lines)


# ── Search ────────────────────────────────────────────────────────────────


@tool
def pm_global_search(query: str) -> str:
    """Search across all PM entities (projects, tasks, experiments, publications).

    Args:
        query: Search query string

    Returns:
        Search results as formatted text
    """
    from EvoScientist.pm.api.routes.search import global_search
    db = get_db_path()
    results = global_search(db, query)
    lines = []
    for cat in ("projects", "tasks", "experiments", "publications"):
        items = results.get(cat, [])
        if items:
            lines.append(f"{cat.upper()}:")
            for item in items[:5]:
                lines.append(f"  [{item.get('id','')}] {item.get('name') or item.get('title','')}")
    return "\n".join(lines) if lines else "No results found."


# ── Memory ────────────────────────────────────────────────────────────────


@tool
def pm_search_memory(project_id: str, query: str) -> str:
    """Search AI memory/observations for a project.

    Args:
        project_id: Project ID to search within
        query: Search query

    Returns:
        Relevant observations
    """
    from EvoScientist.pm._ai import search_project_knowledge
    results = search_project_knowledge(project_id=project_id, query=query)
    if not results:
        return "No memory results found."
    lines = ["Memory observations:"]
    for r in results:
        lines.append(f"  [{r.get('id','')}] {r.get('title','')} (score={r.get('score',0):.2f})")
        body = r.get("body", "")[:200]
        if body:
            lines.append(f"    {body}")
    return "\n".join(lines)


PM_TOOLS = [
    pm_create_project,
    pm_list_projects,
    pm_get_project,
    pm_create_task,
    pm_list_tasks,
    pm_create_experiment,
    pm_list_experiments,
    pm_add_experiment_entry,
    pm_list_experiment_entries,
    pm_list_publications,
    pm_get_publication,
    pm_create_publication,
    pm_create_lab,
    pm_list_labs,
    pm_get_lab,
    pm_list_grants,
    pm_list_conferences,
    pm_list_irbs,
    pm_global_search,
    pm_search_memory,
]
