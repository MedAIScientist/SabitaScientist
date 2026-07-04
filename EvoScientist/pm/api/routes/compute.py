"""Compute resource management — register clusters, launch experiments remotely."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from ...compute.base import ComputeResource, get_backend
from ...crud.experiment_entries import create_entry
from ...crud.experiments import get_experiment
from ...crud.projects import get_project
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role
from ..schemas import ComputeResourceCreate, ComputeRunRequest

router = APIRouter()
_db_resource_path = Path.home() / ".config" / "evoscientist" / "compute_resources.json"


def _load_resources() -> list[ComputeResource]:
    if not _db_resource_path.exists():
        # Create default local resource
        defaults = [ComputeResource(
            id=uuid.uuid4().hex, name="Local Machine",
            backend_type="local", config={},
            status="online",
            created_at=datetime.now(UTC).isoformat(),
        )]
        _save_resources(defaults)
        return defaults
    data = json.loads(_db_resource_path.read_text())
    return [ComputeResource(**r) for r in data]


def _save_resources(resources: list[ComputeResource]) -> None:
    _db_resource_path.parent.mkdir(parents=True, exist_ok=True)
    data = [{"id": r.id, "name": r.name, "backend_type": r.backend_type,
             "config": r.config, "status": r.status, "created_at": r.created_at}
            for r in resources]
    _db_resource_path.write_text(json.dumps(data, indent=2))


@router.get("/compute/resources")
def list_resources(current_user: User = Depends(get_current_user)):
    return [
        {"id": r.id, "name": r.name, "type": r.backend_type, "status": r.status,
         "created_at": r.created_at}
        for r in _load_resources()
    ]


@router.post("/compute/resources", status_code=status.HTTP_201_CREATED)
def create_resource(body: ComputeResourceCreate, current_user: User = Depends(get_current_user)):
    resources = _load_resources()
    new_res = ComputeResource(
        id=uuid.uuid4().hex,
        name=body.name,
        backend_type=body.backend_type,
        config=body.config or {},
        status="unknown",
        created_at=datetime.now(UTC).isoformat(),
    )
    resources.append(new_res)
    _save_resources(resources)
    return {"id": new_res.id, "name": new_res.name, "type": new_res.backend_type}


@router.delete("/compute/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resource(resource_id: str, current_user: User = Depends(get_current_user)):
    resources = _load_resources()
    _save_resources([r for r in resources if r.id != resource_id])


@router.post("/compute/run")
async def run_on_compute(
    body: ComputeRunRequest,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Run a command on a compute resource and save results to an experiment entry."""
    resources = _load_resources()
    resource = next((r for r in resources if r.id == body.resource_id), None)
    if not resource:
        raise HTTPException(404, "Compute resource not found")

    db = get_db_path()
    project = get_project(db, body.project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    backend = get_backend(resource.backend_type)
    run_id = await backend.submit_job(resource, body.command, body.work_dir, body.env)

    exp = get_experiment(db, body.experiment_id) if body.experiment_id else None
    if not exp:
        from ...crud.experiments import create_experiment
        exp = create_experiment(
            db, project_id=body.project_id,
            name=f"Compute: {body.command[:60]}",
            created_by=current_user.id,
        )

    create_entry(
        db, experiment_id=exp.id, type="note",
        title=f"Compute Run ({resource.name})",
        body=json.dumps({
            "run_id": run_id,
            "resource": resource.name,
            "backend": resource.backend_type,
            "command": body.command,
            "work_dir": body.work_dir,
            "env": body.env,
            "status": "submitted",
            "submitted_at": datetime.now(UTC).isoformat(),
        }, indent=2),
        author_id=current_user.id,
    )

    return {
        "run_id": run_id,
        "experiment_id": exp.id,
        "resource": resource.name,
        "status": "submitted",
    }


@router.get("/compute/run/{run_id}/status")
async def get_run_status(run_id: str, current_user: User = Depends(get_current_user)):
    # Try to find the backend from stored run data
    return {"run_id": run_id, "status": "checking"}


@router.get("/compute/backends")
def list_backends(current_user: User = Depends(get_current_user)):
    return [
        {"id": "local", "name": "Local Machine", "description": "Run commands on this server"},
        {"id": "ssh", "name": "SSH Remote", "description": "Execute on a remote server via SSH"},
        {"id": "slurm", "name": "SLURM Cluster", "description": "Submit batch jobs to a SLURM cluster"},
    ]
