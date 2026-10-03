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
_STEPS = [
    ("requested", "Requested"),
    ("pi", "PI approval"),
    ("admin", "Admin approval"),
    ("access", "Project access"),
    ("delivery", "Delivery"),
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
    if ds.status == "draft":
        current, waiting = "pi", "Lab PI"
    elif ds.status == "pi_approved":
        current, waiting = "admin", "Platform admin"
    elif grant is None:
        current, waiting = "access", "Lab PI (share with the project)"
    elif grant.admin_approved_at is None:
        current, waiting = "access", "Platform admin (activate access)"
    elif ds.status in ("approved", "delivering"):
        current, waiting = "delivery", "Delivery from PACS"
    else:  # sealed and granted
        current, waiting = None, None
    keys = [k for k, _ in _STEPS]
    at = keys.index(current) if current else len(keys)
    steps = [Step(key=k, label=lbl, state="done" if i < at else "current" if i == at else "todo")
             for i, (k, lbl) in enumerate(_STEPS)]
    if current is None:
        steps[-1] = Step(key="ready", label="Ready", state="done")
    return steps, waiting


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
        retention_until=ds.retention_until, grant_id=grant_id, irbs=irbs, blockers=blockers,
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
