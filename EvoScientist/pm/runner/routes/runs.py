"""Runner run endpoints: start, stream SSE, cancel."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from .. import agent_runner
from ..models import RunRequest

router = APIRouter()


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def start_run(body: RunRequest):
    """Accept a run request and launch the agent as a background asyncio task."""
    await agent_runner.start_run(
        body.run_id, body.agent_type, body.prompt, body.workspace_dir
    )
    return {"run_id": body.run_id}


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    """SSE stream of token and status events for a run."""
    async def event_gen():
        async for event in agent_runner.stream_events(run_id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_run(run_id: str):
    """Cancel an in-progress run."""
    cancelled = await agent_runner.cancel(run_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Run not found or already complete")
