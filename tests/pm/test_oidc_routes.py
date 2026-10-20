"""Regression tests for the OIDC callback (SSO) user provisioning."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from gazzali.api.app import create_app
from gazzali.api.routes import auth_oidc as auth_oidc_mod
from gazzali.auth import hash_password
from gazzali.crud.users import (
    create_user,
    get_user_by_email,
    get_user_by_username,
)
from gazzali.oidc import OIDCUser


def _patch_oidc(monkeypatch, db_path, oidc_user):
    """Point the OIDC route at a temp DB and a fake provider response."""
    monkeypatch.setattr(auth_oidc_mod, "get_db_path", lambda: db_path)

    async def fake_exchange(code: str):
        return oidc_user

    monkeypatch.setattr(auth_oidc_mod, "exchange_code", fake_exchange)


def _callback(client: TestClient, state: str) -> TestClient.response:
    auth_oidc_mod._oidc_states[state] = "/login"
    return client.get(
        f"/api/v1/auth/oidc/callback?code=code123&state={state}",
        follow_redirects=False,
    )


def _make_client(tmp_db):
    return TestClient(create_app(tmp_db))


def test_oidc_callback_reuses_existing_user_with_same_email(tmp_db, monkeypatch):
    """Regression: a user matching by email but not by display name must not
    trigger a UNIQUE(email) violation on create."""
    create_user(
        tmp_db,
        username="Alice Local",
        password_hash=hash_password("pw"),
        email="alice@medipol.edu.tr",
    )
    oidc_user = OIDCUser(
        sub="sub-123",
        email="alice@medipol.edu.tr",
        name="Alice Yeni Isim",
        preferred_username=None,
        issuer="https://login.microsoftonline.com/tenant/v2.0",
    )
    _patch_oidc(monkeypatch, tmp_db, oidc_user)

    resp = _callback(_make_client(tmp_db), "state1")

    assert resp.status_code == 307
    assert "token=" in resp.headers["location"]
    user = get_user_by_email(tmp_db, "alice@medipol.edu.tr")
    assert user is not None
    assert user.username == "Alice Local"
    assert get_user_by_username(tmp_db, "Alice Yeni Isim") is None


def test_oidc_callback_creates_new_user(tmp_db, monkeypatch):
    oidc_user = OIDCUser(
        sub="sub-456",
        email="bob@medipol.edu.tr",
        name="Bob",
        preferred_username=None,
        issuer="https://login.microsoftonline.com/tenant/v2.0",
    )
    _patch_oidc(monkeypatch, tmp_db, oidc_user)

    resp = _callback(_make_client(tmp_db), "state2")

    assert resp.status_code == 307
    user = get_user_by_email(tmp_db, "bob@medipol.edu.tr")
    assert user is not None
    assert user.username == "Bob"


def test_oidc_callback_repeated_login_does_not_duplicate(tmp_db, monkeypatch):
    oidc_user = OIDCUser(
        sub="sub-789",
        email="carol@medipol.edu.tr",
        name="Carol",
        preferred_username=None,
        issuer="https://login.microsoftonline.com/tenant/v2.0",
    )
    _patch_oidc(monkeypatch, tmp_db, oidc_user)
    client = _make_client(tmp_db)

    resp1 = _callback(client, "state3")
    resp2 = _callback(client, "state4")

    assert resp1.status_code == 307
    assert resp2.status_code == 307
    user = get_user_by_email(tmp_db, "carol@medipol.edu.tr")
    assert user is not None
    with sqlite3.connect(tmp_db) as conn:
        (count,) = conn.execute(
            "SELECT COUNT(*) FROM users WHERE email = ?", ("carol@medipol.edu.tr",)
        ).fetchone()
    assert count == 1


# ── Reachability: configured is not the same as answering ─────────────────────
#
# The identity provider is published through a gateway that can be down while this
# application is healthy, and a user sent into a bare gateway error page cannot tell
# that a password still works.


def test_status_reports_the_provider_as_unreachable_when_it_does_not_answer(
    client, monkeypatch
) -> None:
    # The route holds its own references, which is the convention in this module.
    monkeypatch.setattr(auth_oidc_mod, "is_configured", lambda: True)
    monkeypatch.setattr(auth_oidc_mod, "is_reachable", lambda *a, **k: False)

    body = client.get("/api/v1/auth/oidc/status").json()
    assert body == {"configured": True, "reachable": False}


def test_status_says_reachable_when_the_provider_answers(client, monkeypatch) -> None:
    monkeypatch.setattr(auth_oidc_mod, "is_configured", lambda: True)
    monkeypatch.setattr(auth_oidc_mod, "is_reachable", lambda *a, **k: True)

    assert client.get("/api/v1/auth/oidc/status").json()["reachable"] is True


def test_an_unconfigured_provider_is_never_probed(client, monkeypatch) -> None:
    monkeypatch.setattr(auth_oidc_mod, "is_configured", lambda: False)
    monkeypatch.setattr(auth_oidc_mod, "is_reachable", lambda *a, **k: pytest.fail("probed anyway"))

    assert client.get("/api/v1/auth/oidc/status").json() == {"configured": False, "reachable": False}


class TestReachabilityProbe:
    def _clean(self, monkeypatch):
        import gazzali.oidc as oidc

        monkeypatch.setattr(oidc, "_reachable", None)
        monkeypatch.setattr(oidc, "_discovery_at", 0.0)
        monkeypatch.setattr(oidc, "_discovery_doc", None)
        return oidc

    def test_a_reset_tls_handshake_means_unreachable(self, monkeypatch) -> None:
        """Reproduced live: TCP connects, then the gateway resets the handshake."""
        import httpx

        oidc = self._clean(monkeypatch)
        monkeypatch.setattr(oidc, "OIDC_CONFIG", {**oidc.OIDC_CONFIG, "issuer_url": "https://idp.test/auth/"})

        def boom(*a, **k):
            raise httpx.ConnectError("Connection reset by peer")

        monkeypatch.setattr(oidc.httpx, "get", boom)
        assert oidc.is_reachable() is False

    def test_any_http_answer_counts_as_reachable(self, monkeypatch) -> None:
        """A 4xx still proves the provider is alive; only silence means down."""
        import httpx

        oidc = self._clean(monkeypatch)
        monkeypatch.setattr(oidc, "OIDC_CONFIG", {**oidc.OIDC_CONFIG, "issuer_url": "https://idp.test/auth/"})
        monkeypatch.setattr(
            oidc.httpx, "get",
            lambda *a, **k: httpx.Response(404, request=httpx.Request("GET", "https://idp.test/")),
        )
        assert oidc.is_reachable() is True

    def test_a_gateway_error_counts_as_unreachable(self, monkeypatch) -> None:
        """Observed live: nginx answered 502 for /auth/, but that is not the provider."""
        import httpx

        oidc = self._clean(monkeypatch)
        monkeypatch.setattr(oidc, "OIDC_CONFIG", {**oidc.OIDC_CONFIG, "issuer_url": "https://idp.test/auth/"})
        monkeypatch.setattr(
            oidc.httpx, "get",
            lambda *a, **k: httpx.Response(502, request=httpx.Request("GET", "https://idp.test/")),
        )
        assert oidc.is_reachable() is False

    def test_a_server_error_counts_as_unreachable(self, monkeypatch) -> None:
        import httpx

        oidc = self._clean(monkeypatch)
        monkeypatch.setattr(oidc, "OIDC_CONFIG", {**oidc.OIDC_CONFIG, "issuer_url": "https://idp.test/auth/"})
        monkeypatch.setattr(
            oidc.httpx, "get",
            lambda *a, **k: httpx.Response(503, request=httpx.Request("GET", "https://idp.test/")),
        )
        assert oidc.is_reachable() is False

    def test_the_probe_is_cached_between_calls(self, monkeypatch) -> None:
        """The login page loads often; probing it every time would add latency."""
        import httpx

        oidc = self._clean(monkeypatch)
        monkeypatch.setattr(oidc, "OIDC_CONFIG", {**oidc.OIDC_CONFIG, "issuer_url": "https://idp.test/auth/"})
        calls = {"n": 0}

        def counted(*a, **k):
            calls["n"] += 1
            return httpx.Response(200, request=httpx.Request("GET", "https://idp.test/"))

        monkeypatch.setattr(oidc.httpx, "get", counted)
        now = 1000.0
        assert oidc.is_reachable(now=now) is True
        assert oidc.is_reachable(now=now + 1) is True
        assert calls["n"] == 1

    def test_discovery_is_refetched_once_the_cached_copy_is_stale(self, monkeypatch) -> None:
        """A document cached forever would pin every authorize URL to a stale provider."""
        import httpx

        oidc = self._clean(monkeypatch)
        monkeypatch.setattr(oidc, "OIDC_CONFIG", {**oidc.OIDC_CONFIG, "issuer_url": "https://idp.test/auth/"})
        calls = {"n": 0}

        def counted(*a, **k):
            calls["n"] += 1
            return httpx.Response(
                200, json={"issuer": "https://idp.test/auth/"}, request=httpx.Request("GET", "https://idp.test/")
            )

        monkeypatch.setattr(oidc.httpx, "get", counted)
        oidc._load_discovery(now=1000.0)
        oidc._load_discovery(now=1001.0)
        assert calls["n"] == 1, "a fresh copy should be reused"
        oidc._load_discovery(now=1000.0 + oidc._DISCOVERY_TTL_S + 1)
        assert calls["n"] == 2, "a stale copy must be refetched"

    def test_a_failed_discovery_is_not_retried_on_every_request(self, monkeypatch) -> None:
        """A 10s timeout per request would make an IdP outage feel like ours."""
        oidc = self._clean(monkeypatch)
        monkeypatch.setattr(oidc, "OIDC_CONFIG", {**oidc.OIDC_CONFIG, "issuer_url": "https://idp.test/auth/"})
        calls = {"n": 0}

        def boom(*a, **k):
            calls["n"] += 1
            raise OSError("no route to host")

        monkeypatch.setattr(oidc.httpx, "get", boom)
        assert oidc._load_discovery(now=2000.0) is None
        assert oidc._load_discovery(now=2000.0 + 5) is None
        assert calls["n"] == 1, "the failure should be remembered briefly"
        assert oidc._load_discovery(now=2000.0 + oidc._DISCOVERY_FAILURE_TTL_S + 1) is None
        assert calls["n"] == 2, "but not forever"


class TestProviderIsNeverSubstituted:
    """A configured issuer is the provider. Falling back to Microsoft is not a fallback.

    Observed live while the identity gateway was down: /api/v1/login/oidc answered 307 to
    login.microsoftonline.com with client_id=medai-pm — a client Microsoft has never heard
    of — while token verification still demanded the Authentik issuer. Wrong provider, and
    an opaque error for the user.
    """

    ISSUER = "https://idp.test/auth/application/o/pm/"

    def _fresh(self, monkeypatch, issuer=ISSUER):
        import gazzali.oidc as oidc

        monkeypatch.setattr(oidc, "_discovery_doc", None)
        monkeypatch.setattr(oidc, "_discovery_at", 0.0)
        monkeypatch.setattr(oidc, "OIDC_CONFIG", {**oidc.OIDC_CONFIG, "issuer_url": issuer})
        return oidc

    def test_an_unreachable_provider_raises_instead_of_pointing_at_microsoft(
        self, monkeypatch
    ) -> None:
        oidc = self._fresh(monkeypatch)
        monkeypatch.setattr(oidc.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("reset")))

        with pytest.raises(oidc.ProviderUnavailable):
            oidc.get_authorization_url("state123")

    def test_token_and_key_endpoints_also_refuse_to_move_provider(self, monkeypatch) -> None:
        # The dangerous half: tokens would be checked against Microsoft's keys while the
        # issuer check still required Authentik, so every login would fail.
        oidc = self._fresh(monkeypatch)
        monkeypatch.setattr(oidc.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(OSError("reset")))

        with pytest.raises(oidc.ProviderUnavailable):
            oidc._token_url()
        with pytest.raises(oidc.ProviderUnavailable):
            oidc._jwks_url()

    def test_microsoft_urls_are_used_when_no_issuer_is_configured(self, monkeypatch) -> None:
        """The legacy Entra path must keep working."""
        oidc = self._fresh(monkeypatch, issuer="")
        monkeypatch.setattr(oidc, "OIDC_CONFIG", {**oidc.OIDC_CONFIG, "issuer_url": "", "tenant_id": "t-1"})

        assert oidc._authorize_url().startswith("https://login.microsoftonline.com/t-1/")
        assert oidc._token_url().startswith("https://login.microsoftonline.com/t-1/")
        assert oidc._jwks_url().startswith("https://login.microsoftonline.com/t-1/")

    def test_the_discovered_endpoints_are_used_when_the_provider_answers(self, monkeypatch) -> None:
        import httpx

        oidc = self._fresh(monkeypatch)
        monkeypatch.setattr(
            oidc.httpx, "get",
            lambda *a, **k: httpx.Response(
                200,
                json={
                    "issuer": self.ISSUER,
                    "authorization_endpoint": "https://idp.test/auth/application/o/authorize/",
                    "token_endpoint": "https://idp.test/auth/application/o/token/",
                    "jwks_uri": "https://idp.test/auth/application/o/pm/jwks/",
                },
                request=httpx.Request("GET", "https://idp.test/"),
            ),
        )

        assert oidc._authorize_url() == "https://idp.test/auth/application/o/authorize/"
        assert oidc.get_authorization_url("s").startswith(
            "https://idp.test/auth/application/o/authorize/?client_id="
        )


def test_the_login_route_reports_an_unreachable_provider_as_503(client, monkeypatch) -> None:
    """A browser hitting sign-in during an outage should get the truth, not Microsoft."""
    import gazzali.oidc as oidc

    monkeypatch.setattr(auth_oidc_mod, "is_configured", lambda: True)
    monkeypatch.setattr(
        auth_oidc_mod,
        "get_authorization_url",
        lambda state: (_ for _ in ()).throw(oidc.ProviderUnavailable("not answering")),
    )

    resp = client.get("/api/v1/login/oidc", follow_redirects=False)
    assert resp.status_code == 503
    assert "password" in resp.json()["detail"]
    # And no state is left behind for a login that cannot complete.
    assert not any(v == "/login" for v in auth_oidc_mod._oidc_states.values())


def _token_owner(tmp_db, resp) -> str:
    token = resp.headers["location"].split("token=", 1)[1]
    con = sqlite3.connect(tmp_db)
    try:
        (user_id,) = con.execute("SELECT user_id FROM auth_tokens WHERE token = ?", (token,)).fetchone()
    finally:
        con.close()
    return user_id


def _sso(email, name):
    return OIDCUser(sub=f"sub-{email}", email=email, name=name, preferred_username=None,
                    issuer="https://medai.medipol.edu.tr/auth/application/o/medai-pm/")


def test_a_display_name_never_signs_anyone_into_an_existing_account(tmp_db, monkeypatch):
    """Security: a sign-in whose e-mail is unknown but whose display name equals an existing
    username used to be logged straight into that account — an admin's included."""
    admin = create_user(tmp_db, username="Ahmet Kaplan", password_hash=hash_password("pw"),
                        email="ahmet@medipol.edu.tr", is_admin=True)
    _patch_oidc(monkeypatch, tmp_db, _sso("intruder@example.org", "Ahmet Kaplan"))

    resp = _callback(_make_client(tmp_db), "s-takeover")

    assert resp.status_code == 307
    owner = _token_owner(tmp_db, resp)
    assert owner != admin.id, "the session was issued for the existing admin account"
    newcomer = get_user_by_email(tmp_db, "intruder@example.org")
    assert newcomer is not None
    assert newcomer.id == owner
    assert not newcomer.is_admin
    assert newcomer.username == "Ahmet Kaplan (intruder@example.org)"
    assert get_user_by_username(tmp_db, "Ahmet Kaplan").email == "ahmet@medipol.edu.tr"


