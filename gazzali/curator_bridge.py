"""Medai ↔ Curator hand-off: Medai's server reads a researcher's saved Curator selection directly.

It replaces a manual step that should never have existed — an administrator copying a cohort's
accession numbers out of Curator and pasting them into the request dialog, which also forced that
administrator onto every student's project, because only a project's editors may file for it.
Now the researcher picks their own saved selection; this module fetches the list server to server,
and no person ever holds it.

Same shape as the platform-control push client: the DMZ calls INTO the cluster (the allowed
firewall direction) over TLS pinned to the internal CA, with a dedicated bearer token. Curator
serves these routes only on the internal hostname, and only to that token.

Configuration (all three empty = the feature is off and the dialog says so):
    CURATOR_HANDOFF_URL     e.g. https://platform.medai.medipol.edu.tr
    CURATOR_HANDOFF_TOKEN   the shared secret (never logged)
    CURATOR_HANDOFF_CA      CA pem; defaults to MEDAI_PLATFORM_CONTROL_CA (the same internal CA)
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15


class CuratorUnavailable(RuntimeError):
    """Curator could not be reached or failed on its side (transport error or 5xx)."""


class CuratorRefused(Exception):
    """Curator answered a firm 4xx — its detail is meant for the person who asked."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


def configured() -> bool:
    return bool(os.environ.get("CURATOR_HANDOFF_URL") and os.environ.get("CURATOR_HANDOFF_TOKEN"))


def _request(method: str, path: str, *, body: dict | None = None,
             query: dict | None = None) -> dict[str, Any]:
    base = os.environ.get("CURATOR_HANDOFF_URL", "").rstrip("/")
    token = os.environ.get("CURATOR_HANDOFF_TOKEN", "")
    if not base or not token:
        raise CuratorUnavailable("the Curator hand-off is not configured")
    url = f"{base}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    # The gateway serves the platform's INTERNAL CA, which no system store carries. Pin the CA,
    # never the 90-day leaf — the same rule the platform push client follows.
    ca = os.environ.get("CURATOR_HANDOFF_CA") or os.environ.get("MEDAI_PLATFORM_CONTROL_CA", "")
    ctx = ssl.create_default_context(cafile=ca) if ca else None
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS, context=ctx) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = str(json.loads(exc.read() or b"{}").get("detail") or "")
        except (ValueError, AttributeError):
            pass
        if 400 <= exc.code < 500:
            raise CuratorRefused(exc.code, detail or exc.reason) from exc
        raise CuratorUnavailable(f"Curator answered {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise CuratorUnavailable(f"Curator could not be reached: {exc}") from exc


def list_selections(email: str) -> dict[str, Any]:
    """{selections: [...], bytes_per_object, rate_source} for the person with this e-mail.
    Counts and status only — Curator never puts an accession or the stored query in this answer."""
    return _request("GET", "/api/v1/handoff/selections", query={"owner_email": email})


def submit_selection(selection_id: str, email: str, dataset_id: str) -> dict[str, Any]:
    """Mark the selection requested as `dataset_id` and return its accessions (server side only)."""
    return _request("POST", f"/api/v1/handoff/selections/{urllib.parse.quote(selection_id)}/submit",
                    body={"owner_email": email, "dataset_id": dataset_id})


def retract_selection(selection_id: str, email: str, dataset_id: str) -> bool:
    """Undo a submit whose dataset could not be created. Best effort: a failure here is logged, the
    original error still reaches the person, and Curator's admin queue shows the stray mark."""
    try:
        answer = _request(
            "POST", f"/api/v1/handoff/selections/{urllib.parse.quote(selection_id)}/retract",
            body={"owner_email": email, "dataset_id": dataset_id})
        return bool(answer.get("retracted"))
    except (CuratorUnavailable, CuratorRefused) as exc:
        logger.warning("curator retract failed selection=%s dataset=%s: %s",
                       selection_id, dataset_id, exc)
        return False


def estimated_bytes(instances: int, *, renders: bool, bytes_per_instance: int,
                    bytes_per_render: int) -> int | None:
    """The storage to reserve: the delivery preflight's arithmetic — bytes per DICOM image, plus
    bytes per viewable image (PNG) when renders are asked for, both measured by Curator for this
    selection's modality — plus a 25% margin, because a rate is an average and the quota is a hard
    stop. None while nothing has been measured: an invented number would become a real limit.

    Per IMAGE, never per stored object. On 2026-10-17 a per-object average — diluted by one tiny
    manifest file per study and by light PNGs — under-stated a DX cohort 1.88x, and the reservation
    Medai suggested stopped its delivery at study 11 of 12."""
    if instances <= 0 or bytes_per_instance <= 0:
        return None
    per_image = bytes_per_instance + (max(0, bytes_per_render) if renders else 0)
    return -(-instances * per_image * 5 // 4)   # ceil(instances x per-image x 1.25), in integers


def rates_from(answer: dict[str, Any]) -> tuple[int, int]:
    """(bytes per DICOM image, bytes per render) from Curator's submit answer.

    A Curator build from before per-image sizing sends only `bytes_per_object`, meant to be
    multiplied by one object per image, or two with renders — which is the same arithmetic with
    the render priced at the object rate. So an older answer still reads correctly here."""
    if "bytes_per_instance" in answer:
        return int(answer.get("bytes_per_instance") or 0), int(answer.get("bytes_per_render") or 0)
    legacy = int(answer.get("bytes_per_object") or 0)
    return legacy, legacy
