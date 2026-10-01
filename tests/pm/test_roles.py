"""Student vs professor follows the institutional address; only professors create labs."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from EvoScientist.pm.api.app import create_app
from EvoScientist.pm.auth import hash_password
from EvoScientist.pm.crud.users import create_user, get_user_by_id
from EvoScientist.pm.roles import role_for_email, sync_all_roles


def test_role_for_email(monkeypatch) -> None:
    monkeypatch.delenv("PM_STAFF_EMAIL_DOMAINS", raising=False)
    assert role_for_email("ayse@std.medipol.edu.tr") == "student"
    assert role_for_email("Prof.Kaya@Medipol.edu.tr") == "professor"
    assert role_for_email("someone@gmail.com") is None
    assert role_for_email("x@evil-medipol.edu.tr") is None  # look-alike domain
    assert role_for_email(None) is None
    monkeypatch.setenv("PM_STAFF_EMAIL_DOMAINS", "medipol.edu.tr, example.edu")
    assert role_for_email("a@std.example.edu") == "student"


def test_startup_sync_fixes_defaulted_roles_but_never_touches_admins(tmp_db: Path) -> None:
    prof = create_user(tmp_db, "kaya", hash_password("p"), email="kaya@medipol.edu.tr", role="student")
    stud = create_user(tmp_db, "ayse", hash_password("p"), email="ayse@std.medipol.edu.tr", role="professor")
    admin = create_user(tmp_db, "root", hash_password("p"), email="root@medipol.edu.tr", is_admin=True, role="admin")
    other = create_user(tmp_db, "guest", hash_password("p"), email="g@gmail.com", role="professor")

    assert sync_all_roles(tmp_db) == 2
    assert get_user_by_id(tmp_db, prof.id).role == "professor"
    assert get_user_by_id(tmp_db, stud.id).role == "student"
    assert get_user_by_id(tmp_db, admin.id).role == "admin"
    assert get_user_by_id(tmp_db, other.id).role == "professor"  # outside the domains: unchanged
    assert sync_all_roles(tmp_db) == 0  # idempotent


def test_login_applies_the_rule_and_only_professors_create_labs(tmp_db: Path) -> None:
    create_user(tmp_db, "kaya", hash_password("pw123456"), email="kaya@medipol.edu.tr")  # defaults to student
    create_user(tmp_db, "ayse", hash_password("pw123456"), email="ayse@std.medipol.edu.tr")
    client = TestClient(create_app(tmp_db))

    prof = client.post("/api/v1/auth/login", json={"username": "kaya", "password": "pw123456"}).json()
    assert prof["role"] == "professor"
    stud = client.post("/api/v1/auth/login", json={"username": "ayse", "password": "pw123456"}).json()
    assert stud["role"] == "student"

    r = client.post("/api/v1/labs", json={"name": "Student lab"}, headers={"Authorization": f"Bearer {stud['token']}"})
    assert r.status_code == 403
    r = client.post("/api/v1/labs", json={"name": "Retina Lab"}, headers={"Authorization": f"Bearer {prof['token']}"})
    assert r.status_code == 201
    lab = r.json()
    assert lab["pi_id"] == prof["user_id"]  # the creator leads the lab as PI
