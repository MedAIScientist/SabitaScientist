"""Grant management routes."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ...crud.grant_budget import (
    create_budget_item,
    delete_budget_item,
    get_budget_item,
    list_budget_items,
    update_budget_item,
)
from ...crud.grant_members import (
    add_member,
    get_member,
    list_members,
    remove_member,
    update_member,
)
from ...crud.grant_milestones import (
    create_milestone,
    delete_milestone,
    get_milestone,
    list_milestones,
    update_milestone,
)
from ...crud.grant_stats import summarize as summarize_grants
from ...crud.grants import (
    DEFAULT_SORT,
    create_grant,
    delete_grant,
    get_grant,
    list_grants,
    update_grant,
)
from ...crud.labs import get_lab
from ...crud.labs import get_member_role as get_lab_member_role
from ...crud.projects import get_member_role as get_project_member_role
from ...crud.projects import get_project
from ...crud.users import get_user_by_id
from ...db import get_db_path
from ...models import User
from ..audit_helper import log_action
from ..deps import get_current_user
from ..schemas import (
    GrantBudgetItemCreate,
    GrantBudgetItemResponse,
    GrantBudgetItemUpdate,
    GrantCreate,
    GrantMemberCreate,
    GrantMemberResponse,
    GrantMemberUpdate,
    GrantMilestoneCreate,
    GrantMilestoneResponse,
    GrantMilestoneUpdate,
    GrantResponse,
    GrantStatsResponse,
    GrantUpdate,
)

router = APIRouter()


def _grant_response(g, current_user: User, db) -> GrantResponse:
    """Project a Grant row onto the wire format (one place, not five)."""
    return GrantResponse(
        id=g.id,
        title=g.title,
        funder=g.funder,
        amount_requested=g.amount_requested,
        amount_awarded=g.amount_awarded,
        currency=g.currency,
        status=g.status,
        submitted_at=g.submitted_at,
        awarded_at=g.awarded_at,
        start_date=g.start_date,
        end_date=g.end_date,
        description=g.description,
        pi_id=g.pi_id,
        pi_username=g.pi_username,
        project_id=g.project_id,
        lab_id=g.lab_id,
        created_by=g.created_by,
        created_at=g.created_at,
        updated_at=g.updated_at,
        can_manage=_may_write_grant(current_user, g, db),
    )


# Lab roles that may change a grant belonging to that lab, and project roles that
# may change a grant belonging to that project. Reading is open to every role.
_LAB_WRITE_ROLES = ("pi", "admin")
_PROJECT_WRITE_ROLES = ("owner", "editor")

# The visibility filter runs per row in Python, so the list route reads a bounded
# window of the matching grants and paginates what survives it. Well above any
# real grants table here, and it keeps the per-row role lookups bounded.
_VISIBILITY_SCAN_LIMIT = 2000

_WRITE_DENIED = (
    "grant write access requires the lab 'pi'/'admin', "
    "the project 'owner'/'editor', or a platform admin"
)


def _is_grant_owner(user: User, grant_or_body) -> bool:
    """The grant's named PI, or the person who filed it.

    A GrantCreate body carries no created_by yet — whoever is posting it is about
    to become it — so a body counts as owned by the caller.
    """
    return user.id == grant_or_body.pi_id or user.id == getattr(
        grant_or_body, "created_by", user.id
    )


def _may_read_grant(user: User, grant, db) -> bool:
    """Whether the caller may see a grant at all.

    A grant carries funder and money, so it stays inside the group it belongs to:
    a platform admin, any member of its lab, anyone on its project team, or its
    own PI/creator.
    """
    if user.is_admin or _is_grant_owner(user, grant):
        return True
    if grant.lab_id and get_lab_member_role(db, grant.lab_id, user.id) is not None:
        return True
    if (
        grant.project_id
        and get_project_member_role(db, grant.project_id, user.id) is not None
    ):
        return True
    return False


def _may_write_grant(user: User, grant_or_body, db) -> bool:
    """Whether the caller may create/change/delete a grant.

    Reading a lab's grant takes any lab role; changing one takes 'pi'/'admin' —
    the same pair that already governs the lab itself. A grant attached to
    neither a lab nor a project has no group to answer to, so only its PI/creator
    (or a platform admin) can touch it.
    """
    if user.is_admin:
        return True
    lab_id = grant_or_body.lab_id
    project_id = grant_or_body.project_id
    if lab_id and get_lab_member_role(db, lab_id, user.id) in _LAB_WRITE_ROLES:
        return True
    if (
        project_id
        and get_project_member_role(db, project_id, user.id) in _PROJECT_WRITE_ROLES
    ):
        return True
    if not lab_id and not project_id:
        return _is_grant_owner(user, grant_or_body)
    return False


def _load_readable_grant(db, gid: str, current_user: User):
    """Fetch a grant the caller may see, 404 otherwise.

    A grant somebody may not see answers exactly like a grant that does not
    exist, so /grants/{gid} cannot be used to enumerate other groups' grants —
    the same deliberate existence-hiding require_project_role() does.
    """
    g = get_grant(db, gid)
    if not g or not _may_read_grant(current_user, g, db):
        raise HTTPException(status_code=404, detail="Grant not found")
    return g


def _require_grant_write(current_user: User, grant_or_body, db) -> None:
    """403 on a grant the caller may see but may not change."""
    if not _may_write_grant(current_user, grant_or_body, db):
        raise HTTPException(status_code=403, detail=_WRITE_DENIED)


@router.get("", response_model=list[GrantResponse])
def list_all_grants(
    current_user: User = Depends(get_current_user),
    lab_id: str | None = Query(None),
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    q: str | None = Query(None, max_length=200),
    sort: str = Query(DEFAULT_SORT),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_db_path()
    if (
        lab_id
        and not current_user.is_admin
        and get_lab_member_role(db, lab_id, current_user.id) is None
    ):
        # An explicit ask for one lab's grants earns an explicit refusal, rather
        # than an empty page that reads like "this lab has no grants". Labs are
        # listable by any authenticated user anyway, so a 403 here leaks nothing
        # — the same reasoning require_lab_role() uses. An unpermitted project_id
        # stays silent instead, because project existence is deliberately hidden.
        raise HTTPException(
            status_code=403, detail="lab membership required (any role)"
        )
    # Filter first, paginate second: offset/limit walk the grants this caller may
    # actually see, so page 1 is not mostly other groups' grants withheld.
    visible = [
        g
        for g in list_grants(
            db, lab_id, project_id, status, 0, _VISIBILITY_SCAN_LIMIT, q=q, sort=sort
        )
        if _may_read_grant(current_user, g, db)
    ]
    return [
        _grant_response(g, current_user, db) for g in visible[offset : offset + limit]
    ]


@router.get("/stats", response_model=GrantStatsResponse)
def grant_stats(
    current_user: User = Depends(get_current_user),
    lab_id: str | None = Query(None),
    project_id: str | None = Query(None),
):
    """Dashboard counters over exactly the grants the caller may see.

    Declared before /{gid} so that "stats" is not swallowed by the id path param.
    """
    db = get_db_path()
    if (
        lab_id
        and not current_user.is_admin
        and get_lab_member_role(db, lab_id, current_user.id) is None
    ):
        raise HTTPException(
            status_code=403, detail="lab membership required (any role)"
        )
    visible = [
        g
        for g in list_grants(db, lab_id, project_id, None, 0, _VISIBILITY_SCAN_LIMIT)
        if _may_read_grant(current_user, g, db)
    ]
    return GrantStatsResponse(**summarize_grants(db, visible))


@router.post("", response_model=GrantResponse, status_code=status.HTTP_201_CREATED)
def create_new_grant(
    request: Request,
    body: GrantCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    # grants.lab_id/project_id are ON DELETE SET NULL, not validated on insert, so
    # an unknown id would silently produce an orphan grant nobody can govern.
    if body.lab_id and not get_lab(db, body.lab_id):
        raise HTTPException(status_code=400, detail="Lab not found")
    if body.project_id and not get_project(db, body.project_id):
        raise HTTPException(status_code=400, detail="Project not found")
    _require_grant_write(current_user, body, db)
    g = create_grant(
        db,
        title=body.title,
        funder=body.funder,
        created_by=current_user.id,
        lab_id=body.lab_id,
        project_id=body.project_id,
        amount_requested=body.amount_requested,
        amount_awarded=body.amount_awarded,
        currency=body.currency,
        status=body.status,
        submitted_at=body.submitted_at,
        awarded_at=body.awarded_at,
        start_date=body.start_date,
        end_date=body.end_date,
        description=body.description,
        pi_id=body.pi_id,
    )
    log_action(request, current_user, "create", "grant", g.id, f"title={g.title}")
    return _grant_response(g, current_user, db)


@router.get("/{gid}", response_model=GrantResponse)
def get_grant_detail(
    gid: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    g = _load_readable_grant(db, gid, current_user)
    return _grant_response(g, current_user, db)


@router.put("/{gid}", response_model=GrantResponse)
def update_existing_grant(
    request: Request,
    gid: str,
    body: GrantUpdate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    existing = _load_readable_grant(db, gid, current_user)
    _require_grant_write(current_user, existing, db)
    # Re-targeting is a write against the destination too, so an unattached grant
    # cannot be pushed into a lab or project the caller has no say in.
    if (body.lab_id and body.lab_id != existing.lab_id) or (
        body.project_id and body.project_id != existing.project_id
    ):
        if body.lab_id and not get_lab(db, body.lab_id):
            raise HTTPException(status_code=400, detail="Lab not found")
        if body.project_id and not get_project(db, body.project_id):
            raise HTTPException(status_code=400, detail="Project not found")
        _require_grant_write(current_user, body, db)
    g = update_grant(
        db,
        gid,
        title=body.title,
        funder=body.funder,
        amount_requested=body.amount_requested,
        amount_awarded=body.amount_awarded,
        currency=body.currency,
        status=body.status,
        submitted_at=body.submitted_at,
        awarded_at=body.awarded_at,
        start_date=body.start_date,
        end_date=body.end_date,
        description=body.description,
        pi_id=body.pi_id,
        lab_id=body.lab_id,
        project_id=body.project_id,
    )
    if not g:
        raise HTTPException(status_code=404, detail="Grant not found")
    log_action(request, current_user, "update", "grant", gid, f"title={g.title}")
    return _grant_response(g, current_user, db)


@router.delete("/{gid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_grant(
    request: Request,
    gid: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    # An unknown gid now answers 404 like an invisible one: a grant the caller may
    # not see has to be indistinguishable from a grant that is not there.
    g = _load_readable_grant(db, gid, current_user)
    _require_grant_write(current_user, g, db)
    log_action(request, current_user, "delete", "grant", gid, f"title={g.title}")
    delete_grant(db, gid)


# ── Budget lines ──────────────────────────────────────────────────────────────


def _budget_response(item) -> GrantBudgetItemResponse:
    return GrantBudgetItemResponse(
        id=item.id,
        grant_id=item.grant_id,
        category=item.category,
        description=item.description,
        planned_amount=item.planned_amount,
        spent_amount=item.spent_amount,
        position=item.position,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _milestone_response(m) -> GrantMilestoneResponse:
    return GrantMilestoneResponse(
        id=m.id,
        grant_id=m.grant_id,
        title=m.title,
        kind=m.kind,
        due_date=m.due_date,
        completed_at=m.completed_at,
        owner_id=m.owner_id,
        notes=m.notes,
        position=m.position,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _member_response(m) -> GrantMemberResponse:
    return GrantMemberResponse(
        id=m.id,
        grant_id=m.grant_id,
        user_id=m.user_id,
        username=m.username,
        role=m.role,
        share_percent=m.share_percent,
        added_at=m.added_at,
    )


@router.get("/{gid}/budget", response_model=list[GrantBudgetItemResponse])
def list_grant_budget(gid: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    _load_readable_grant(db, gid, current_user)
    return [_budget_response(i) for i in list_budget_items(db, gid)]


@router.post(
    "/{gid}/budget",
    response_model=GrantBudgetItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_grant_budget_item(
    request: Request,
    gid: str,
    body: GrantBudgetItemCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    g = _load_readable_grant(db, gid, current_user)
    _require_grant_write(current_user, g, db)
    item = create_budget_item(
        db,
        gid,
        category=body.category,
        description=body.description,
        planned_amount=body.planned_amount,
        spent_amount=body.spent_amount,
        position=body.position,
    )
    log_action(
        request, current_user, "create", "grant_budget_item", item.id, f"grant={gid}"
    )
    return _budget_response(item)


@router.put("/{gid}/budget/{item_id}", response_model=GrantBudgetItemResponse)
def update_grant_budget_item(
    request: Request,
    gid: str,
    item_id: str,
    body: GrantBudgetItemUpdate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    g = _load_readable_grant(db, gid, current_user)
    _require_grant_write(current_user, g, db)
    item = get_budget_item(db, item_id)
    # A line id from another grant must not be reachable through this grant's URL.
    if not item or item.grant_id != gid:
        raise HTTPException(status_code=404, detail="Budget item not found")
    updated = update_budget_item(db, item_id, body.model_dump(exclude_unset=True))
    log_action(
        request, current_user, "update", "grant_budget_item", item_id, f"grant={gid}"
    )
    return _budget_response(updated)


@router.delete("/{gid}/budget/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grant_budget_item(
    request: Request,
    gid: str,
    item_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    g = _load_readable_grant(db, gid, current_user)
    _require_grant_write(current_user, g, db)
    item = get_budget_item(db, item_id)
    if not item or item.grant_id != gid:
        raise HTTPException(status_code=404, detail="Budget item not found")
    log_action(
        request, current_user, "delete", "grant_budget_item", item_id, f"grant={gid}"
    )
    delete_budget_item(db, item_id)


# ── Milestones, reports and deliverables ──────────────────────────────────────


@router.get("/{gid}/milestones", response_model=list[GrantMilestoneResponse])
def list_grant_milestones(gid: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    _load_readable_grant(db, gid, current_user)
    return [_milestone_response(m) for m in list_milestones(db, gid)]


@router.post(
    "/{gid}/milestones",
    response_model=GrantMilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_grant_milestone(
    request: Request,
    gid: str,
    body: GrantMilestoneCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    g = _load_readable_grant(db, gid, current_user)
    _require_grant_write(current_user, g, db)
    # owner_id is ON DELETE SET NULL with no insert-time check, so an unknown id
    # would quietly create an unowned milestone.
    if body.owner_id and not get_user_by_id(db, body.owner_id):
        raise HTTPException(status_code=400, detail="Owner not found")
    m = create_milestone(
        db,
        gid,
        title=body.title,
        kind=body.kind,
        due_date=body.due_date,
        owner_id=body.owner_id,
        notes=body.notes,
        position=body.position,
    )
    log_action(request, current_user, "create", "grant_milestone", m.id, f"grant={gid}")
    return _milestone_response(m)


@router.put("/{gid}/milestones/{mid}", response_model=GrantMilestoneResponse)
def update_grant_milestone(
    request: Request,
    gid: str,
    mid: str,
    body: GrantMilestoneUpdate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    g = _load_readable_grant(db, gid, current_user)
    _require_grant_write(current_user, g, db)
    existing = get_milestone(db, mid)
    if not existing or existing.grant_id != gid:
        raise HTTPException(status_code=404, detail="Milestone not found")
    fields = body.model_dump(exclude_unset=True)
    # 'completed' is sugar over completed_at and wins if both are sent.
    if "completed" in fields:
        completed = fields.pop("completed")
        fields["completed_at"] = datetime.now(UTC).isoformat() if completed else None
    if fields.get("owner_id") and not get_user_by_id(db, fields["owner_id"]):
        raise HTTPException(status_code=400, detail="Owner not found")
    updated = update_milestone(db, mid, fields)
    log_action(request, current_user, "update", "grant_milestone", mid, f"grant={gid}")
    return _milestone_response(updated)


@router.delete("/{gid}/milestones/{mid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grant_milestone(
    request: Request,
    gid: str,
    mid: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    g = _load_readable_grant(db, gid, current_user)
    _require_grant_write(current_user, g, db)
    existing = get_milestone(db, mid)
    if not existing or existing.grant_id != gid:
        raise HTTPException(status_code=404, detail="Milestone not found")
    log_action(request, current_user, "delete", "grant_milestone", mid, f"grant={gid}")
    delete_milestone(db, mid)


# ── Team ──────────────────────────────────────────────────────────────────────


@router.get("/{gid}/members", response_model=list[GrantMemberResponse])
def list_grant_members(gid: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    _load_readable_grant(db, gid, current_user)
    return [_member_response(m) for m in list_members(db, gid)]


@router.post(
    "/{gid}/members",
    response_model=GrantMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_grant_member(
    request: Request,
    gid: str,
    body: GrantMemberCreate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    g = _load_readable_grant(db, gid, current_user)
    _require_grant_write(current_user, g, db)
    if not get_user_by_id(db, body.user_id):
        raise HTTPException(status_code=400, detail="User not found")
    try:
        member = add_member(
            db, gid, body.user_id, role=body.role, share_percent=body.share_percent
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="User is already on this grant team"
        ) from exc
    log_action(
        request, current_user, "create", "grant_member", member.id, f"grant={gid}"
    )
    return _member_response(get_member(db, member.id))


@router.put("/{gid}/members/{member_id}", response_model=GrantMemberResponse)
def update_grant_member(
    request: Request,
    gid: str,
    member_id: str,
    body: GrantMemberUpdate,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    g = _load_readable_grant(db, gid, current_user)
    _require_grant_write(current_user, g, db)
    existing = get_member(db, member_id)
    if not existing or existing.grant_id != gid:
        raise HTTPException(status_code=404, detail="Team member not found")
    updated = update_member(db, member_id, body.model_dump(exclude_unset=True))
    log_action(
        request, current_user, "update", "grant_member", member_id, f"grant={gid}"
    )
    return _member_response(updated)


@router.delete("/{gid}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_grant_member(
    request: Request,
    gid: str,
    member_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    g = _load_readable_grant(db, gid, current_user)
    _require_grant_write(current_user, g, db)
    existing = get_member(db, member_id)
    if not existing or existing.grant_id != gid:
        raise HTTPException(status_code=404, detail="Team member not found")
    log_action(
        request, current_user, "delete", "grant_member", member_id, f"grant={gid}"
    )
    remove_member(db, member_id)
