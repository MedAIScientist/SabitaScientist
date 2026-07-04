"""Agent tools for reading and writing PM entities (projects, tasks, experiments)."""

from __future__ import annotations

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


@tool
def pm_create_project(name: str, description: str = "", lab_id: str = "") -> str:
    """Create a new research project in the Project Management system.

    Args:
        name: Project name
        description: Optional project description
        lab_id: Optional lab/group ID to associate the project with

    Returns:
        Project ID and name on success
    """
    db = get_db_path()
    project = create_project(
        db,
        name=name,
        description=description or None,
        created_by="agent",
        lab_id=lab_id or None,
    )
    return f"Created project '{project.name}' with id={project.id}"


@tool
def pm_list_projects() -> str:
    """List all projects visible to the agent.

    Returns:
        Formatted list of projects with IDs, names, and task counts
    """
    db = get_db_path()
    projects = list_projects_for_user(db, "agent")
    if not projects:
        return "No projects found."
    lines = ["Projects:"]
    for p in projects:
        lines.append(f"  [{p.id}] {p.name} — created {p.created_at[:10]}")
    return "\n".join(lines)


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
        created_by="agent",
        description=description or None,
        priority=priority,
    )
    return f"Created task '{task.title}' with id={task.id} in project {project_id}"


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
        created_by="agent",
        hypothesis=hypothesis or None,
        protocol=protocol or None,
    )
    return f"Created experiment '{exp.name}' with id={exp.id} in project {project_id}"


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
        author_id="agent",
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


PM_TOOLS = [
    pm_create_project,
    pm_list_projects,
    pm_create_task,
    pm_list_tasks,
    pm_get_project,
    pm_create_experiment,
    pm_add_experiment_entry,
    pm_list_experiment_entries,
    pm_list_experiments,
]
