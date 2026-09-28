"""Companion applications published as subpaths of the public host.

CVAT, Curator and JupyterHub run in the Kubernetes cluster and are reverse
proxied by nginx under /cvat, /pacs and /jupyter — see
``deploy/nginx/conf.d/locations/*.conf``.

They deliberately cannot be embedded in the dashboard: each answers with
``X-Frame-Options: DENY`` or a CSP ``frame-ancestors 'none'``, so the dashboard
links out to them instead and reports whether they are reachable. Reachability
is probed server-side because the services send no CORS headers a browser could
read a status from.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx

# A probe that comes back with OUR OWN SPA means nginx is not routing the subpath
# — the failure mode deploy/nginx/conf.d/locations/cvat.conf warns about, where a
# mis-scoped location serves Medai's HTML with a 200 and looks like success. That
# must read as DOWN, so the body is checked rather than only the status code.
_SPA_MARKER = "Gazzali PM"
_BODY_SNIFF_BYTES = 8192

_PROBE_TIMEOUT_SECONDS = 6.0
# Short enough that a user who just started a service sees it flip, long enough
# that a dashboard left open does not hammer four upstreams every render.
_CACHE_TTL_SECONDS = 20.0

# Anything under 400 answered. 401/403 also mean the service is alive and merely
# wants credentials, which is the normal state for Authentik and JupyterHub.
_UP_BELOW = 400
_AUTH_STATUSES = frozenset({401, 403})


@dataclass(frozen=True)
class Integration:
    key: str
    name: str
    path: str
    kind: str
    description: str
    admin_only: bool = False


INTEGRATIONS: tuple[Integration, ...] = (
    Integration(
        key="cvat",
        name="CVAT",
        path="/cvat/",
        kind="annotation",
        description=(
            "Annotate images and video for computer-vision datasets: "
            "boxes, polygons, keypoints and tracks."
        ),
    ),
    Integration(
        key="curator",
        name="Curator",
        path="/pacs/",
        kind="imaging",
        description=(
            "Search the hospital PACS archive and pull imaging studies "
            "into a research dataset."
        ),
    ),
    Integration(
        key="jupyter",
        name="JupyterHub",
        path="/jupyter/",
        kind="compute",
        description=(
            "Notebook workspaces for analysis, figures and model development, "
            "backed by cluster compute."
        ),
    ),
    Integration(
        key="auth",
        name="Authentik",
        path="/auth/",
        kind="identity",
        description=(
            "Identity provider behind single sign-on. Administer users, groups "
            "and OIDC applications here."
        ),
        admin_only=True,
    ),
)

# base_url -> (monotonic timestamp, statuses)
_cache: dict[str, tuple[float, list[dict]]] = {}
_cache_lock = threading.Lock()


def resolve_base_url(request) -> str:
    """The public base URL a browser used, as nginx reports it.

    Honours X-Forwarded-Proto because the app itself is reached over plain HTTP
    on the docker network; without it every probe would be sent to the http
    listener, which answers a 301 for every path and so would report each service
    up even when it is down.
    """
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    proto = proto.split(",")[0].strip()
    host = request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}"


def _probe(client: httpx.Client, base_url: str, item: Integration) -> dict:
    started = time.perf_counter()
    status_code: int | None = None
    up = False
    try:
        resp = client.get(f"{base_url.rstrip('/')}{item.path}")
        status_code = resp.status_code
        up = (
            status_code < _UP_BELOW or status_code in _AUTH_STATUSES
        ) and _SPA_MARKER not in resp.text[:_BODY_SNIFF_BYTES]
    except httpx.HTTPError:
        up = False
    return {
        "key": item.key,
        "name": item.name,
        "path": item.path,
        "kind": item.kind,
        "description": item.description,
        "up": up,
        "http_status": status_code,
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


def _probe_all(base_url: str) -> list[dict]:
    # One client reused across the pool: TLS handshakes are the expensive part and
    # the four probes are independent, so they run concurrently.
    with httpx.Client(timeout=_PROBE_TIMEOUT_SECONDS, follow_redirects=False) as client:
        with ThreadPoolExecutor(max_workers=len(INTEGRATIONS)) as pool:
            return list(pool.map(lambda i: _probe(client, base_url, i), INTEGRATIONS))


def statuses(base_url: str, *, force: bool = False) -> list[dict]:
    """Return one status record per integration, cached briefly.

    Never raises: an unreachable service is reported as ``up: False`` rather than
    failing the request that asked about it.
    """
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(base_url)
        if cached and not force and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]
    result = _probe_all(base_url)
    with _cache_lock:
        _cache[base_url] = (now, result)
    return result


def clear_cache() -> None:
    """Drop cached probes (used by tests and after a deploy)."""
    with _cache_lock:
        _cache.clear()
