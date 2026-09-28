"""Memory integration — search observations, launch workers, manage relations and autoskill proposals.

Wraps EvoScientist's memory subsystem for PM dashboard use:
  - ``memory/search.py`` — TF-IDF search across project observations
  - ``memory/launch.py`` — background memory workers for project context
  - ``memory/relations.py`` — link PM observations
  - ``memory/autoskills/`` — browse/manage skill proposals
  - ``memory/observations/store.py`` — list/read observations
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...models import User
from ..deps import get_current_user

router = APIRouter()


def _mem_dir() -> str:
    """Resolve the EvoScientist memory directory from paths."""
    from ....paths import MEMORIES_DIR

    return str(MEMORIES_DIR)


@router.get("/memory/observations")
def list_observations(
    project_id: str = Query(min_length=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    """List observations for a project via EvoScientist.memory.

    Uses ``list_observation_documents()`` from memory/observations/store.
    """
    from ....memory.observations.store import list_observation_documents

    docs = list_observation_documents(
        memory_dir=_mem_dir(),
        project_id=project_id,
    )
    return {
        "observations": [
            {
                "id": d.observation_id,
                "title": d.summary,
                "body": (d.body or "")[:500],
                "memory_type": str(d.memory_type),
                "scope": str(d.scope),
            }
            for d in docs[:limit]
        ],
        "total": len(docs),
    }


@router.get("/memory/search")
def search_memory(
    project_id: str = Query(min_length=1),
    q: str = Query(min_length=2),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """Search project observations using EvoScientist's TF-IDF ranked search.

    Uses ``search_documents()`` from memory/search.py with RANKED mode.
    """
    from ....memory.observations.store import list_observation_documents
    from ....memory.search import ObservationSearchMode, search_documents

    docs = list_observation_documents(
        memory_dir=_mem_dir(),
        project_id=project_id,
    )
    hits = search_documents(
        documents=docs,
        query=q,
        limit=limit,
        mode=ObservationSearchMode.RANKED,
    )
    return {
        "results": [
            {
                "id": h.get("id", ""),
                "title": h.get("title", h.get("summary", "")),
                "body": (h.get("body", "") or "")[:500],
                "score": h.get("score", 0.0),
                "tags": h.get("tags", []),
            }
            for h in hits
        ]
    }


@router.post("/memory/observations", status_code=status.HTTP_201_CREATED)
def record_observation(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Record an observation via EvoScientist.memory for a project.

    Uses ``record_observation_file()`` from memory/observations/store.
    """
    from ....memory.observations.store import record_observation_file
    from ....memory.types import MemoryScope, MemorySourceType, MemoryType

    project_id = body.get("project_id", "")
    summary = body.get("title", "") or body.get("summary", "")
    observation = body.get("body", "") or body.get("observation", "")

    if not project_id or not summary:
        raise HTTPException(status_code=400, detail="project_id and title are required")

    record_observation_file(
        memory_dir=_mem_dir(),
        project_id=project_id,
        memory_type=MemoryType.SEMANTIC,
        summary=summary,
        observation=observation[:3000],
        why_it_matters="Recorded via PM dashboard.",
        scope=MemoryScope.PROJECT,
        source_type=MemorySourceType.TURN,
        source_session_id=body.get("session_id", "pm_dashboard"),
        source_agent="pm_dashboard",
    )
    return {"status": "recorded", "project_id": project_id, "title": summary}


