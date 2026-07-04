"""Project template loader — discovers YAML templates and hydrates projects."""

from __future__ import annotations

from pathlib import Path

import yaml

_TEMPLATES_DIR = Path(__file__).parent


class TaskTemplate:
    def __init__(self, data: dict) -> None:
        self.title: str = data["title"]
        self.description: str = data.get("description", "")
        self.phase: str = data["phase"]
        self.priority: str = data.get("priority", "medium")


class ExperimentTypeTemplate:
    def __init__(self, data: dict) -> None:
        self.name: str = data["name"]
        self.description: str = data.get("description", "")
        self.protocol_template: str = data.get("protocol_template", "")


class PhaseTemplate:
    def __init__(self, data: dict) -> None:
        self.name: str = data["name"]
        self.color: str = data.get("color", "#6366f1")
        self.position: int = data.get("position", 0)


class ProjectTemplate:
    def __init__(self, data: dict) -> None:
        self.id: str = data["id"]
        self.name: str = data["name"]
        self.description: str = data.get("description", "")
        self.domain: str = data.get("domain", "general")
        self.icon: str = data.get("icon", "📋")
        self.phases: list[PhaseTemplate] = [PhaseTemplate(p) for p in data.get("phases", [])]
        self.experiment_types: list[ExperimentTypeTemplate] = [
            ExperimentTypeTemplate(e) for e in data.get("experiment_types", [])
        ]
        self.tasks: list[TaskTemplate] = [TaskTemplate(t) for t in data.get("tasks", [])]


def _discover_templates() -> list[ProjectTemplate]:
    """Scan the templates directory for all *.yaml template files."""
    templates: list[ProjectTemplate] = []
    if not _TEMPLATES_DIR.exists():
        return templates
    for path in sorted(_TEMPLATES_DIR.glob("*.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f)
        if data:
            templates.append(ProjectTemplate(data))
    return templates


def get_template(template_id: str) -> ProjectTemplate | None:
    """Return a template by its id, or None."""
    for t in _discover_templates():
        if t.id == template_id:
            return t
    return None


def list_templates() -> list[ProjectTemplate]:
    """Return all available project templates."""
    return _discover_templates()


def template_to_dict(t: ProjectTemplate) -> dict:
    """Serialize a template to a plain dict for API responses."""
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "domain": t.domain,
        "icon": t.icon,
        "phases": [
            {"name": p.name, "color": p.color, "position": p.position}
            for p in t.phases
        ],
        "experiment_types": [
            {"name": e.name, "description": e.description}
            for e in t.experiment_types
        ],
        "tasks": [
            {"title": t.title, "description": t.description, "phase": t.phase, "priority": t.priority}
            for t in t.tasks
        ],
    }