def test_an_account_without_email_is_never_adopted_by_a_sign_in_with_one(tmp_db, monkeypatch):
    """Local password accounts carry no e-mail (e.g. 'ahmet.kaplan'); a same-named SSO user is a
    different person until a human says otherwise."""
    local = create_user(tmp_db, username="ahmet.kaplan", password_hash=hash_password("pw"), email=None)
    _patch_oidc(monkeypatch, tmp_db, _sso("someone@medipol.edu.tr", "ahmet.kaplan"))

    owner = _token_owner(tmp_db, _callback(_make_client(tmp_db), "s-local"))

    assert owner != local.id
    assert get_user_by_username(tmp_db, "ahmet.kaplan").email is None, "the local row must stay untouched"


def test_the_disambiguated_account_is_reused_on_the_next_sign_in(tmp_db, monkeypatch):
    create_user(tmp_db, username="Ali Veli", password_hash=hash_password("pw"), email="ali1@medipol.edu.tr")
    _patch_oidc(monkeypatch, tmp_db, _sso("ali2@medipol.edu.tr", "Ali Veli"))
    client = _make_client(tmp_db)
    first = _token_owner(tmp_db, _callback(client, "s-a"))
    second = _token_owner(tmp_db, _callback(client, "s-b"))
    assert first == second


