"""OIDC (Microsoft 365 / Azure AD) authentication routes."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from ...auth import create_token
from ...crud.users import create_user
from ...db import get_db, get_db_path
from ...oidc import exchange_code, get_authorization_url, is_configured

router = APIRouter()
_TOKEN_TTL_HOURS = 24

# In-memory state store for CSRF protection (single-server only)
_oidc_states: dict[str, str] = {}  # state -> redirect_after


@router.get("/login/oidc")
def oidc_login(redirect: str = "/projects"):
    """Redirect to Microsoft login page."""
    if not is_configured():
        raise HTTPException(503, "OIDC not configured — set OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_TENANT_ID")

    state = secrets.token_hex(16)
    _oidc_states[state] = redirect
    auth_url = get_authorization_url(state)
    return RedirectResponse(url=auth_url)


@router.get("/auth/oidc/callback")
async def oidc_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    """Handle the OIDC callback from Microsoft."""
    if error:
        raise HTTPException(400, f"OIDC error: {error}")
    if not code or not state:
        raise HTTPException(400, "Missing code or state")

    # Verify state (CSRF)
    redirect_after = _oidc_states.pop(state, None)
    if redirect_after is None:
        raise HTTPException(400, "Invalid state parameter")

    # Exchange code for user info
    oidc_user = await exchange_code(code)
    if not oidc_user:
        raise HTTPException(401, "Failed to authenticate with Microsoft")

    # Find or create PM user
    from ...crud.users import get_user_by_username as _get_user
    db = get_db_path()
    username = oidc_user.preferred_username or oidc_user.email or oidc_user.sub.split("-")[0][:20]
    user = _get_user(db, username)

    if not user:
        existing = _get_user(db, username)
        if existing:
            user = existing
        else:
            random_pw = secrets.token_hex(16)
            user = create_user(
                db, username=username,
                password=random_pw,
                email=oidc_user.email,
            )

    # Issue session token
    token = create_token()
    expires_at = (datetime.now(UTC) + timedelta(hours=_TOKEN_TTL_HOURS)).isoformat()
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user.id, expires_at),
        )

    # Redirect back to the frontend with the token
    base_url = str(request.base_url).rstrip("/")
    redirect_url = f"{base_url}{redirect_after}?token={token}"
    return RedirectResponse(url=redirect_url)


@router.get("/auth/oidc/status")
def oidc_status():
    """Return whether OIDC is configured."""
    return {"configured": is_configured()}
