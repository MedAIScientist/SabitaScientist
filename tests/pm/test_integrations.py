"""Tests for the companion-app launcher: probe logic and the /integrations route."""

from __future__ import annotations

import httpx
import pytest

from EvoScientist.pm import integrations

CVAT = next(i for i in integrations.INTEGRATIONS if i.key == "cvat")
AUTH = next(i for i in integrations.INTEGRATIONS if i.key == "auth")


class _Resp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


class _Client:
    """Minimal httpx.Client stand-in that records the URLs it was asked for."""

    def __init__(self, response):
        self.response = response
        self.requested: list[str] = []

    def get(self, url: str):
        self.requested.append(url)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture(autouse=True)
def _clear_probe_cache():
    integrations.clear_cache()
    yield
    integrations.clear_cache()


# ── Probe classification ──────────────────────────────────────────────────────


def test_service_page_is_up() -> None:
    client = _Client(_Resp(200, "<title>Computer Vision Annotation Tool</title>"))
    result = integrations._probe(client, "https://medai.test", CVAT)
    assert result["up"] is True
    assert result["http_status"] == 200
    assert client.requested == ["https://medai.test/cvat/"]
    assert result["latency_ms"] >= 0


def test_own_spa_answer_counts_as_down() -> None:
    """The false-positive trap: an unrouted subpath serves Medai's HTML with a 200."""
    client = _Client(_Resp(200, "<title>Gazzali PM</title>"))
    result = integrations._probe(client, "https://medai.test", CVAT)
    assert result["up"] is False
    assert result["http_status"] == 200  # the status alone would have looked fine


def test_redirect_to_a_login_page_is_up() -> None:
    # JupyterHub and Authentik both answer 302 before showing anything.
    client = _Client(_Resp(302, ""))
    assert integrations._probe(client, "https://medai.test", CVAT)["up"] is True


def test_auth_challenge_is_up() -> None:
    for status in (401, 403):
        client = _Client(_Resp(status, ""))
        assert integrations._probe(client, "https://medai.test", CVAT)["up"] is True


def test_server_error_is_down() -> None:
    client = _Client(_Resp(502, "<html>bad gateway</html>"))
    assert integrations._probe(client, "https://medai.test", CVAT)["up"] is False


def test_missing_path_is_down() -> None:
    client = _Client(_Resp(404, "not found"))
    assert integrations._probe(client, "https://medai.test", CVAT)["up"] is False


def test_connection_failure_is_down_not_an_exception() -> None:
    client = _Client(httpx.ConnectError("refused"))
    result = integrations._probe(client, "https://medai.test", CVAT)
    assert result["up"] is False
    assert result["http_status"] is None


# ── Cache ─────────────────────────────────────────────────────────────────────


def test_probes_are_cached_between_calls(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_probe_all(base_url):
        calls["n"] += 1
        return [
            {
                "key": i.key,
                "name": i.name,
                "path": i.path,
                "kind": i.kind,
                "description": i.description,
                "up": True,
                "http_status": 200,
                "latency_ms": 1,
            }
            for i in integrations.INTEGRATIONS
        ]

    monkeypatch.setattr(integrations, "_probe_all", fake_probe_all)
    first = integrations.statuses("https://medai.test")
    second = integrations.statuses("https://medai.test")
    assert calls["n"] == 1
    assert first == second
    # force bypasses the cache
    integrations.statuses("https://medai.test", force=True)
    assert calls["n"] == 2


def test_cache_is_keyed_by_base_url(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_probe_all(base_url):
        calls["n"] += 1
        return []

    monkeypatch.setattr(integrations, "_probe_all", fake_probe_all)
    integrations.statuses("https://a.test")
    integrations.statuses("https://b.test")
    assert calls["n"] == 2


# ── Base URL resolution ───────────────────────────────────────────────────────


class _Req:
    """Stands in for a Starlette Request (whose URL.netloc is a str, unlike httpx's)."""

    def __init__(self, scheme="http", netloc="localhost:7860", headers=None):
        from starlette.datastructures import URL

        self.url = URL(f"{scheme}://{netloc}/api/v1/integrations")
        self.headers = headers or {}


def test_base_url_prefers_forwarded_proto() -> None:
    """nginx terminates TLS; without this the probe would hit the http listener,
    which 301s every path and would report every service up."""
    req = _Req(headers={"x-forwarded-proto": "https", "host": "medai.medipol.edu.tr"})
    assert integrations.resolve_base_url(req) == "https://medai.medipol.edu.tr"


def test_base_url_falls_back_to_the_request() -> None:
    req = _Req(scheme="http", netloc="127.0.0.1:7860")
    assert integrations.resolve_base_url(req) == "http://127.0.0.1:7860"


def test_base_url_takes_the_first_forwarded_value() -> None:
    req = _Req(headers={"x-forwarded-proto": "https,http", "host": "medai.test"})
    assert integrations.resolve_base_url(req) == "https://medai.test"


# ── Route ─────────────────────────────────────────────────────────────────────


def _fake_probe_all(base_url):
    return [
        {
            "key": i.key,
            "name": i.name,
            "path": i.path,
            "kind": i.kind,
            "description": i.description,
            "up": i.key == "cvat",
            "http_status": 200 if i.key == "cvat" else 502,
            "latency_ms": 12,
        }
        for i in integrations.INTEGRATIONS
    ]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_user(client, tmp_db, username, password="pw", is_admin=False):
    from EvoScientist.pm.auth import hash_password
    from EvoScientist.pm.crud.users import create_user

    create_user(
        tmp_db,
        username=username,
        password_hash=hash_password(password),
        is_admin=is_admin,
    )
    return client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    ).json()["token"]


def test_route_lists_apps_with_status(client, tmp_db, monkeypatch) -> None:
    # The route module imported `statuses` by name, so patch it there.
    import EvoScientist.pm.api.routes.integrations as route_mod

    monkeypatch.setattr(route_mod, "statuses", _fake_probe_all)
    token = _make_user(client, tmp_db, "app_user")

    resp = client.get("/api/v1/integrations", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    keys = [row["key"] for row in body]
    assert keys == ["cvat", "curator", "jupyter"]

    cvat = next(row for row in body if row["key"] == "cvat")
    assert cvat["up"] is True
    assert cvat["http_status"] == 200
    assert cvat["path"] == "/cvat/"
    curator = next(row for row in body if row["key"] == "curator")
    assert curator["up"] is False
    assert curator["http_status"] == 502


def test_identity_provider_is_hidden_from_non_admins(
    client, tmp_db, monkeypatch
) -> None:
    import EvoScientist.pm.api.routes.integrations as route_mod

    monkeypatch.setattr(route_mod, "statuses", _fake_probe_all)
    user_token = _make_user(client, tmp_db, "plain_user")
    admin_token = _make_user(client, tmp_db, "admin_user", is_admin=True)

    plain = client.get("/api/v1/integrations", headers=_auth(user_token)).json()
    assert "auth" not in [row["key"] for row in plain]

    admin = client.get("/api/v1/integrations", headers=_auth(admin_token)).json()
    assert "auth" in [row["key"] for row in admin]


def test_route_requires_authentication(client) -> None:
    assert client.get("/api/v1/integrations").status_code == 401