@router.post("/memory/observations/link", status_code=status.HTTP_201_CREATED)
def link_observations(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Link two observations with a semantic relation.

    Uses ``link_observation_files()`` from memory/relations.py.
    Relations: ``complements``, ``contradicts``, ``supersedes``.
    """
    from ....memory.observations.relations import (
        ObservationRelation,
        link_observation_files,
    )

    project_id = body.get("project_id", "")
    source_id = body.get("source_observation_id", "")
    target_id = body.get("target_observation_id", "")
    reason = body.get("reason", "")
    relation_str = body.get("relation", "complements")

    if not all([project_id, source_id, target_id]):
        raise HTTPException(
            status_code=400,
            detail="project_id, source_observation_id, target_observation_id required",
        )

    try:
        relation = ObservationRelation(relation_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid relation: {relation_str}. Use: complements, contradicts, supersedes",
        ) from exc

    result = link_observation_files(
        memory_dir=_mem_dir(),
        project_id=project_id,
        source_observation_id=source_id,
        target_observation_id=target_id,
        reason=reason or f"Linked via PM dashboard as {relation.value}",
        relation=relation,
        bidirectional=body.get("bidirectional", True),
    )
    return result


@router.get("/memory/workers/status")
def memory_worker_status(
    project_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Check memory worker status for a project.

    Uses ``memory_worker_launch_request()`` / ``snapshot_memory_outputs()``
    from memory/launch.py to inspect what workers have produced.
    """
    from ....memory.launch import snapshot_memory_outputs

    snapshot = snapshot_memory_outputs(memory_dir=_mem_dir())
    return {
        "profile_count": len(snapshot.profile_files) if snapshot else 0,
        "observation_count": len(snapshot.observation_files) if snapshot else 0,
    }


@router.post("/memory/workers/launch", status_code=status.HTTP_202_ACCEPTED)
def launch_memory_worker(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Launch a background memory worker for a project.

    Uses ``alaunch_memory_worker()`` from memory/launch.py to process
    project observations into indexed memory the agent can search.
    """
    import asyncio

    from ....memory.launch import alaunch_memory_worker
    from ....memory.source_context import (
        MemorySourceContext,
        MemorySourceType,
    )

    project_id = body.get("project_id", "")
    workspace_dir = body.get("workspace_dir", "")

    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    context = MemorySourceContext(
        source_type=MemorySourceType.TURN,
        memory_dir=__import__("pathlib").Path(_mem_dir()),
        workspace_dir=__import__("pathlib").Path(workspace_dir) if workspace_dir else __import__("pathlib").Path("."),
        project_id=project_id,
        source_agent="pm_dashboard",
        session_id="",
        trajectory=[],
        trajectory_digest="",
    )

    try:
        run = asyncio.run(alaunch_memory_worker(context))
    except RuntimeError:
        # No running event loop — fire and forget via a new thread
        import threading

        def _run():
            asyncio.run(alaunch_memory_worker(context))

        threading.Thread(target=_run, daemon=True).start()
        return {"status": "launched", "project_id": project_id, "async": True}

    return {
        "status": "launched",
        "project_id": project_id,
        "run_id": run.run_id if run else None,
    }


@router.get("/memory/skills/proposals")
def list_skill_proposals(
    status: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    """List AutoSkills proposals — skills EvoScientist suggests creating.

    Uses ``list_skill_proposals()`` from memory/autoskills/proposals.py.
    """
    from ....memory.autoskills.proposals import list_skill_proposals

    proposals = list_skill_proposals(
        memory_dir=_mem_dir(),
        status=status,
    )
    return {
        "proposals": [
            {
                "id": p.proposal_id,
                "skill_name": p.skill_name,
                "description": p.description,
                "status": p.status,
                "operation": p.operation,
                "project_id": p.project_id,
                "created_at": p.created_at,
                "source_observation_count": len(p.source_observation_ids),
            }
            for p in proposals
        ]
    }


@router.post("/memory/skills/proposals/{proposal_id}/approve")
def approve_skill_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user),
):
    """Approve an AutoSkills proposal, creating the skill.

    Uses ``approve_skill_proposal()`` from memory/autoskills/proposals.py.
    """
    from ....memory.autoskills.proposals import approve_skill_proposal

    try:
        result = approve_skill_proposal(memory_dir=_mem_dir(), proposal_id=proposal_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Proposal not found") from exc

    return {"status": "approved", "details": result}


@router.post("/memory/skills/proposals/{proposal_id}/reject")
def reject_skill_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user),
):
    """Reject an AutoSkills proposal.

    Uses ``reject_skill_proposal()`` from memory/autoskills/proposals.py.
    """
    from ....memory.autoskills.proposals import reject_skill_proposal

    try:
        result = reject_skill_proposal(memory_dir=_mem_dir(), proposal_id=proposal_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Proposal not found") from exc

    return {"status": "rejected", "details": result}


@router.get("/memory/skills/candidates")
def list_skill_candidates(
    project_id: str | None = Query(None),
    current_user: User = Depends(get_current_user),
):
    """List candidate skills EvoScientist's AutoSkills system has identified.

    Uses ``autoskill_candidates()`` from memory/autoskills/candidates.py.
    """
    from ....memory.autoskills.candidates import autoskill_candidates

    candidates = autoskill_candidates(
        memory_dir=_mem_dir(),
        project_id=project_id or "",
    )
    return {
        "candidates": [
            {
                "skill_name": c.skill_name,
                "rationale": c.rationale,
                "observation_count": len(c.observation_ids),
                "confidence": c.confidence,
            }
            for c in candidates
        ]
    }
