"""OIDC (Microsoft 365 / Azure AD) authentication routes."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from sqlite3 import IntegrityError

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from ...auth import create_token, hash_password
from ...crud.users import create_user, get_user_by_email
from ...db import get_db, get_db_path
from ...oidc import (
    ProviderUnavailable,
    exchange_code,
    get_authorization_url,
    is_configured,
    is_reachable,
)

router = APIRouter()
_TOKEN_TTL_HOURS = 24

# In-memory state store for CSRF protection (single-server only)
_oidc_states: dict[str, str] = {}  # state -> redirect_after


@router.get("/login/oidc")
def oidc_login(redirect: str = "/login"):
    """Redirect to OIDC provider (Authentik or Microsoft) login page."""
    if not is_configured():
        raise HTTPException(
            503, "OIDC not configured — set OIDC_CLIENT_ID and OIDC_CLIENT_SECRET"
        )

    state = secrets.token_hex(16)
    _oidc_states[state] = redirect
    try:
        auth_url = get_authorization_url(state)
    except ProviderUnavailable as exc:
        # Never send the browser to a different provider as a stand-in; say what is
        # wrong and let the user sign in with a password.
        _oidc_states.pop(state, None)
        raise HTTPException(
            503,
            "Single sign-on is unavailable: the identity provider is not answering. "
            "Sign in with your username or e-mail and password instead.",
        ) from exc
    return RedirectResponse(url=auth_url)


def _create_sso_user(db, username: str, email: str):
    """Create the account for a first SSO sign-in, never adopting someone else's.

    The display name is tried first because it is what people recognise. If another account
    already holds it, the e-mail disambiguates — e-mails are UNIQUE, so "name (email)" cannot
    collide with another SSO account. A concurrent first sign-in of the SAME person is
    recognised by its e-mail, not by its name.
    """
    for candidate in (username, f"{username} ({email})", f"{email}-{secrets.token_hex(3)}"):
        try:
            return create_user(
                db,
                username=candidate,
                password_hash=hash_password(secrets.token_hex(16)),
                email=email,
            )
        except IntegrityError:
            same_person = get_user_by_email(db, email)
            if same_person:
                return same_person
    raise HTTPException(500, "Could not create an account for this sign-in")


@router.get("/auth/oidc/callback")
async def oidc_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Handle the OIDC callback from the provider (Authentik or Microsoft)."""
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
        raise HTTPException(401, "Failed to authenticate with OIDC provider")

    # Find or create PM user. Match by email first — it is stable across
    # providers and survives display-name changes; matching by username only
    # would try to insert a duplicate email and 500 on UNIQUE constraint.
    db = get_db_path()
    username = (
        oidc_user.name
        or oidc_user.preferred_username
        or oidc_user.email
        or oidc_user.sub.split("-")[0][:20]
    )
    if oidc_user.email:
        # An e-mail is the identity. A display name is NOT: two people share names, and
        # anyone who can set a display name in the identity provider could otherwise sign
        # in as the existing account that happens to carry that username — an admin's
        # included. So with an e-mail, a miss creates a NEW account; it never adopts one.
        user = get_user_by_email(db, oidc_user.email)
        if not user:
            user = _create_sso_user(db, username, oidc_user.email)
    else:
        # No e-mail claim: refuse. The only other key on offer is the display name, and matching
        # it adopted whichever existing account carried that username — an admin's included —
        # for anyone whose identity-provider account has no address (or who can rename
        # themselves). Creating a fresh account instead would make a new one at every sign-in.
        # No live sign-in relies on this path: the teacher's password account signs in through
        # the form, and his single sign-on identity carries an e-mail.
        raise HTTPException(
            403,
            "This sign-in carries no e-mail address, so it cannot be matched to an account. "
            "Ask an administrator to add your e-mail in the identity provider, then sign in again.",
        )

    # The address decides student vs professor (new accounts used to default to student).
    from ...roles import sync_role

    user = sync_role(db, user)

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
    """Whether single sign-on is configured *and* the provider is answering.

    Configuration alone is not enough to show a working button: the provider sits
    behind a gateway that can be down while this app is healthy, and a user who
    clicks into a gateway error page has no way to know a password still works.
    """
    configured = is_configured()
    return {
        "configured": configured,
        "reachable": is_reachable() if configured else False,
    }
