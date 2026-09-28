"""CVAT REST API client — a thin, lazily configured wrapper.

Only what project provisioning needs: create a project, and read one back.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# The call crosses two hops (DMZ nginx -> Kubernetes Gateway -> CVAT), so allow more
# than httpx's default while still failing instead of hanging forever.
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_ERROR_BODY_CHARS = 300


class CVATError(RuntimeError):
    """CVAT is unconfigured, unreachable, or answered with an error."""


def _config() -> tuple[str, str, str]:
    """Return ``(base_url, token, auth_scheme)`` from the environment.

    Read on every call rather than captured at import time: importing this module must
    never fail, so it can never depend on the environment already being populated.
    """
    return (
        os.environ.get("CVAT_BASE_URL", "").rstrip("/"),
        os.environ.get("CVAT_API_TOKEN", ""),
        # "Token <key>" is DRF TokenAuthentication, what a login-issued key uses, and
        # what this deployment is verified against. CVAT 2.69 also accepts a UI-issued
        # "API Access token" as "Bearer <key>" — set CVAT_AUTH_SCHEME=Bearer for that
        # kind of credential, otherwise every call 401s with nothing naming the cause.
        os.environ.get("CVAT_AUTH_SCHEME", "Token"),
    )


def is_configured() -> bool:
    """Return whether CVAT_BASE_URL and CVAT_API_TOKEN are both set."""
    base_url, token, _ = _config()
    return bool(base_url and token)


def _connection() -> tuple[str, dict[str, str]]:
    """Return ``(base_url, headers)``, raising CVATError if CVAT is not configured.

    TLS verification stays at httpx's default (the system trust store): CVAT is reached
    over its public URL, which serves a publicly trusted certificate. There is
    deliberately no ``verify`` knob here — a global trust-store override would also
    break this app's server-side Microsoft SSO.
    """
    base_url, token, scheme = _config()
    if not base_url or not token:
        raise CVATError("CVAT is not configured; set CVAT_BASE_URL and CVAT_API_TOKEN")
    # No explicit Accept header on purpose. CVAT renders a VENDOR media type
    # ("application/vnd.cvat+json"), so "Accept: application/json" is rejected outright
    # with 406 "Could not satisfy the request Accept header" — verified against the live
    # server. httpx's default "*/*" is what plain curl sends and what CVAT accepts.
    return base_url, {"Authorization": f"{scheme} {token}"}


def _excerpt(resp: httpx.Response) -> str:
    """Return a short single-line excerpt of a response body, for error messages.

    Only ever applied to CVAT's own reply, which never contains our credential.
    """
    text = " ".join(resp.text.split())
    return text[:_ERROR_BODY_CHARS] + " ..." if len(text) > _ERROR_BODY_CHARS else text


def _check(resp: httpx.Response, *, expected: tuple[int, ...], what: str) -> dict:
    """Return the decoded JSON object, raising CVATError on any unexpected reply."""
    if resp.status_code in (401, 403):
        # Never echo the body here: the cause is our credential, and the useful remedy
        # is naming the two settings that control it.
        raise CVATError(
            f"CVAT rejected the API token (HTTP {resp.status_code}); "
            "check CVAT_API_TOKEN and CVAT_AUTH_SCHEME"
        )
    if resp.status_code not in expected:
        raise CVATError(f"{what} (HTTP {resp.status_code}): {_excerpt(resp)}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise CVATError(f"{what}: CVAT returned a non-JSON response") from exc
    if not isinstance(data, dict):
        raise CVATError(f"{what}: CVAT returned an unexpected response shape")
    return data


async def _request(method: str, path: str, json_body: dict | None = None) -> httpx.Response:
    """Send one request to CVAT, converting transport failures into CVATError."""
    base_url, headers = _connection()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            return await client.request(
                method, f"{base_url}{path}", json=json_body, headers=headers
            )
    except httpx.HTTPError as exc:
        # Log the exception TYPE only: an httpx message can carry the request URL, and
        # nothing from this module may ever put the credential into a log line.
        logger.warning("CVAT %s %s failed: %s", method, path, type(exc).__name__)
        raise CVATError(f"CVAT is unreachable ({type(exc).__name__})") from exc


def _storage_block() -> dict:
    """Return target/source storage pointing at the configured CVAT cloud storage.

    Empty dict when CVAT_CLOUD_STORAGE_ID is unset, so a deployment without object storage
    behaves exactly as before — projects are simply created without a storage binding.

    Why both target and source: target is where an export is written, source is where an
    import is read from. Binding only the target would export to S3 but still expect uploads
    from the local disk, which is a confusing half-configuration.
    """
    raw = os.environ.get("CVAT_CLOUD_STORAGE_ID", "").strip()
    if not raw:
        return {}
    try:
        cs_id = int(raw)
    except ValueError:
        # Never fail project creation over a malformed optional setting.
        logger.warning("CVAT_CLOUD_STORAGE_ID is not an integer; ignoring it")
        return {}
    # CVAT rejects a cloud_storage_id without location="cloud_storage" and vice versa
    # (StorageSerializer.validate), so the pair must always travel together.
    block = {"location": "cloud_storage", "cloud_storage_id": cs_id}
    return {"target_storage": dict(block), "source_storage": dict(block)}


async def create_project(name: str, labels: list[dict] | None = None) -> dict:
    """Create a project in CVAT and return its representation.

    When a cloud storage is configured the project is bound to it, so that a later dataset
    export is written into the bucket instead of CVAT's local disk. The object key is chosen
    per export via the ?filename= parameter (CVAT uses it verbatim, slashes included), which
    is what lets the platform record a predictable export_key.
    """
    body = {"name": name, "labels": labels or []}
    body.update(_storage_block())
    resp = await _request("POST", "/api/projects", body)
    return _check(resp, expected=(200, 201), what="CVAT refused the project")


async def get_project(cvat_id: int) -> dict:
    """Return one CVAT project by its numeric id."""
    resp = await _request("GET", f"/api/projects/{int(cvat_id)}")
    return _check(resp, expected=(200,), what=f"CVAT project {cvat_id} is unreadable")
