"""Microsoft O365 / Azure AD OIDC authentication for the PM API."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx
from jwt import PyJWKClient
from jwt import decode as jwt_decode

logger = logging.getLogger(__name__)

OIDC_CONFIG = {
    "client_id": os.environ.get("OIDC_CLIENT_ID", ""),
    "client_secret": os.environ.get("OIDC_CLIENT_SECRET", ""),
    "tenant_id": os.environ.get("OIDC_TENANT_ID", "common"),
    "redirect_uri": os.environ.get("OIDC_REDIRECT_URI", "http://localhost:7860/api/v1/auth/oidc/callback"),
    "scope": os.environ.get("OIDC_SCOPE", "openid email profile"),
}


@dataclass
class OIDCUser:
    sub: str
    email: str | None
    name: str | None
    preferred_username: str | None
    issuer: str


def is_configured() -> bool:
    return bool(OIDC_CONFIG["client_id"] and OIDC_CONFIG["client_secret"])


def get_authorization_url(state: str) -> str:
    """Build the Azure AD authorize URL."""
    tenant = OIDC_CONFIG["tenant_id"]
    return (
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize"
        f"?client_id={OIDC_CONFIG['client_id']}"
        f"&response_type=code"
        f"&redirect_uri={OIDC_CONFIG['redirect_uri']}"
        f"&scope={OIDC_CONFIG['scope']}"
        f"&state={state}"
        f"&response_mode=query"
    )


async def exchange_code(code: str) -> OIDCUser | None:
    """Exchange an authorization code for an ID token and decode it."""
    tenant = OIDC_CONFIG["tenant_id"]
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(token_url, data={
                "client_id": OIDC_CONFIG["client_id"],
                "client_secret": OIDC_CONFIG["client_secret"],
                "code": code,
                "redirect_uri": OIDC_CONFIG["redirect_uri"],
                "grant_type": "authorization_code",
                "scope": OIDC_CONFIG["scope"],
            })
            if resp.status_code != 200:
                logger.error("Token exchange failed: %s", resp.text)
                return None

            tokens = resp.json()
            id_token = tokens.get("id_token")
            if not id_token:
                logger.error("No id_token in response")
                return None

            return _decode_id_token(id_token)
    except Exception:
        logger.exception("OIDC token exchange failed")
        return None


def _decode_id_token(id_token: str) -> OIDCUser | None:
    """Decode and verify an Azure AD ID token."""
    try:
        tenant = OIDC_CONFIG["tenant_id"]
        issuer = f"https://login.microsoftonline.com/{tenant}/v2.0"
        jwks_url = f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"

        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)

        claims: dict[str, Any] = jwt_decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=OIDC_CONFIG["client_id"],
            issuer=issuer,
            options={"verify_exp": True},
        )

        return OIDCUser(
            sub=claims.get("sub", ""),
            email=claims.get("email") or claims.get("upn"),
            name=claims.get("name"),
            preferred_username=claims.get("preferred_username"),
            issuer=claims.get("iss", ""),
        )
    except Exception:
        logger.exception("Failed to decode ID token")
        return None
