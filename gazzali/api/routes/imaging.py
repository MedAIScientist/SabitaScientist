"""Imaging-data requests as the people involved see them.

Two read-only views over the dataset governance in ``routes/datasets.py``:

* ``GET /projects/{id}/dataset-requests`` — for everyone on the project: where
  each request stands and who has to act next. Metadata only; accession numbers
  are never included (they stay with the owning lab).
* ``GET /imaging/inbox`` — for PIs and admins: the steps waiting on *them*, with
  the reasons a step cannot be taken yet ("blockers"), so nobody clicks Approve
  just to read a 409.

The actions themselves stay on the existing endpoints (pi-approve,
admin-approve, grants, grant approve), which enforce the rules. The blockers
here mirror those rules so the UI can explain them up front.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...crud.datasets import list_datasets, list_grants, list_irb_ids
from ...crud.irb import get_irb
from ...crud.labs import get_lab, list_labs_for_user
from ...crud.labs import get_member_role as get_lab_member_role
from ...crud.projects import get_project
from ...crud.users import get_user_by_id
from ...db import get_db_path
from ...models import Dataset, User
from ..deps import get_current_user, require_project_role

router = APIRouter()

_LAB_PI_ROLES = {"pi", "admin"}
_APPROVED = {"approved", "delivering", "sealed"}
# Delivery comes before project access because that is the order things happen in:
# admin approval pushes the dataset and Curator delivers it whatever its grants are.
# The two run independently, so progress() gives each its own state instead of
# inferring one from the other's position.
_STEPS = [
    ("requested", "Requested"),
    ("pi", "PI approval"),
    ("admin", "Admin approval"),
    ("delivery", "Delivery"),
    ("access", "Project access"),
    ("ready", "Ready"),
]


class Step(BaseModel):
    key: str
    label: str
    state: str  # done | current | todo


class IrbBrief(BaseModel):
    id: str
    title: str
    status: str
    expiry_date: str | None = None


class DatasetRequest(BaseModel):
    id: str
    name: str
    modality: str | None = None
    purpose: str
    status: str
    requested_by: str | None = None
    accession_count: int
    created_at: str
    steps: list[Step]
    waiting_on: str | None = None
    irbs: list[IrbBrief]


class InboxItem(BaseModel):
    action: str  # pi-approve | admin-approve | propose-grant | approve-grant
    dataset_id: str
    dataset_name: str
    modality: str | None = None
    purpose: str
    lab_name: str | None = None
    project_id: str | None = None
    project_name: str | None = None
    requested_by: str | None = None
    accession_count: int
    retention_until: str | None = None
    grant_id: str | None = None
    # Whether the dataset makes viewable images. Annotation (CVAT staging) is refused
    # without them, so the share card can say so before the PI asks for it.
    renders: bool = True
    # The storage reserved so far (the bucket's quota once approved) — the admin's approval card
    # starts from it. None: nothing reserved, and the bucket would have no size limit.
    estimated_bytes: int | None = None
    irbs: list[IrbBrief]
    blockers: list[str]


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _irbs(db, ds: Dataset) -> list[IrbBrief]:
    out = []
    for irb_id in list_irb_ids(db, ds.id):
        irb = get_irb(db, irb_id)
        if irb:
            out.append(IrbBrief(id=irb.id, title=irb.title, status=irb.status, expiry_date=irb.expiry_date))
    return out


def _username(db, user_id: str | None) -> str | None:
    user = get_user_by_id(db, user_id) if user_id else None
    return user.username if user else None


def progress(ds: Dataset, grants: list, project_id: str | None) -> tuple[list[Step], str | None]:
    """Steps from request to "ready for the project", and who has to act next."""
    if ds.status in ("expired", "revoked"):
        return [Step(key=k, label=lbl, state="done" if k == "requested" else "todo") for k, lbl in _STEPS], None
    grant = next((g for g in grants if g.project_id == project_id and g.revoked_at is None), None)
    approved = ds.status in _APPROVED
    sealed = ds.status == "sealed"
    active = grant is not None and grant.admin_approved_at is not None
    state = {
        "requested": "done",
        "pi": "current" if ds.status == "draft" else "done",
        "admin": "todo" if ds.status == "draft" else "current" if ds.status == "pi_approved" else "done",
        "delivery": "done" if sealed else "current" if approved else "todo",
        "access": "done" if active else "current" if approved else "todo",
        "ready": "done" if sealed and active else "todo",
    }
    waiting: list[str] = []
    if ds.status == "draft":
        waiting.append("Lab PI")
    elif ds.status == "pi_approved":
        waiting.append("Platform admin")
    else:
        if not sealed:
            waiting.append("Delivery in progress (PACS → cohort)" if ds.status == "delivering"
                           else "Delivery from PACS")
        if grant is None:
            waiting.append("Lab PI (share with the project)")
        elif not active:
            waiting.append("Platform admin (activate access)")
    steps = [Step(key=k, label=lbl, state=state[k]) for k, lbl in _STEPS]
    return steps, " · ".join(waiting) or None


@router.get("/projects/{project_id}/dataset-requests", response_model=list[DatasetRequest])
def project_dataset_requests(
    project_id: str,
    current_user: User = Depends(require_project_role("owner", "editor", "viewer")),
):
    db = get_db_path()
    out = []
    for ds in list_datasets(db, project_id=project_id):
        steps, waiting = progress(ds, list_grants(db, ds.id), project_id)
        out.append(DatasetRequest(
            id=ds.id, name=ds.name, modality=ds.modality, purpose=ds.purpose, status=ds.status,
            requested_by=_username(db, ds.requested_by), accession_count=len(ds.accession_list or []),
            created_at=ds.created_at, steps=steps, waiting_on=waiting, irbs=_irbs(db, ds),
        ))
    return out


def _irb_blockers(irbs: list[IrbBrief]) -> list[str]:
    if not irbs:
        return ["No IRB approval is linked to this request."]
    blockers = []
    for irb in irbs:
        if irb.status != "approved":
            blockers.append(f"IRB “{irb.title}” is {irb.status}, not approved.")
        elif not irb.expiry_date or irb.expiry_date <= _today():
            blockers.append(f"IRB “{irb.title}” has expired or has no expiry date.")
    return blockers


def _item(db, ds: Dataset, action: str, blockers: list[str], irbs: list[IrbBrief], grant_id: str | None = None,
          project_id: str | None = None) -> InboxItem:
    lab = get_lab(db, ds.lab_id)
    pid = project_id or ds.project_id
    project = get_project(db, pid) if pid else None
    return InboxItem(
        action=action, dataset_id=ds.id, dataset_name=ds.name, modality=ds.modality, purpose=ds.purpose,
        lab_name=lab.name if lab else None, project_id=pid, project_name=project.name if project else None,
        requested_by=_username(db, ds.requested_by), accession_count=len(ds.accession_list or []),
        retention_until=ds.retention_until, grant_id=grant_id, renders=ds.renders, estimated_bytes=ds.estimated_bytes, irbs=irbs, blockers=blockers,
    )


@router.get("/imaging/inbox", response_model=list[InboxItem])
def my_inbox(current_user: User = Depends(get_current_user)):
    """Dataset steps waiting on the caller, under the same rules the actions enforce."""
    db = get_db_path()
    items: list[InboxItem] = []

    pi_labs = [lab.id for lab in list_labs_for_user(db, current_user.id)
               if get_lab_member_role(db, lab.id, current_user.id) in _LAB_PI_ROLES]
    for ds in list_datasets(db, lab_ids=pi_labs):
        irbs = _irbs(db, ds)
        if ds.status == "draft":
            # pi-approve only needs a linked IRB; its validity is checked at the admin step.
            items.append(_item(db, ds, "pi-approve", [] if irbs else ["Link an IRB approval first."], irbs))
        elif ds.status in _APPROVED and ds.project_id and not any(
            g.project_id == ds.project_id and g.revoked_at is None for g in list_grants(db, ds.id)
        ):
            items.append(_item(db, ds, "propose-grant", [], irbs))

    if current_user.is_admin:
        for ds in list_datasets(db, status="pi_approved"):
            if ds.pi_approved_by == current_user.id:
                continue  # a different human must take the admin step
            irbs = _irbs(db, ds)
            items.append(_item(db, ds, "admin-approve", _irb_blockers(irbs), irbs))
        for ds in list_datasets(db):
            for g in list_grants(db, ds.id):
                if g.admin_approved_at is None and g.revoked_at is None and g.granted_by != current_user.id:
                    items.append(_item(db, ds, "approve-grant", [], _irbs(db, ds), grant_id=g.id,
                                       project_id=g.project_id))
    return items
