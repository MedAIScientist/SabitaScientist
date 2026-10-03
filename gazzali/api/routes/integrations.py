"""Companion application launcher routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ...integrations import INTEGRATIONS, resolve_base_url, statuses
from ...models import User
from ..deps import get_current_user
from ..schemas import IntegrationStatus

router = APIRouter()


@router.get("/integrations", response_model=list[IntegrationStatus])
def list_integrations(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Advertise the cluster-hosted companion apps and whether each is reachable.

    Admin-only entries (the identity provider) are hidden from other users rather
    than shown disabled — a greyed-out card would still disclose that it exists.
    """
    visible = [
        item for item in INTEGRATIONS if not item.admin_only or current_user.is_admin
    ]
    probed = {status["key"]: status for status in statuses(resolve_base_url(request))}
    return [IntegrationStatus(**probed[item.key]) for item in visible]
