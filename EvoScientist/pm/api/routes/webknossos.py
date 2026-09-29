"""WebKnossos dataset integration for 3D EM annotation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ...crud.experiment_assets import clear_asset_links
from ...crud.projects import get_project
from ...crud.webknossos import (
    create_wk_dataset,
    delete_wk_dataset,
    get_wk_dataset,
    list_wk_datasets,
    update_wk_dataset,
)
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role

router = APIRouter()


class WKCreate(BaseModel):
    name: str = Field(min_length=1)
    directory_name: str = Field(min_length=1)
    wk_id: str | None = None


class WKUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(imported|segmenting|proofreading|completed|archived)$")
    segmentation_status: str | None = None
    num_skeletons: int | None = None
    num_volumes: int | None = None
    wk_id: str | None = None


@router.post("/projects/{project_id}/webknossos", status_code=status.HTTP_201_CREATED)
def create_wk(
    project_id: str,
    body: WKCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    p = get_project(get_db_path(), project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    ds = create_wk_dataset(get_db_path(), project_id, body.name, body.directory_name, current_user.id, body.wk_id)
    return {"id": ds.id, "name": ds.name, "status": ds.status}


@router.get("/projects/{project_id}/webknossos")
def list_wk(
    project_id: str,
    current_user: User = Depends(get_current_user),
):
    return list_wk_datasets(get_db_path(), project_id)


@router.put("/projects/{project_id}/webknossos/{wk_ds_id}")
def update_wk(
    project_id: str,
    wk_ds_id: str,
    body: WKUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    ds = get_wk_dataset(get_db_path(), wk_ds_id)
    if not ds or ds.project_id != project_id:
        raise HTTPException(404, "WebKnossos dataset not found")
    updated = update_wk_dataset(
        get_db_path(), wk_ds_id,
        status=body.status, segmentation_status=body.segmentation_status,
        num_skeletons=body.num_skeletons, num_volumes=body.num_volumes,
        wk_id=body.wk_id,
    )
    return {"id": updated.id, "status": updated.status}


@router.delete("/projects/{project_id}/webknossos/{wk_ds_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wk(
    project_id: str,
    wk_ds_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    ds = get_wk_dataset(get_db_path(), wk_ds_id)
    if not ds or ds.project_id != project_id:
        raise HTTPException(404, "WebKnossos dataset not found")
    # Drop experiment lineage links first: asset_id has no FK to cascade them.
    clear_asset_links(get_db_path(), "webknossos_dataset", wk_ds_id)
    delete_wk_dataset(get_db_path(), wk_ds_id)
