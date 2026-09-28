"""Imaging dataset governance: /api/v1/datasets.

The approval chain is TWO DISTINCT HUMANS by construction:

  draft ──(lab PI: pi-approve)──> pi_approved ──(platform admin: admin-approve)──> approved

* The PI leg accepts only a real lab role ('pi'/'admin' in the OWNING lab) — a
  platform admin does NOT satisfy it unless they also hold that lab role. This
  is the one place the platform-admin superuser rule is deliberately suspended:
  PHI release accountability belongs to the lab.
* The admin leg requires ``is_admin`` AND a different human than the PI leg, so
  one person can never walk a cohort out alone — even an admin who is also PI.
* The admin leg refuses unless every linked IRB is status 'approved' with an
  unexpired expiry_date, and a retention date is set.

Grants extend a dataset to a project (which may be lab-less) under the same two
legs: the owning lab's PI proposes, a different platform admin activates. Every
transition pushes the desired grant state to platform-control (fire-and-forget;
the push module and the hourly reconcile own retries).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from ...crud.datasets import (
    approve_grant,
    create_dataset,
    create_grant,
    get_dataset,
    get_grant,
    link_irb,
    list_datasets,
    list_grants,
    list_irb_ids,
    revoke_grant,
    update_dataset,
)
from ...crud.irb import get_irb
from ...crud.labs import get_lab, get_member_role as get_lab_member_role
from ...crud.labs import list_labs_for_user
from ...crud.projects import get_project
from ...db import get_db_path
from ...models import Dataset, User
from ...platform_push import push_dataset
from ..audit_helper import log_action
from ..deps import get_current_user, require_admin
from ..schemas import (
    DatasetCreate,
    DatasetGrantCreate,
    DatasetGrantResponse,
    DatasetResponse,
    DatasetTransition,
)

router = APIRouter()

_LAB_PI_ROLES = {"pi", "admin"}
_TERMINAL = {"expired", "revoked"}


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _require_owning_pi(db, dataset: Dataset, user: User) -> None:
    """The PI leg: a real 'pi'/'admin' role in the OWNING lab. No admin bypass —
    see the module docstring for why the superuser rule stops here."""
    role = get_lab_member_role(db, dataset.lab_id, user.id)
    if role not in _LAB_PI_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="the owning lab's PI must act here (lab role 'pi'/'admin'; "
            "platform admin does not substitute)",
        )


def _may_view(db, dataset: Dataset, user: User) -> bool:
    if user.is_admin:
        return True
    return get_lab_member_role(db, dataset.lab_id, user.id) is not None


def _grant_resp(g) -> DatasetGrantResponse:
    return DatasetGrantResponse(
        id=g.id,
        dataset_id=g.dataset_id,
        project_id=g.project_id,
        granted_by=g.granted_by,
        admin_approved_by=g.admin_approved_by,
        admin_approved_at=g.admin_approved_at,
        granted_at=g.granted_at,
        expires_at=g.expires_at,
        revoked_at=g.revoked_at,
        revoked_by=g.revoked_by,
        active=g.admin_approved_at is not None and g.revoked_at is None,
        cvat_project_id=g.cvat_project_id,
        task_size=g.task_size,
    )


def _dataset_resp(db, ds: Dataset) -> DatasetResponse:
    return DatasetResponse(
        id=ds.id,
        name=ds.name,
        purpose=ds.purpose,
        lab_id=ds.lab_id,
        requested_by=ds.requested_by,
        modality=ds.modality,
        accession_list=ds.accession_list or [],
        estimated_bytes=ds.estimated_bytes,
        status=ds.status,
        pi_approved_by=ds.pi_approved_by,
        pi_approved_at=ds.pi_approved_at,
        admin_approved_by=ds.admin_approved_by,
        admin_approved_at=ds.admin_approved_at,
        retention_until=ds.retention_until,
        bucket=ds.bucket,
        renders=ds.renders,
        sealed_at=ds.sealed_at,
        content_root_sha256=ds.content_root_sha256,
        generation=ds.generation,
        created_at=ds.created_at,
        updated_at=ds.updated_at,
        irb_ids=list_irb_ids(db, ds.id),
        grants=[_grant_resp(g) for g in list_grants(db, ds.id)],
    )


def _load_visible(db, dataset_id: str, user: User) -> Dataset:
    ds = get_dataset(db, dataset_id)
    if not ds or not _may_view(db, ds, user):
        raise HTTPException(status_code=404, detail="Dataset not found")
    return ds


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def create_new(
    request: Request,
    body: DatasetCreate,
    current_user: User = Depends(get_current_user),
):
    """Draft a dataset. Any member of the owning lab (or a platform admin) may
    draft; the approval legs are where authority is enforced."""
    db = get_db_path()
    if not get_lab(db, body.lab_id):
        raise HTTPException(status_code=400, detail="lab does not exist")
    if not current_user.is_admin and get_lab_member_role(
        db, body.lab_id, current_user.id
    ) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="lab membership required (any role)",
        )
    for irb_id in body.irb_ids:
        if not get_irb(db, irb_id):
            raise HTTPException(status_code=400, detail=f"IRB {irb_id} does not exist")
    if not body.accession_list:
        raise HTTPException(
            status_code=400, detail="a dataset names at least one accession"
        )
    ds = create_dataset(
        db,
        name=body.name,
        purpose=body.purpose,
        lab_id=body.lab_id,
        requested_by=current_user.id,
        modality=body.modality,
        accession_list=body.accession_list,
        estimated_bytes=body.estimated_bytes,
        renders=body.renders,
    )
    for irb_id in body.irb_ids:
        link_irb(db, ds.id, irb_id)
    log_action(request, current_user, "create", "dataset", ds.id, f"name={ds.name}")
    return _dataset_resp(db, ds)


@router.get("", response_model=list[DatasetResponse])
def list_all(
    current_user: User = Depends(get_current_user),
    lab_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
):
    db = get_db_path()
    if current_user.is_admin:
        lab_ids = [lab_id] if lab_id else None
    else:
        member_of = [lab.id for lab in list_labs_for_user(db, current_user.id)]
        lab_ids = [lab_id] if lab_id and lab_id in member_of else member_of
    return [
        _dataset_resp(db, ds)
        for ds in list_datasets(db, lab_ids=lab_ids, status=status_filter)
    ]


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_detail(dataset_id: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    return _dataset_resp(db, _load_visible(db, dataset_id, current_user))


@router.post("/{dataset_id}/pi-approve", response_model=DatasetResponse)
def pi_approve(
    request: Request,
    dataset_id: str,
    current_user: User = Depends(get_current_user),
):
    db = get_db_path()
    ds = _load_visible(db, dataset_id, current_user)
    _require_owning_pi(db, ds, current_user)
    if ds.status != "draft":
        raise HTTPException(
            status_code=409, detail=f"only a draft can be PI-approved (is: {ds.status})"
        )
    if not list_irb_ids(db, ds.id):
        raise HTTPException(
            status_code=409, detail="link at least one IRB before approval"
        )
    now = datetime.now(UTC).isoformat()
    ds = update_dataset(
        db,
        ds.id,
        status="pi_approved",
        pi_approved_by=current_user.id,
        pi_approved_at=now,
    )
    log_action(request, current_user, "pi-approve", "dataset", ds.id, f"name={ds.name}")
    return _dataset_resp(db, ds)


@router.post("/{dataset_id}/admin-approve", response_model=DatasetResponse)
def admin_approve(
    request: Request,
    dataset_id: str,
    body: DatasetTransition,
    current_user: User = Depends(require_admin),
):
    db = get_db_path()
    ds = get_dataset(db, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if ds.status != "pi_approved":
        raise HTTPException(
            status_code=409,
            detail=f"only a PI-approved dataset can be admin-approved (is: {ds.status})",
        )
    if ds.pi_approved_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="the admin approver must be a different human than the PI approver",
        )
    for irb_id in list_irb_ids(db, ds.id):
        irb = get_irb(db, irb_id)
        if not irb or irb.status != "approved":
            raise HTTPException(
                status_code=409, detail=f"IRB {irb_id} is not in status 'approved'"
            )
        if not irb.expiry_date or irb.expiry_date <= _today():
            raise HTTPException(
                status_code=409, detail=f"IRB {irb_id} is expired or has no expiry date"
            )
    retention = body.retention_until or ds.retention_until
    if not retention:
        raise HTTPException(
            status_code=409, detail="retention_until is required to approve a dataset"
        )
    now = datetime.now(UTC).isoformat()
    ds = update_dataset(
        db,
        ds.id,
        status="approved",
        admin_approved_by=current_user.id,
        admin_approved_at=now,
        retention_until=retention,
        # The FULL id, not a prefix: platform-control derives every dataset
        # resource name from the id (bucket ds-<id>, ingest key ds-<id>-ingest)
        # and validates the pushed bucket against that derivation, so the two
        # sides can never disagree about which bucket a dataset owns.
        bucket=f"ds-{ds.id}",
    )
    log_action(
        request, current_user, "admin-approve", "dataset", ds.id, f"name={ds.name}"
    )
    push_dataset(db, ds.id)
    return _dataset_resp(db, ds)


@router.post("/{dataset_id}/transition", response_model=DatasetResponse)
def transition(
    request: Request,
    dataset_id: str,
    body: DatasetTransition,
    current_user: User = Depends(require_admin),
):
    """Lifecycle transitions after approval — driven by Curator's delivery today
    (via an admin credential) and by retention later. Strictly guarded:
    approved->delivering->sealed, and expired/revoked from any post-approval state."""
    db = get_db_path()
    ds = get_dataset(db, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    target = body.status
    if target == "delivering":
        allowed_from = {"approved"}
    elif target == "sealed":
        allowed_from = {"delivering"}
        if not (body.content_root_sha256 or ds.content_root_sha256):
            raise HTTPException(
                status_code=409,
                detail="sealing requires content_root_sha256 (the delivery merkle root)",
            )
    elif target in _TERMINAL:
        allowed_from = {"approved", "delivering", "sealed"}
    else:
        raise HTTPException(
            status_code=400,
            detail="transition targets: delivering|sealed|expired|revoked",
        )
    if ds.status not in allowed_from:
        raise HTTPException(
            status_code=409, detail=f"cannot go {ds.status} -> {target}"
        )
    fields: dict = {"status": target}
    if target == "sealed":
        fields["sealed_at"] = datetime.now(UTC).isoformat()
        if body.content_root_sha256:
            fields["content_root_sha256"] = body.content_root_sha256
    ds = update_dataset(db, ds.id, **fields)
    log_action(request, current_user, target, "dataset", ds.id, f"name={ds.name}")
    push_dataset(db, ds.id)
    return _dataset_resp(db, ds)


# ── Grants: extend a dataset to a project (which may be lab-less) ─────────────


@router.post(
    "/{dataset_id}/grants",
    response_model=DatasetGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
def propose_grant(
    request: Request,
    dataset_id: str,
    body: DatasetGrantCreate,
    current_user: User = Depends(get_current_user),
):
    """The PI leg of sharing: only the OWNING lab's PI proposes. The grant is
    pending (grants nothing anywhere) until a different platform admin approves."""
    db = get_db_path()
    ds = _load_visible(db, dataset_id, current_user)
    _require_owning_pi(db, ds, current_user)
    if ds.status not in ("approved", "delivering", "sealed"):
        raise HTTPException(
            status_code=409,
            detail=f"grants need an approved dataset (is: {ds.status})",
        )
    if not get_project(db, body.project_id):
        raise HTTPException(status_code=400, detail="project does not exist")
    if any(
        g.project_id == body.project_id and g.revoked_at is None
        for g in list_grants(db, ds.id)
    ):
        raise HTTPException(
            status_code=409, detail="an unrevoked grant to this project already exists"
        )
    cvat_project_id = None
    if body.annotate:
        if not ds.renders:
            raise HTTPException(
                status_code=409,
                detail="annotate requested but this dataset was approved with renders=false — "
                       "CVAT cannot display DICOM, so an annotation grant needs renders",
            )
        # The staging target is the PROJECT's provisioned CVAT project — resolved here so the
        # push carries a concrete CVAT id and the cluster never guesses. No provision, no
        # staging: the PI provisions first (POST /projects/{id}/cvat/provision), then grants.
        from ...crud.cvat import list_cvat_projects

        rows = list_cvat_projects(db, body.project_id)
        if not rows:
            raise HTTPException(
                status_code=400,
                detail="annotate requested but the project has no provisioned CVAT project — "
                       "provision it first, then grant",
            )
        cvat_project_id = int(rows[-1].cvat_id)
    g = create_grant(
        db, ds.id, body.project_id, granted_by=current_user.id,
        expires_at=body.expires_at,
        cvat_project_id=cvat_project_id,
        task_size=(body.task_size if body.annotate else None),
    )
    log_action(
        request, current_user, "propose-grant", "dataset", ds.id,
        f"project={body.project_id}",
    )
    return _grant_resp(g)


@router.post("/{dataset_id}/grants/{grant_id}/approve", response_model=DatasetGrantResponse)
def activate_grant(
    request: Request,
    dataset_id: str,
    grant_id: str,
    current_user: User = Depends(require_admin),
):
    db = get_db_path()
    g = get_grant(db, grant_id)
    if not g or g.dataset_id != dataset_id:
        raise HTTPException(status_code=404, detail="Grant not found")
    if g.revoked_at:
        raise HTTPException(status_code=409, detail="grant is revoked")
    if g.admin_approved_at:
        raise HTTPException(status_code=409, detail="grant is already approved")
    if g.granted_by == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="the admin approver must be a different human than the proposer",
        )
    g = approve_grant(db, grant_id, current_user.id)
    log_action(
        request, current_user, "approve-grant", "dataset", dataset_id,
        f"project={g.project_id}",
    )
    from ...crud.datasets import bump_generation

    bump_generation(db, dataset_id)
    push_dataset(db, dataset_id)
    return _grant_resp(g)


@router.delete("/{dataset_id}/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke(
    request: Request,
    dataset_id: str,
    grant_id: str,
    current_user: User = Depends(get_current_user),
):
    """Revocation is deliberately easier than granting: the owning lab's PI OR a
    platform admin, one human, effective on the next push."""
    db = get_db_path()
    ds = get_dataset(db, dataset_id)
    g = get_grant(db, grant_id)
    if not ds or not g or g.dataset_id != dataset_id:
        raise HTTPException(status_code=404, detail="Grant not found")
    if not current_user.is_admin:
        _require_owning_pi(db, ds, current_user)
    if g.revoked_at:
        return None  # already revoked — idempotent
    revoke_grant(db, grant_id, current_user.id)
    log_action(
        request, current_user, "revoke-grant", "dataset", dataset_id,
        f"project={g.project_id}",
    )
    from ...crud.datasets import bump_generation

    bump_generation(db, dataset_id)
    push_dataset(db, dataset_id)
    return None
