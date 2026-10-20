"""The signed-in researcher's saved Curator selections — what the request dialog offers them.

Read server to server through `curator_bridge` (the DMZ calls into the cluster, as every Medai ↔
cluster conversation does). Counts and status only: the response model is declared field by field,
so not even a future change on Curator's side could pass an accession number through to a browser.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from ... import curator_bridge
from ...crud.datasets import get_dataset
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user
from ..schemas import CuratorSelectionOut, CuratorSelectionsOut

router = APIRouter()

# A mark younger than this may belong to a request still being created (Curator answered, Medai has
# not inserted the row yet), so it is never released here.
ORPHAN_GRACE = timedelta(minutes=2)


def _orphaned(sel: dict, db, now: datetime) -> bool:
    """A mark Curator holds for a dataset Medai never created: a submit whose answer arrived after
    Medai had given up, or a crash between the two. Old enough to be sure, and no such dataset."""
    dataset_id = sel.get("medai_dataset_id")
    if sel.get("status") != "submitted" or not dataset_id:
        return False
    try:
        at = datetime.fromisoformat(str(sel.get("submitted_at")))
    except ValueError:
        return False
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return now - at > ORPHAN_GRACE and get_dataset(db, str(dataset_id)) is None


@router.get("/curator/selections", response_model=CuratorSelectionsOut)
def my_curator_selections(current_user: User = Depends(get_current_user)) -> CuratorSelectionsOut:
    if not curator_bridge.configured():
        raise HTTPException(status_code=404, detail="the link to Curator is not configured")
    if not current_user.email:
        raise HTTPException(
            status_code=409,
            detail="your account has no e-mail address, so your Curator selections cannot be found",
        )
    try:
        answer = curator_bridge.list_selections(current_user.email)
    except curator_bridge.CuratorUnavailable as exc:
        raise HTTPException(status_code=503, detail="Curator could not be reached; try again") from exc
    except curator_bridge.CuratorRefused as exc:
        raise HTTPException(status_code=503, detail="Curator refused Medai's request") from exc
    # Self-healing: a selection stuck as "already requested" with no dataset behind it is released, so
    # the researcher never needs an administrator to unstick it. The retract names the exact dataset id,
    # so it can only ever undo that orphaned hand-off.
    db = get_db_path()
    now = datetime.now(UTC)
    selections = []
    for sel in answer.get("selections") or []:
        if _orphaned(sel, db, now) and curator_bridge.retract_selection(
                str(sel["id"]), current_user.email, str(sel["medai_dataset_id"])):
            sel = {**sel, "status": "pending", "medai_dataset_id": None, "submitted_at": None}
        selections.append(CuratorSelectionOut.model_validate(sel))
    return CuratorSelectionsOut(selections=selections)
