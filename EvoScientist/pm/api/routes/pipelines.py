"""De-identification pipeline endpoints — define pipelines, track runs, verify PHI removal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...crud.experiment_assets import clear_asset_links
from ...crud.pipelines import (
    create_pipeline,
    create_run,
    delete_pipeline,
    get_pipeline,
    get_run,
    list_pipelines,
    list_project_runs,
    list_runs,
    update_pipeline,
    update_run,
)
from ...crud.projects import get_project
from ...db import get_db_path
from ...models import User
from ..deps import require_project_role
from ..schemas import (
    PipelineCreate,
    PipelineResponse,
    PipelineRunCreate,
    PipelineRunResponse,
    PipelineRunUpdate,
    PipelineUpdate,
)

router = APIRouter()


@router.post(
    "/projects/{project_id}/deid-pipelines",
    response_model=PipelineResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pipeline_endpoint(
    project_id: str,
    body: PipelineCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    p = get_project(get_db_path(), project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return create_pipeline(
        get_db_path(),
        project_id,
        body.name,
        body.pipeline_type,
        current_user.id,
        body.description,
        body.config_json,
    )


@router.get(
    "/projects/{project_id}/deid-pipelines", response_model=list[PipelineResponse]
)
def list_pipelines_endpoint(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    return list_pipelines(get_db_path(), project_id)


@router.get(
    "/projects/{project_id}/deid-pipelines/{pipeline_id}",
    response_model=PipelineResponse,
)
def get_pipeline_endpoint(
    project_id: str,
    pipeline_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    p = get_pipeline(get_db_path(), pipeline_id)
    if not p or p.project_id != project_id:
        raise HTTPException(404, "Pipeline not found")
    return p


@router.put(
    "/projects/{project_id}/deid-pipelines/{pipeline_id}",
    response_model=PipelineResponse,
)
def update_pipeline_endpoint(
    project_id: str,
    pipeline_id: str,
    body: PipelineUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    p = get_pipeline(get_db_path(), pipeline_id)
    if not p or p.project_id != project_id:
        raise HTTPException(404, "Pipeline not found")
    return update_pipeline(
        get_db_path(),
        pipeline_id,
        name=body.name,
        description=body.description,
        config_json=body.config_json,
    )


@router.delete(
    "/projects/{project_id}/deid-pipelines/{pipeline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_pipeline_endpoint(
    project_id: str,
    pipeline_id: str,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    p = get_pipeline(get_db_path(), pipeline_id)
    if not p or p.project_id != project_id:
        raise HTTPException(404, "Pipeline not found")
    # Runs cascade with the pipeline, so clear their experiment lineage links first
    # (asset_id has no FK to cascade them).
    for run in list_runs(get_db_path(), pipeline_id):
        clear_asset_links(get_db_path(), "pipeline_run", run.id)
    delete_pipeline(get_db_path(), pipeline_id)


# ── Pipeline Runs ─────────────────────────────────────────────────────────


@router.post(
    "/projects/{project_id}/deid-pipelines/{pipeline_id}/runs",
    response_model=PipelineRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_run_endpoint(
    project_id: str,
    pipeline_id: str,
    body: PipelineRunCreate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    p = get_pipeline(get_db_path(), pipeline_id)
    if not p or p.project_id != project_id:
        raise HTTPException(404, "Pipeline not found")
    return create_run(
        get_db_path(),
        project_id,
        pipeline_id,
        body.input_location,
        body.output_location,
        current_user.id,
        body.irb_id,
    )


@router.get(
    "/projects/{project_id}/deid-pipelines/{pipeline_id}/runs",
    response_model=list[PipelineRunResponse],
)
def list_runs_endpoint(
    project_id: str,
    pipeline_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    # The pipeline must belong to the project the caller was checked against;
    # without this, a role in one project would read another project's run
    # input/output locations by passing that pipeline's id.
    pipeline = get_pipeline(get_db_path(), pipeline_id)
    if not pipeline or pipeline.project_id != project_id:
        raise HTTPException(404, "Pipeline not found")
    return list_runs(get_db_path(), pipeline_id)


@router.get(
    "/projects/{project_id}/deid-pipeline-runs",
    response_model=list[PipelineRunResponse],
    summary="Every de-identification run in the project",
)
def list_project_runs_endpoint(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """Flat run list, so an experiment's lineage can offer runs to pick from."""
    return list_project_runs(get_db_path(), project_id)


@router.get(
    "/projects/{project_id}/deid-pipelines/{pipeline_id}/runs/{run_id}",
    response_model=PipelineRunResponse,
)
def get_run_endpoint(
    project_id: str,
    pipeline_id: str,
    run_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    r = get_run(get_db_path(), run_id)
    if not r or r.project_id != project_id:
        raise HTTPException(404, "Run not found")
    return r


@router.put(
    "/projects/{project_id}/deid-pipelines/{pipeline_id}/runs/{run_id}",
    response_model=PipelineRunResponse,
)
def update_run_endpoint(
    project_id: str,
    pipeline_id: str,
    run_id: str,
    body: PipelineRunUpdate,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    r = get_run(get_db_path(), run_id)
    if not r or r.project_id != project_id:
        raise HTTPException(404, "Run not found")
    return update_run(
        get_db_path(),
        run_id,
        status=body.status,
        output_location=body.output_location,
        input_size_bytes=body.input_size_bytes,
        output_size_bytes=body.output_size_bytes,
        records_processed=body.records_processed,
        phi_fields_removed=body.phi_fields_removed,
        verification_status=body.verification_status,
        verification_notes=body.verification_notes,
        error=body.error,
    )
