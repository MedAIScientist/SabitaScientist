"""Platform role from the institutional e-mail address.

At Medipol the address says who someone is:

* ``…@std.medipol.edu.tr`` — a student;
* ``…@medipol.edu.tr``     — staff, i.e. a professor (faculty member).

That rule is the source of truth for the platform roles 'student' and
'professor'. It is applied when an account is created (admin form, bulk import,
first Microsoft sign-in), on every login, and once at startup for existing
accounts — new accounts used to default to 'student', so faculty signing in with
Microsoft never became professors.

Never touched automatically: the platform role 'admin' and the is_admin flag
(those are deliberate decisions), and addresses outside the configured domains
(an admin sets those roles by hand).

Staff domains are configurable with PM_STAFF_EMAIL_DOMAINS (comma-separated;
default ``medipol.edu.tr``); the student domain of each is ``std.<domain>``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import replace
from pathlib import Path

from .db import get_db
from .models import User

logger = logging.getLogger(__name__)

_DEFAULT_STAFF_DOMAINS = "medipol.edu.tr"


def staff_domains() -> list[str]:
    raw = os.environ.get("PM_STAFF_EMAIL_DOMAINS", _DEFAULT_STAFF_DOMAINS)
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def role_for_email(email: str | None) -> str | None:
    """'student', 'professor', or None when the address says nothing."""
    if not email or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[1].strip().lower()
    for staff in staff_domains():
        if domain == f"std.{staff}":
            return "student"
        if domain == staff:
            return "professor"
    return None


def sync_role(db: Path, user: User) -> User:
    """Bring the user's role in line with their address. Returns the (possibly updated) user."""
    derived = role_for_email(user.email)
    if derived is None or user.role == "admin" or user.role == derived:
        return user
    with get_db(db) as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (derived, user.id))
    logger.info("role set from e-mail domain user=%s %s -> %s", user.id, user.role, derived)
    return replace(user, role=derived)


def sync_all_roles(db: Path) -> int:
    """Apply the rule to every account (idempotent). Returns how many changed."""
    from .crud.users import list_users

    changed = 0
    for user in list_users(db):
        if sync_role(db, user) is not user:
            changed += 1
    if changed:
        logger.info("role sync from e-mail domains: %d account(s) updated", changed)
    return changed
