"""Pydantic models for the runner service API."""
from __future__ import annotations
from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    run_id: str
    agent_type: str = Field(pattern="^(research|code|data_analysis|writing)$")
    prompt: str = Field(min_length=1)
    workspace_dir: str


class RunEvent(BaseModel):
    type: str   # 'token' | 'status' | 'error'
    data: str
