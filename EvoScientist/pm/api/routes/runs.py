"""Run endpoints — create, list, SSE proxy, cancel."""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ...crud.runs import (
    create_run,
    get_run,
    list_runs_for_task,
    update_run_output,
    update_run_status,
)
from ...crud.tasks import get_task
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role
from ..schemas import RunCreate, RunResponse

router = APIRouter()

RUNNER_URL = os.getenv("RUNNER_URL", "http://127.0.0.1:8001")


def _run_to_response(r) -> RunResponse:
    return RunResponse(
        id=r.id,
        task_id=r.task_id,
        project_id=r.project_id,
        agent_type=r.agent_type,
        prompt=r.prompt,
        status=r.status,
        output=r.output,
        error=r.error,
        started_at=r.started_at,
        finished_at=r.finished_at,
        created_by=r.created_by,
        created_at=r.created_at,
    )


async def _notify_runner(
    run_id: str, agent_type: str, prompt: str, workspace_dir: str
) -> None:
    """Fire-and-forget: tell the runner service to start the agent run."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{RUNNER_URL}/runs",
                json={
                    "run_id": run_id,
                    "agent_type": agent_type,
                    "prompt": prompt,
                    "workspace_dir": workspace_dir,
                },
            )
    except Exception:
        # Runner unreachable — mark run as failed so UI shows an error
        update_run_status(get_db_path(), run_id, "failed")


@router.post(
    "/{project_id}/tasks/{task_id}/runs",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_run(
    project_id: str,
    task_id: str,
    body: RunCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Create a run record and dispatch it to the runner service."""
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")

    run = create_run(
        get_db_path(),
        task_id=task_id,
        project_id=project_id,
        agent_type=body.agent_type,
        prompt=body.prompt,
        created_by=current_user.id,
    )

    # Workspace isolated per project + task
    workspace_base = os.getenv(
        "EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs")
    )
    workspace_dir = str(Path(workspace_base) / project_id / task_id)

    background_tasks.add_task(
        _notify_runner, run.id, body.agent_type, body.prompt, workspace_dir
    )
    return _run_to_response(run)


@router.get("/{project_id}/tasks/{task_id}/runs", response_model=list[RunResponse])
def list_task_runs(
    project_id: str,
    task_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    """List all runs for a task, newest first."""
    task = get_task(get_db_path(), task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return [_run_to_response(r) for r in list_runs_for_task(get_db_path(), task_id)]


@router.get("/runs/{run_id}/stream")
async def stream_run_output(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """SSE stream of run output tokens. Returns saved output if run is complete."""
    run = get_run(get_db_path(), run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Already complete — stream saved output then close
    if run.status in ("done", "failed", "cancelled"):
        async def _completed():
            if run.output:
                yield f'data: {json.dumps({"type": "token", "data": run.output})}\n\n'
            yield f'data: {json.dumps({"type": "status", "data": run.status})}\n\n'
        return StreamingResponse(
            _completed(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Mark running and proxy SSE from runner
    update_run_status(get_db_path(), run_id, "running")

    async def _proxy():
        accumulated: list[str] = []
        final_status = "failed"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
                async with client.stream(
                    "GET", f"{RUNNER_URL}/runs/{run_id}/stream"
                ) as resp:
                    async for raw_line in resp.aiter_lines():
                        if not raw_line:
                            continue
                        yield f"{raw_line}\n\n"
                        if raw_line.startswith("data: "):
                            try:
                                event = json.loads(raw_line[6:])
                                if event.get("type") == "token":
                                    accumulated.append(event["data"])
                                elif event.get("type") == "status":
                                    final_status = event["data"]
                            except Exception:
                                pass
        except Exception as exc:
            yield f'data: {json.dumps({"type": "error", "data": str(exc)})}\n\n'
            yield f'data: {json.dumps({"type": "status", "data": "failed"})}\n\n'
            final_status = "failed"
        finally:
            update_run_output(
                get_db_path(), run_id, final_status, "".join(accumulated)
            )

    return StreamingResponse(
        _proxy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
):
    """Cancel a running run."""
    run = get_run(get_db_path(), run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.delete(f"{RUNNER_URL}/runs/{run_id}")
    except Exception:
        pass
    update_run_status(get_db_path(), run_id, "cancelled")