def _users(tmp_db) -> int:
    con = sqlite3.connect(tmp_db)
    try:
        return con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    finally:
        con.close()


def _tokens(tmp_db) -> int:
    con = sqlite3.connect(tmp_db)
    try:
        return con.execute("SELECT COUNT(*) FROM auth_tokens").fetchone()[0]
    finally:
        con.close()


@pytest.mark.parametrize("email", [None, ""])
def test_a_sign_in_without_email_cannot_take_over_an_admin_by_name(tmp_db, monkeypatch, email):
    """THE TAKEOVER. The bootstrap admin has no e-mail; a sign-in whose token carries none (an
    identity-provider account without an address sends an empty claim) and a display name equal
    to that username used to be signed in AS that admin. Now it is refused, and nothing is made."""
    create_user(tmp_db, username="ahmet.kaplan", password_hash=hash_password("pw"), email=None,
                is_admin=True)
    before = _users(tmp_db)
    _patch_oidc(monkeypatch, tmp_db, OIDCUser(sub="s", email=email, name="ahmet.kaplan",
                                              preferred_username=None,
                                              issuer="https://medai.medipol.edu.tr/auth/application/o/medai-pm/"))
    resp = _callback(_make_client(tmp_db), f"s-noemail-{email!r}")
    assert resp.status_code == 403, resp.text
    assert "no e-mail address" in resp.text
    assert _tokens(tmp_db) == 0, "no session was issued"
    assert _users(tmp_db) == before, "and no account was created"


def test_the_password_account_still_signs_in_through_the_form(tmp_db):
    """Refusing e-mail-less single sign-on does not touch the password door the NULL-e-mail
    accounts actually use."""
    create_user(tmp_db, username="ahmet.kaplan", password_hash=hash_password("pw"), email=None,
                is_admin=True)
    r = _make_client(tmp_db).post("/api/v1/auth/login",
                                  json={"username": "ahmet.kaplan", "password": "pw"})
    assert r.status_code == 200, r.text
