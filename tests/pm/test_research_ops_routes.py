"""CRUD + auth smoke tests for grants, conferences, and IRB routes."""
from __future__ import annotations


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_project(client, admin_token: str) -> str:
    resp = client.post("/api/v1/projects", json={"name": "Host"}, headers=_auth(admin_token))
    assert resp.status_code == 201
    return resp.json()["id"]


# --- grants ---------------------------------------------------------------

def test_grant_crud_round_trip(client, admin_token) -> None:
    created = client.post(
        "/api/v1/grants",
        json={"title": "R01", "funder": "NIH", "amount_awarded": 50000},
        headers=_auth(admin_token),
    )
    assert created.status_code == 201
    gid = created.json()["id"]

    got = client.get(f"/api/v1/grants/{gid}", headers=_auth(admin_token))
    assert got.status_code == 200
    assert got.json()["title"] == "R01"
    assert got.json()["funder"] == "NIH"

    updated = client.put(f"/api/v1/grants/{gid}", json={"status": "awarded"}, headers=_auth(admin_token))
    assert updated.status_code == 200

    assert any(g["id"] == gid for g in client.get("/api/v1/grants", headers=_auth(admin_token)).json())

    assert client.delete(f"/api/v1/grants/{gid}", headers=_auth(admin_token)).status_code == 204
    assert client.get(f"/api/v1/grants/{gid}", headers=_auth(admin_token)).status_code == 404


def test_grant_requires_auth(client) -> None:
    assert client.get("/api/v1/grants").status_code == 401


# --- conferences ----------------------------------------------------------

def test_conference_crud_round_trip(client, admin_token) -> None:
    created = client.post(
        "/api/v1/conferences",
        json={"name": "NeurIPS 2026", "venue": "San Diego", "presentation_type": "oral"},
        headers=_auth(admin_token),
    )
    assert created.status_code == 201
    cid = created.json()["id"]

    got = client.get(f"/api/v1/conferences/{cid}", headers=_auth(admin_token))
    assert got.status_code == 200
    assert got.json()["name"] == "NeurIPS 2026"

    assert client.put(f"/api/v1/conferences/{cid}", json={"status": "submitted"}, headers=_auth(admin_token)).status_code == 200
    assert client.delete(f"/api/v1/conferences/{cid}", headers=_auth(admin_token)).status_code == 204
    assert client.get(f"/api/v1/conferences/{cid}", headers=_auth(admin_token)).status_code == 404


def test_conference_requires_auth(client) -> None:
    assert client.get("/api/v1/conferences").status_code == 401


# --- IRB ------------------------------------------------------------------

def test_irb_crud_round_trip(client, admin_token) -> None:
    # Updated 2026-08-20 for the IRB lockdown: an IRB is born draft/submitted,
    # approval is an admin transition FROM submitted WITH evidence (dates+docs),
    # and the record is append-only forever — delete answers 403 and the row
    # stays. The old version of this test encoded the self-service hole as the
    # expected behaviour. Deep coverage lives in test_api_irb_lockdown.py.
    project_id = _make_project(client, admin_token)
    created = client.post(
        "/api/v1/irb",
        json={
            "project_id": project_id,
            "institution": "Bogazici University",
            "protocol_number": "2026-42",
            "title": "Human subjects study",
            "status": "submitted",
        },
        headers=_auth(admin_token),
    )
    assert created.status_code == 201
    iid = created.json()["id"]

    got = client.get(f"/api/v1/irb/{iid}", headers=_auth(admin_token))
    assert got.status_code == 200
    assert got.json()["protocol_number"] == "2026-42"

    # approval without evidence is refused; with evidence it lands and is attributed
    assert client.put(f"/api/v1/irb/{iid}", json={"status": "approved"}, headers=_auth(admin_token)).status_code == 409
    approved = client.put(
        f"/api/v1/irb/{iid}",
        json={"status": "approved", "approval_date": "2026-08-01",
              "expiry_date": "2030-01-01", "documents": ["protocol.pdf"]},
        headers=_auth(admin_token),
    )
    assert approved.status_code == 200
    assert approved.json()["approved_by"]

    # append-only: no deletion, ever — close it instead
    assert client.delete(f"/api/v1/irb/{iid}", headers=_auth(admin_token)).status_code == 403
    assert client.get(f"/api/v1/irb/{iid}", headers=_auth(admin_token)).status_code == 200
    assert client.put(f"/api/v1/irb/{iid}", json={"status": "closed"}, headers=_auth(admin_token)).status_code == 200


def test_irb_requires_auth(client) -> None:
    assert client.get("/api/v1/irb").status_code == 401
