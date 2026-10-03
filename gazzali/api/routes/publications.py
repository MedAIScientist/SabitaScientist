from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...crud.publications import (
    create_publication,
    create_review,
    create_version,
    delete_publication,
    get_project_name_for_publication,
    get_publication,
    get_version,
    link_experiment,
    list_linked_experiments,
    list_publications,
    list_reviews,
    list_versions,
    unlink_experiment,
    update_publication,
)
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user
from ..schemas import (
    AIDisclosureResponse,
    PublicationCreate,
    PublicationLinkExperimentRequest,
    PublicationResponse,
    PublicationUpdate,
    ReviewCreate,
    ReviewResponse,
    VersionCreate,
    VersionResponse,
)

router = APIRouter()


def _pub_to_response(pub) -> PublicationResponse:
    db = get_db_path()
    project_name = get_project_name_for_publication(db, pub.project_id)
    linked_experiments = list_linked_experiments(db, pub.id) if pub.id else []
    return PublicationResponse(
        id=pub.id,
        project_id=pub.project_id,
        project_name=project_name,
        title=pub.title,
        venue=pub.venue,
        venue_type=pub.venue_type,
        authors=pub.authors,
        status=pub.status,
        doi=pub.doi,
        url=pub.url,
        abstract=pub.abstract,
        submitted_at=pub.submitted_at,
        accepted_at=pub.accepted_at,
        published_at=pub.published_at,
        reporting_guideline=pub.reporting_guideline,
        data_availability=pub.data_availability,
        code_availability=pub.code_availability,
        conflict_of_interest=pub.conflict_of_interest,
        funding_statement=pub.funding_statement,
        created_by=pub.created_by,
        created_at=pub.created_at,
        updated_at=pub.updated_at,
        linked_experiments=linked_experiments,
    )


