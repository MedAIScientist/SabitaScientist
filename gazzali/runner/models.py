"""Pydantic models for the runner service API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    run_id: str
    agent_type: str = Field(pattern="^(research|code|data_analysis|writing)$")
    prompt: str = Field(min_length=1)
    workspace_dir: str
    # Attribution, so the tokens this run burns can be reported against the person
    # and the paper that asked for it. Optional on purpose: missing bookkeeping
    # must never reject a run.
    task: str | None = None
    user_id: str | None = None
    project_id: str | None = None
    publication_id: str | None = None


class RunEvent(BaseModel):
    type: str   # 'token' | 'status' | 'error'
    data: str
