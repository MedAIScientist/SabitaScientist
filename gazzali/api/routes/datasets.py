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

import logging
import os
import uuid
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
    raise_estimated_bytes,
    revoke_grant,
    update_dataset,
)
from ...crud.irb import get_irb
from ...crud.labs import get_lab, get_member_role as get_lab_member_role
from ...crud.labs import list_labs_for_user
from ...crud.projects import get_member_role as get_project_member_role
from ...crud.projects import get_project
from ...db import get_db_path
from ...models import Dataset, User
from ... import curator_bridge
from ...platform_pull import bucket_usage
from ...platform_push import push_dataset
from ..audit_helper import log_action
from ..deps import get_current_user, require_admin
from ..schemas import (
    DatasetAdminApprove,
    DatasetCreate,
    DatasetGrantCreate,
    DatasetGrantResponse,
    DatasetResponse,
    DatasetStorageRaise,
    DatasetTransition,
)

router = APIRouter()
logger = logging.getLogger(__name__)

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


def _project_name(db, project_id: str) -> str | None:
    project = get_project(db, project_id)
    return project.name if project else None


def _grant_resp(g, project_name: str | None = None) -> DatasetGrantResponse:
    return DatasetGrantResponse(
        id=g.id,
        dataset_id=g.dataset_id,
        project_id=g.project_id,
        project_name=project_name,
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


def _dataset_resp(db, ds: Dataset, user: User | None = None) -> DatasetResponse:
    keys = ds.accession_list or []
    return DatasetResponse(
        id=ds.id,
        name=ds.name,
        purpose=ds.purpose,
        lab_id=ds.lab_id,
        requested_by=ds.requested_by,
        modality=ds.modality,
        # Study keys to platform admins only (delivery, audits); a researcher sees the count.
        accession_list=keys if (user is not None and user.is_admin) else [],
        accession_count=len(keys),
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
        project_id=ds.project_id,
        grants=[_grant_resp(g, _project_name(db, g.project_id)) for g in list_grants(db, ds.id)],
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
    if body.project_id and get_project_member_role(db, body.project_id, current_user.id) not in (
        "owner", "editor",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="requesting data for a project needs owner or editor role in it",
        )
    if body.curator_selection_id and body.accession_list:
        raise HTTPException(
            status_code=400,
            detail="send a saved Curator selection or an accession list, not both",
        )
    if not body.curator_selection_id:
        # A typed or pasted list is the manual step the Curator hand-off replaced: researchers never
        # hold accession numbers, so filing by list stays an API for platform admins only.
        if not current_user.is_admin:
            raise HTTPException(
                status_code=400,
                detail="choose one of your saved Curator selections for this request",
            )
        if not body.accession_list:
            raise HTTPException(
                status_code=400, detail="a dataset names at least one accession"
            )

    # Everything checkable here has been checked; only now is Curator asked. The selection is marked
    # requested under THIS id in the same step that hands its studies over, so it can never be
    # requested twice, and the two systems name the dataset identically from the first moment.
    dataset_id = uuid.uuid4().hex
    accessions = body.accession_list
    estimated = body.estimated_bytes
    modality = body.modality
    if body.curator_selection_id:
        accessions, estimated, modality = _take_curator_selection(
            body, current_user, dataset_id)
    try:
        ds = create_dataset(
            db,
            name=body.name,
            purpose=body.purpose,
            lab_id=body.lab_id,
            requested_by=current_user.id,
            modality=modality,
            accession_list=accessions,
            estimated_bytes=estimated,
            renders=body.renders,
            project_id=body.project_id,
            dataset_id=dataset_id,
        )
    except Exception:
        if body.curator_selection_id:
            # No dataset exists, so the selection must not stay marked as requested.
            curator_bridge.retract_selection(body.curator_selection_id, current_user.email or "",
                                             dataset_id)
        raise
    for irb_id in body.irb_ids:
        link_irb(db, ds.id, irb_id)
    log_action(request, current_user, "create", "dataset", ds.id,
               f"name={ds.name} studies={len(accessions)}"
               + (f" curator_selection={body.curator_selection_id}" if body.curator_selection_id else ""))
    return _dataset_resp(db, ds, current_user)


def _take_curator_selection(body: DatasetCreate, user: User,
                            dataset_id: str) -> tuple[list[str], int | None, str | None]:
    """(accessions, estimated_bytes, modality) for the researcher's saved Curator selection, read
    server to server — or the HTTP error the person should see. The studies never touch a browser.

    The storage estimate is Curator's own arithmetic (measured bytes per DICOM image, plus per
    viewable image when renders are asked for, for this selection's modality) plus a margin; it
    pre-fills the admin's "Storage to reserve"."""
    if not curator_bridge.configured():
        raise HTTPException(status_code=503, detail="the link to Curator is not configured")
    if not user.email:
        raise HTTPException(
            status_code=409,
            detail="your account has no e-mail address, so your Curator selections cannot be found",
        )
    try:
        handed = curator_bridge.submit_selection(body.curator_selection_id or "", user.email,
                                                 dataset_id)
    except curator_bridge.CuratorRefused as exc:
        if exc.status == 404:
            raise HTTPException(status_code=404,
                                detail="that selection is not one of yours, or it has expired") from exc
        if exc.status == 409:
            raise HTTPException(status_code=409, detail=exc.detail) from exc
        raise HTTPException(status_code=503,
                            detail="Curator refused Medai's request; nothing was filed") from exc
    except curator_bridge.CuratorUnavailable as exc:
        # Curator may have recorded the submit and only the answer was lost: undo it now if it did
        # (exact id, so harmless if it did not). One that lands later is released by the dialog's
        # own listing (curator_selections) once it is old enough to be sure.
        curator_bridge.retract_selection(body.curator_selection_id or "", user.email, dataset_id)
        raise HTTPException(status_code=503,
                            detail="Curator could not be reached; nothing was filed — try again") from exc
    accessions = [str(a) for a in (handed.get("accessions") or []) if str(a).strip()]
    if not accessions:
        curator_bridge.retract_selection(body.curator_selection_id or "", user.email, dataset_id)
        raise HTTPException(status_code=409, detail="that selection holds no studies")
    per_image, per_render = curator_bridge.rates_from(handed)
    estimated = curator_bridge.estimated_bytes(
        int(handed.get("instances") or 0), renders=body.renders,
        bytes_per_instance=per_image, bytes_per_render=per_render)
    modality = body.modality or handed.get("modality") or None
    return accessions, estimated if estimated is not None else body.estimated_bytes, modality


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
        _dataset_resp(db, ds, current_user)
        for ds in list_datasets(db, lab_ids=lab_ids, status=status_filter)
    ]


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_detail(dataset_id: str, current_user: User = Depends(get_current_user)):
    db = get_db_path()
    return _dataset_resp(db, _load_visible(db, dataset_id, current_user), current_user)


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
    return _dataset_resp(db, ds, current_user)


@router.post("/{dataset_id}/admin-approve", response_model=DatasetResponse)
def admin_approve(
    request: Request,
    dataset_id: str,
    body: DatasetAdminApprove,
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
        # The storage the admin reserves, when given; otherwise whatever the request carried.
        estimated_bytes=body.estimated_bytes or ds.estimated_bytes,
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
    return _dataset_resp(db, ds, current_user)


def _first_limit_refusal(dataset_id: str) -> str | None:
    """Why a FIRST limit must not be set now, or None. A bucket with no limit may already be being
    delivered into — and Medai cannot tell: nothing sets 'delivering' during a real delivery. A
    first limit is therefore accepted only on a bucket that is verifiably empty (or not created
    yet), and refused when what it holds cannot be read. Raising an existing limit needs none of
    this: it only ever grows."""
    if not (os.environ.get("MEDAI_PLATFORM_CONTROL_URL") and os.environ.get("MEDAI_PLATFORM_CONTROL_TOKEN")):
        return None  # nothing is pushed anywhere, so no bucket exists to protect
    try:
        usage = bucket_usage(dataset_id)
    except Exception:  # unknown contents must refuse, whatever the failure
        logger.warning("first storage limit refused: catalogue unreadable dataset=%s", dataset_id)
        return "could not check what the dataset's bucket already holds — try again in a moment"
    if usage is not None and (usage[0] > 0 or usage[1] > 0):
        return (f"the bucket already holds {usage[0]} objects and has no limit; a delivery may be "
                "writing to it, and a first limit could land below what it holds — a first limit "
                "can be set only while the bucket is empty")
    # Empty when checked is the most Medai can know: a delivery that has just started may not have
    # stored its first object yet. If it then meets this limit it stops loudly and never seals;
    # raising the limit and delivering again resumes it. The UI says so next to the field.
    return None


@router.post("/{dataset_id}/storage", response_model=DatasetResponse)
def raise_storage(
    request: Request,
    dataset_id: str,
    body: DatasetStorageRaise,
    current_user: User = Depends(require_admin),
):
    """Reserve more storage for an approved dataset — the remedy when Curator refuses a delivery
    because the cohort cannot fit, or when it was approved without a reservation.

    RAISE-ONLY. platform-control applies the pushed quota exactly, in both directions; a value
    below what the bucket already holds would stop the delivery that is filling it. And only
    while a delivery can still write: a sealed bucket has no writer to make room for."""
    db = get_db_path()
    ds = get_dataset(db, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if ds.status not in ("approved", "delivering"):
        raise HTTPException(
            status_code=409,
            detail=f"storage can be reserved only before delivery finishes (is: {ds.status})",
        )
    if not ds.estimated_bytes and ds.status == "delivering":
        # The bucket has no limit and a delivery is writing to it: a first limit could land below
        # what it already holds and stop that delivery. Reserve before delivering, not during.
        raise HTTPException(
            status_code=409,
            detail="this bucket has no limit and is being delivered into; a first reservation "
                   "could be smaller than what it already holds — set it before delivery starts",
        )
    if ds.estimated_bytes and body.estimated_bytes <= ds.estimated_bytes:
        raise HTTPException(
            status_code=409,
            detail=f"storage can only be raised (currently {ds.estimated_bytes} bytes)",
        )
    if not ds.estimated_bytes:
        refusal = _first_limit_refusal(ds.id)
        if refusal:
            raise HTTPException(status_code=409, detail=refusal)
    if not raise_estimated_bytes(db, ds.id, body.estimated_bytes):
        # Another change landed between the checks above and the write (a concurrent raise, a
        # status move): nothing was written. The caller reloads and decides again.
        raise HTTPException(status_code=409, detail="the dataset changed meanwhile; reload and try again")
    ds = get_dataset(db, ds.id)
    log_action(
        request, current_user, "raise-storage", "dataset", ds.id,
        f"estimated_bytes={body.estimated_bytes}",
    )
    push_dataset(db, ds.id)
    return _dataset_resp(db, ds, current_user)


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
    return _dataset_resp(db, ds, current_user)


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
    return _grant_resp(g, _project_name(db, g.project_id))


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
    return _grant_resp(g, _project_name(db, g.project_id))


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