@router.get("", response_model=list[PublicationResponse])
def list_all_publications(
    current_user: User = Depends(get_current_user),
    project_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    db = get_db_path()
    return [_pub_to_response(p) for p in list_publications(db, project_id=project_id, status=status)]


@router.post("", response_model=PublicationResponse, status_code=status.HTTP_201_CREATED)
def create_new_publication(
    body: PublicationCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    pub = create_publication(
        db,
        title=body.title,
        created_by=current_user.id,
        project_id=body.project_id,
        venue=body.venue,
        venue_type=body.venue_type,
        authors=body.authors,
        abstract=body.abstract,
        doi=body.doi,
        url=body.url,
    )
    return _pub_to_response(pub)


@router.get("/{pub_id}", response_model=PublicationResponse)
def get_publication_detail(
    pub_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(status_code=404, detail="Publication not found")
    return _pub_to_response(pub)


@router.put("/{pub_id}", response_model=PublicationResponse)
def update_existing_publication(
    pub_id: str,
    body: PublicationUpdate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    data = body.model_dump(exclude_none=True)
    pub = update_publication(db, pub_id, **data)
    if pub is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    return _pub_to_response(pub)


@router.post("/{pub_id}/submit", response_model=PublicationResponse)
def submit_publication(
    pub_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    pub = update_publication(db, pub_id, status="submitted", submitted_at=datetime.now(UTC).isoformat())
    if pub is None:
        raise HTTPException(status_code=404, detail="Publication not found")
    return _pub_to_response(pub)


@router.post("/{pub_id}/link-experiment", response_model=PublicationResponse)
def link_experiment_to_publication(
    pub_id: str,
    body: PublicationLinkExperimentRequest,
    current_user: User = Depends(get_current_user),
):
    """Link an experiment to this publication (experiment contributed to this paper)."""
    db = get_db_path()
    link_experiment(db, pub_id, body.experiment_id, body.section)
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(404, "Publication not found")
    return _pub_to_response(pub)


@router.delete("/{pub_id}/link-experiment/{experiment_id}", response_model=PublicationResponse)
def unlink_experiment_from_publication(
    pub_id: str,
    experiment_id: str,
    current_user: User = Depends(get_current_user),
):
    """Remove an experiment-publication link."""
    db = get_db_path()
    unlink_experiment(db, pub_id, experiment_id)
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(404, "Publication not found")
    return _pub_to_response(pub)


@router.get("/{pub_id}/pipeline")
def get_publication_pipeline(
    pub_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return the full publication pipeline: project → experiments → tasks → publication status."""
    db = get_db_path()
    pub = get_publication(db, pub_id)
    if not pub:
        raise HTTPException(404, "Publication not found")

    from ...crud.experiments import get_experiment
    from ...crud.projects import get_project

    project = get_project(db, pub.project_id) if pub.project_id else None
    linked_exps = list_linked_experiments(db, pub_id)

    experiments_detail = []
    for le in linked_exps:
        exp = get_experiment(db, le["experiment_id"])
        if exp:
            from ...crud.experiment_entries import list_entries
            entries = list_entries(db, exp.id)
            experiments_detail.append({
                "experiment_id": exp.id,
                "name": exp.name,
                "status": exp.status,
                "hypothesis": exp.hypothesis,
                "section": le.get("section"),
                "entry_count": len(entries),
            })

    pipeline_stages = [
        {"stage": "project", "status": "done" if project else "none",
         "name": project.name if project else "—", "id": pub.project_id},
        {"stage": "experiments", "status": "done" if linked_exps else "pending",
         "count": len(linked_exps)},
        {"stage": "draft", "status": "done" if pub.status != "draft" else "active",
         "date": pub.created_at},
        {"stage": "submitted", "status": pub.status if pub.status in ("submitted", "reviewing", "accepted", "published") else "pending",
         "date": pub.submitted_at},
        {"stage": "review", "status": pub.status if pub.status in ("reviewing", "accepted", "published") else "pending",
         "reviews": len(list_reviews(db, pub_id))},
        {"stage": "accepted", "status": "done" if pub.status in ("accepted", "published") else "pending",
         "date": pub.accepted_at},
        {"stage": "published", "status": "done" if pub.status == "published" else "pending",
         "date": pub.published_at},
    ]

    return {
        "publication_id": pub_id,
        "title": pub.title,
        "status": pub.status,
        "project": {"id": project.id, "name": project.name, "description": project.description} if project else None,
        "linked_experiments": experiments_detail,
        "pipeline_stages": pipeline_stages,
    }


@router.delete("/{pub_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_publication(
    pub_id: str,
    current_user: User = Depends(get_current_user),
):
    delete_publication(get_db_path(), pub_id)


# ── Versions ────────────────────────────────────────────────────────────────────

@router.get("/{pub_id}/versions", response_model=list[VersionResponse])
def list_publication_versions(
    pub_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    return [_version_to_response(v) for v in list_versions(db, pub_id)]


def _version_to_response(v, include_content: bool = False) -> VersionResponse:
    return VersionResponse(
        id=v.id, publication_id=v.publication_id,
        version=v.version, file_path=v.file_path,
        notes=v.notes, created_by=v.created_by,
        created_at=v.created_at,
        section=v.section, generated_by=v.generated_by,
        model=v.model, prompt_hash=v.prompt_hash, verification=v.verification,
        content_length=len(v.content or ""),
        content=v.content if include_content else None,
    )


@router.post("/{pub_id}/versions", response_model=VersionResponse, status_code=status.HTTP_201_CREATED)
def create_publication_version(
    pub_id: str,
    body: VersionCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    v = create_version(
        db, pub_id, created_by=current_user.id, notes=body.notes,
        content=body.content, section=body.section, generated_by="human",
    )
    return _version_to_response(v, include_content=True)


@router.get("/{pub_id}/versions/{version_id}", response_model=VersionResponse)
def get_publication_version(
    pub_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
):
    """Return one version including its full draft text."""
    version = get_version(get_db_path(), version_id)
    if not version or version.publication_id != pub_id:
        raise HTTPException(404, "Version not found")
    return _version_to_response(version, include_content=True)


@router.post("/{pub_id}/versions/{version_id}/restore")
def restore_publication_version(
    pub_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user),
):
    """Restore a previous version by copying its text into a new version."""
    pub = get_publication(get_db_path(), pub_id)
    if not pub:
        raise HTTPException(404, "Publication not found")
    target = get_version(get_db_path(), version_id)
    if not target or target.publication_id != pub_id:
        raise HTTPException(404, "Version not found")
    # Carry the text forward — a restore that copies only the note restores nothing.
    v = create_version(
        get_db_path(), pub_id, created_by=current_user.id,
        notes=f"Restored from version {target.version} ({target.id}): {target.notes or 'no notes'}",
        content=target.content,
        section=target.section,
        file_path=target.file_path,
        generated_by=target.generated_by,
        model=target.model,
        prompt_hash=target.prompt_hash,
    )
    return {
        "status": "restored",
        "new_version_id": v.id,
        "new_version": v.version,
        "restored_from_version": target.version,
    }


@router.get("/{pub_id}/ai-disclosure", response_model=AIDisclosureResponse)
def get_ai_disclosure(
    pub_id: str,
    current_user: User = Depends(get_current_user),
):
    """Build an AI-use disclosure statement from the recorded version history.

    The statement is derived from what was actually generated, never asserted.
    If no AI versions exist it says so rather than producing boilerplate.
    """
    pub = get_publication(get_db_path(), pub_id)
    if not pub:
        raise HTTPException(404, "Publication not found")

    versions = list_versions(get_db_path(), pub_id)
    ai_versions = [v for v in versions if (v.generated_by or "").startswith("ai")]
    models = sorted({v.model for v in ai_versions if v.model})
    sections = sorted({v.section for v in ai_versions if v.section})

    if not ai_versions:
        statement = (
            "No AI-assisted drafting was recorded for this manuscript in the "
            "project management system."
        )
    else:
        model_phrase = ", ".join(models) if models else "an unrecorded language model"
        section_phrase = (
            f" The assisted sections were: {', '.join(sections)}." if sections else ""
        )
        statement = (
            f"Portions of this manuscript were drafted with AI assistance using "
            f"{model_phrase}. AI assistance was used across {len(ai_versions)} recorded "
            f"draft version(s).{section_phrase} All AI-generated text was reviewed and "
            f"edited by the authors, who take full responsibility for the content."
        )

    return AIDisclosureResponse(
        publication_id=pub_id,
        statement=statement,
        ai_version_count=len(ai_versions),
        human_version_count=len(versions) - len(ai_versions),
        models_used=models,
        sections=sections,
    )


# ── Reviews ─────────────────────────────────────────────────────────────────────

@router.get("/{pub_id}/reviews", response_model=list[ReviewResponse])
def list_publication_reviews(
    pub_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    return [
        ReviewResponse(
            id=r.id, publication_id=r.publication_id,
            reviewer_name=r.reviewer_name, comments=r.comments,
            decision=r.decision, round=r.round, created_at=r.created_at,
        )
        for r in list_reviews(db, pub_id)
    ]


@router.post("/{pub_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_publication_review(
    pub_id: str,
    body: ReviewCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    r = create_review(
        db, pub_id,
        round=body.round,
        reviewer_name=body.reviewer_name,
        comments=body.comments,
        decision=body.decision,
    )
    return ReviewResponse(
        id=r.id, publication_id=r.publication_id,
        reviewer_name=r.reviewer_name, comments=r.comments,
        decision=r.decision, round=r.round, created_at=r.created_at,
    )
