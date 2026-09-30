"""Background AI jobs, as seen by the user who started them."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...crud.ai_jobs import get_job, list_jobs
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user
from ..schemas import AiJobResponse

router = APIRouter()


@router.get("/ai-jobs", response_model=list[AiJobResponse])
def list_my_jobs(
    project_id: str | None = Query(None),
    publication_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """The caller's own jobs, newest first. Jobs belong to whoever started them."""
    return list_jobs(
        get_db_path(), user_id=current_user.id,
        project_id=project_id, publication_id=publication_id, limit=limit,
    )


@router.get("/ai-jobs/{job_id}", response_model=AiJobResponse)
def get_my_job(job_id: str, current_user: User = Depends(get_current_user)):
    job = get_job(get_db_path(), job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
