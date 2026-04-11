"""Experiment AI writing assistant endpoints."""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ...crud.assists import (
    create_assist,
    get_assist,
    list_assists_for_experiment,
    update_assist_output,
    update_assist_status,
)
from ...crud.experiment_entries import list_entries
from ...crud.experiments import get_experiment, list_linked_tasks
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_project_role
from ..schemas import AssistCreate, AssistResponse

router = APIRouter()
global_router = APIRouter()

RUNNER_URL = os.getenv("RUNNER_URL", "http://127.0.0.1:8001")
_MAX_ENTRY_BODY = 500  # chars per entry body in context snapshot


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assist_to_response(a) -> AssistResponse:
    return AssistResponse(
        id=a.id,
        experiment_id=a.experiment_id,
        project_id=a.project_id,
        prompt=a.prompt,
        status=a.status,
        output=a.output,
        error=a.error,
        target_field=a.target_field,
        created_by=a.created_by,
        created_at=a.created_at,
        finished_at=a.finished_at,
    )


def _build_context(experiment_id: str, project_id: str) -> str:
    """Assemble a JSON snapshot of experiment + entries + linked task titles."""
    exp = get_experiment(get_db_path(), experiment_id)
    entries = list_entries(get_db_path(), experiment_id)

    linked_task_titles: list[str] = []
    try:
        linked = list_linked_tasks(get_db_path(), experiment_id)
        linked_task_titles = [t.title for t in linked]
    except Exception:
        pass

    entry_snippets = [
        {
            "type": e.type,
            "title": e.title,
            "body": (e.body or "")[:_MAX_ENTRY_BODY],
        }
        for e in entries
    ]

    ctx = {
        "name": exp.name,
        "hypothesis": exp.hypothesis or "",
        "protocol": exp.protocol or "",
        "status": exp.status,
        "tags": exp.tags if isinstance(exp.tags, list) else [],
        "deadline": exp.deadline or "" if hasattr(exp, "deadline") else "",
        "entries": entry_snippets,
        "linked_tasks": linked_task_titles,
    }
    return json.dumps(ctx)


def _build_prompt(prompt: str, context_json: str) -> str:
    """Combine experiment context with user prompt for the writing agent."""
    ctx = json.loads(context_json)
    lines = [
        "You are an AI writing assistant for a scientific experiment.",
        "",
        f"Experiment: {ctx['name']}",
        f"Hypothesis: {ctx['hypothesis'] or 'not set'}",
        f"Protocol: {ctx['protocol'] or 'not set'}",
        f"Status: {ctx['status']}",
        f"Tags: {', '.join(ctx['tags']) if ctx.get('tags') else 'none'}",
    ]
    if ctx.get("entries"):
        notes = [e for e in ctx["entries"] if e["type"] == "note"]
        results = [e for e in ctx["entries"] if e["type"] == "result"]
        if notes:
            lines.append("\nExisting notes:")
            for e in notes:
                lines.append(f"  - {e['title']}: {e['body']}")
        if results:
            lines.append("\nExisting results:")
            for e in results:
                lines.append(f"  - {e['title']}: {e['body']}")
    if ctx.get("linked_tasks"):
        lines.append(f"\nLinked tasks: {', '.join(ctx['linked_tasks'])}")
    lines.append(f"\nUser request: {prompt}")
    return "\n".join(lines)


async def _notify_runner(assist_id: str, full_prompt: str, workspace_dir: str) -> None:
    """Fire-and-forget: tell the runner to start the writing agent."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{RUNNER_URL}/runs",
                json={
                    "run_id": assist_id,
                    "agent_type": "writing",
                    "prompt": full_prompt,
                    "workspace_dir": workspace_dir,
                },
            )
    except Exception:
        update_assist_status(get_db_path(), assist_id, "failed")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/experiments/{exp_id}/assist",
    response_model=AssistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an AI writing assist for an experiment",
)
async def create_experiment_assist(
    project_id: str,
    exp_id: str,
    body: AssistCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_project_role("owner", "editor")),
):
    """Create an assist record and dispatch the writing agent."""
    exp = get_experiment(get_db_path(), exp_id)
    if not exp or exp.project_id != project_id:
        raise HTTPException(status_code=404, detail="Experiment not found")

    context_json = _build_context(exp_id, project_id)
    full_prompt = _build_prompt(body.prompt, context_json)

    assist = create_assist(
        get_db_path(),
        experiment_id=exp_id,
        project_id=project_id,
        prompt=body.prompt,
        context_json=context_json,
        target_field=body.target_field,
        created_by=current_user.id,
    )

    workspace_base = os.getenv(
        "EVOSCIENTIST_WORKSPACE_DIR", str(Path.home() / "evoscientist" / "runs")
    )
    workspace_dir = str(Path(workspace_base) / "assists" / assist.id)

    background_tasks.add_task(_notify_runner, assist.id, full_prompt, workspace_dir)
    return _assist_to_response(assist)


@router.get(
    "/{project_id}/experiments/{exp_id}/assists",
    response_model=list[AssistResponse],
    summary="List AI assists for an experiment",
)
def list_experiment_assists(
    project_id: str,
    exp_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    exp = get_experiment(get_db_path(), exp_id)
    if not exp or exp.project_id != project_id:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return [
        _assist_to_response(a)
        for a in list_assists_for_experiment(get_db_path(), exp_id)
    ]


@global_router.get(
    "/assists/{assist_id}/stream",
    summary="SSE stream of assist output tokens",
)
async def stream_assist_output(
    assist_id: str,
    current_user: User = Depends(get_current_user),
):
    """SSE stream. Returns saved output immediately if assist is already complete."""
    assist = get_assist(get_db_path(), assist_id)
    if not assist:
        raise HTTPException(status_code=404, detail="Assist not found")

    if assist.status in ("done", "failed", "cancelled"):
        async def _completed():
            if assist.output:
                yield f'data: {json.dumps({"type": "token", "data": assist.output})}\n\n'
            yield f'data: {json.dumps({"type": "status", "data": assist.status})}\n\n'
        return StreamingResponse(
            _completed(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    update_assist_status(get_db_path(), assist_id, "running")

    async def _proxy():
        accumulated: list[str] = []
        final_status = "failed"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(None)) as client:
                async with client.stream(
                    "GET", f"{RUNNER_URL}/runs/{assist_id}/stream"
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
            update_assist_output(
                get_db_path(), assist_id, final_status, "".join(accumulated)
            )

    return StreamingResponse(
        _proxy(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@global_router.delete(
    "/assists/{assist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a running assist",
)
async def cancel_assist(
    assist_id: str,
    current_user: User = Depends(get_current_user),
):
    assist = get_assist(get_db_path(), assist_id)
    if not assist:
        raise HTTPException(status_code=404, detail="Assist not found")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.delete(f"{RUNNER_URL}/runs/{assist_id}")
    except Exception:
        pass
    update_assist_status(get_db_path(), assist_id, "cancelled")
