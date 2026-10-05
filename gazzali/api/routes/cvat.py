"""CVAT annotation project integration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ... import cvat_client
from ...crud.cvat import (
    create_cvat_project,
    delete_cvat_project,
    get_cvat_project,
    list_cvat_projects,
    update_cvat_project,
)
from ...crud.experiment_assets import clear_asset_links
from ...crud.experiment_metrics import create_metrics, delete_metrics_by_source
from ...crud.experiments import get_experiment
from ...crud.projects import get_project
from ...db import get_db_path
from ...metrics_csv import ParsedMetric
from ...models import User
from ..deps import require_project_role

router = APIRouter()


class CVATProjectCreate(BaseModel):
    cvat_id: int
    name: str = Field(min_length=1)
    labels_json: str = "[]"


class CVATProjectUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(created|importing|annotating|reviewing|exported|completed)$")
    num_images: int | None = None
    num_annotations: int | None = None
    export_format: str | None = None
    export_key: str | None = None


@router.post("/projects/{project_id}/cvat", status_code=status.HTTP_201_CREATED)
def create_cvat(
    project_id: str,
    body: CVATProjectCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    p = get_project(get_db_path(), project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    cp = create_cvat_project(get_db_path(), project_id, body.cvat_id, body.name, current_user.id, body.labels_json)
    return {"id": cp.id, "name": cp.name, "cvat_id": cp.cvat_id, "status": cp.status}


@router.get("/projects/{project_id}/cvat")
def list_cvat(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    return list_cvat_projects(get_db_path(), project_id)


@router.put("/projects/{project_id}/cvat/{cvat_id}")
def update_cvat(
    project_id: str,
    cvat_id: str,
    body: CVATProjectUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    cp = get_cvat_project(get_db_path(), cvat_id)
    if not cp or cp.project_id != project_id:
        raise HTTPException(404, "CVAT project not found")
    updated = update_cvat_project(
        get_db_path(), cvat_id,
        status=body.status, num_images=body.num_images,
        num_annotations=body.num_annotations,
        export_format=body.export_format, export_key=body.export_key,
    )
    return {"id": updated.id, "status": updated.status, "num_annotations": updated.num_annotations}


@router.delete("/projects/{project_id}/cvat/{cvat_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cvat(
    project_id: str,
    cvat_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    cp = get_cvat_project(get_db_path(), cvat_id)
    if not cp or cp.project_id != project_id:
        raise HTTPException(404, "CVAT project not found")
    # Drop experiment lineage links first: asset_id has no FK to cascade them.
    clear_asset_links(get_db_path(), "cvat_project", cvat_id)
    delete_cvat_project(get_db_path(), cvat_id)


def _own_cvat_or_404(project_id: str, cvat_id: str):
    cp = get_cvat_project(get_db_path(), cvat_id)
    if not cp or cp.project_id != project_id:
        raise HTTPException(404, "CVAT project not found")
    return cp


@router.get("/projects/{project_id}/cvat/{cvat_id}/progress")
async def cvat_progress(
    project_id: str,
    cvat_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """Live annotation progress read from CVAT; also refreshes the stored image count."""
    cp = _own_cvat_or_404(project_id, cvat_id)
    try:
        progress = await cvat_client.project_progress(cp.cvat_id)
    except cvat_client.CVATError as exc:
        raise HTTPException(502, str(exc)) from exc
    if progress["frames_total"] != cp.num_images:
        update_cvat_project(get_db_path(), cvat_id, num_images=progress["frames_total"])
    return progress


@router.post("/projects/{project_id}/experiments/{exp_id}/cvat/{cvat_id}/import-metrics")
async def cvat_import_metrics(
    project_id: str,
    exp_id: str,
    cvat_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Turn CVAT annotations into measured numbers (source "cvat"), replacing the last import."""
    exp = get_experiment(get_db_path(), exp_id)
    if not exp or exp.project_id != project_id:
        raise HTTPException(404, "Experiment not found")
    cp = _own_cvat_or_404(project_id, cvat_id)
    try:
        summary = await cvat_client.annotation_summary(cp.cvat_id)
    except cvat_client.CVATError as exc:
        raise HTTPException(502, str(exc)) from exc
    if summary["frames_annotated"] == 0:
        raise HTTPException(409, "No annotations in CVAT yet; nothing was recorded.")
    metrics = [
        ParsedMetric(name="images annotated", value=summary["frames_annotated"], unit="images", split=cp.name),
        ParsedMetric(name="images in annotation project", value=summary["frames_total"], unit="images", split=cp.name),
        *(ParsedMetric(name=f"annotations: {label}", value=n, unit="objects", split=cp.name)
          for label, n in summary["labels"].items()),
    ]
    db = get_db_path()
    delete_metrics_by_source(db, exp_id, "cvat", cp.name)
    create_metrics(db, exp_id, metrics, recorded_by=current_user.id, source="cvat")
    update_cvat_project(db, cvat_id, num_images=summary["frames_total"], num_annotations=sum(summary["labels"].values()))
    return {"saved": len(metrics), "summary": summary}
