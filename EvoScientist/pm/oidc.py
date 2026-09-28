"""Generic OIDC authentication via discovery — works with Authentik, Microsoft, etc.

When ``issuer_url`` is configured, uses OIDC discovery (``.well-known/openid-configuration``)
to dynamically resolve authorize, token, and JWKS endpoints.
Falls back to Microsoft-specific URLs when ``issuer_url`` is empty (backward compatible).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx
from jwt import PyJWKClient
from jwt import decode as jwt_decode

from ._evoscientist import get_oidc_config

logger = logging.getLogger(__name__)

OIDC_CONFIG = get_oidc_config()

# Lazily-populated OIDC discovery document
_discovery_doc: dict | None = None


@dataclass
class OIDCUser:
    sub: str
    email: str | None
    name: str | None
    preferred_username: str | None
    issuer: str


def is_configured() -> bool:
    return bool(OIDC_CONFIG["client_id"] and OIDC_CONFIG["client_secret"])


def _load_discovery() -> dict | None:
    """Fetch and cache OIDC discovery document from issuer_url."""
    global _discovery_doc
    if _discovery_doc is not None:
        return _discovery_doc
    issuer_url = OIDC_CONFIG.get("issuer_url", "")
    if not issuer_url:
        _discovery_doc = None
        return None
    disc_url = issuer_url.rstrip("/") + "/.well-known/openid-configuration"
    try:
        resp = httpx.get(disc_url, timeout=10.0)
        resp.raise_for_status()
        _discovery_doc = resp.json()
        return _discovery_doc
    except Exception as exc:
        logger.warning("OIDC discovery failed for %s: %s", issuer_url, exc)
        _discovery_doc = None
        return None


def _discovery_url(key: str) -> str | None:
    doc = _load_discovery()
    if doc is None:
        return None
    val = doc.get(key)
    if isinstance(val, str) and val:
        return val
    logger.warning("OIDC discovery doc missing '%s'", key)
    return None


def _authorize_url() -> str:
    microsoft_url = (
        f"https://login.microsoftonline.com/{OIDC_CONFIG['tenant_id']}"
        "/oauth2/v2.0/authorize"
    )
    return _discovery_url("authorization_endpoint") or microsoft_url


def _token_url() -> str:
    microsoft_url = (
        f"https://login.microsoftonline.com/{OIDC_CONFIG['tenant_id']}"
        "/oauth2/v2.0/token"
    )
    return _discovery_url("token_endpoint") or microsoft_url


def _jwks_url() -> str:
    microsoft_url = (
        f"https://login.microsoftonline.com/{OIDC_CONFIG['tenant_id']}"
        "/discovery/v2.0/keys"
    )
    return _discovery_url("jwks_uri") or microsoft_url


def _expected_issuer() -> str:
    # Prefer the issuer the provider advertises in its own discovery document. That value is
    # authoritative and is byte-for-byte what lands in the id_token "iss" claim — trailing
    # slash included. Authentik advertises ".../application/o/<slug>/" WITH a trailing slash;
    # rstrip("/")-ing the configured URL would drop it, and PyJWT's exact-string issuer check
    # would then reject every token (InvalidIssuerError -> 401). Consulting discovery here also
    # makes this consistent with _authorize_url/_token_url/_jwks_url, which already do.
    # Provider-neutral: for Entra, discovery "issuer" equals the Microsoft fallback below, so
    # the current Entra login is unchanged; when issuer_url is empty, discovery is unavailable
    # and we fall through to exactly today's behaviour.
    discovered = _discovery_url("issuer")
    if discovered:
        return discovered
    issuer_url = OIDC_CONFIG.get("issuer_url", "")
    if issuer_url:
        return issuer_url.rstrip("/")
    tenant = OIDC_CONFIG["tenant_id"]
    return f"https://login.microsoftonline.com/{tenant}/v2.0"


def get_authorization_url(state: str) -> str:
    """Build the OIDC authorize URL (discovery or Microsoft fallback)."""
    return (
        f"{_authorize_url()}"
        f"?client_id={OIDC_CONFIG['client_id']}"
        f"&response_type=code"
        f"&redirect_uri={OIDC_CONFIG['redirect_uri']}"
        f"&scope={OIDC_CONFIG['scope']}"
        f"&state={state}"
        f"&response_mode=query"
    )


async def exchange_code(code: str) -> OIDCUser | None:
    """Exchange an authorization code for an ID token and decode it."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _token_url(),
                data={
                    "client_id": OIDC_CONFIG["client_id"],
                    "client_secret": OIDC_CONFIG["client_secret"],
                    "code": code,
                    "redirect_uri": OIDC_CONFIG["redirect_uri"],
                    "grant_type": "authorization_code",
                    "scope": OIDC_CONFIG["scope"],
                },
            )
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
    """Decode and verify an OIDC ID token (any provider)."""
    try:
        issuer = _expected_issuer()
        jwks_url = _jwks_url()

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
