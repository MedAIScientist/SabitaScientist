"""FastAPI dependencies for authentication and role-based access control."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from ..auth import validate_token
from ..crud.labs import get_member_role as get_lab_member_role
from ..crud.projects import get_member_role
from ..crud.users import get_user_by_id
from ..db import get_db_path
from ..models import User


def _extract_token(authorization: str | None = Header(default=None)) -> str:
    """Parse Bearer token from Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    return authorization.removeprefix("Bearer ").strip()


def get_current_user(token: str = Depends(_extract_token)) -> User:
    """Resolve the current user from the Bearer token. Raises 401 if invalid."""
    user_id = validate_token(token, get_db_path())
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    user = get_user_by_id(get_db_path(), user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Raises 403 if current user is not admin."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


def require_role(*allowed_roles: str):
    """Return a dependency that checks the caller's platform role.

    Platform admin (``is_admin``) always passes. Roles are the academic
    supervision roles on ``users.role``: admin | professor | student.
    """

    def _dep(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_admin:
            return current_user
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' not permitted here",
            )
        return current_user

    return _dep


def require_project_role(*allowed_roles: str):
    """Return a dependency that checks the caller's role in a project.

    Returns 404 for non-members (same as "project not found") to avoid leaking
    project existence to unauthenticated or non-member users.
    """

    def _dep(project_id: str, current_user: User = Depends(get_current_user)) -> User:
        role = get_member_role(get_db_path(), project_id, current_user.id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' not permitted here",
            )
        return current_user

    return _dep


def _is_lab_pi(lab_id: str, user_id: str) -> bool:
    from ..db import get_db

    with get_db(get_db_path()) as conn:
        row = conn.execute("SELECT 1 FROM labs WHERE id = ? AND pi_id = ?", (lab_id, user_id)).fetchone()
    return row is not None


def require_lab_role(*allowed_roles: str):
    """Return a dependency that checks the caller's role in a lab.

    Mirrors require_project_role(), with three deliberate differences:

    * The role comes from ``lab_members`` (crud.labs.get_member_role), not
      ``project_members``.
    * A platform admin (``is_admin``) is always allowed, member or not — the
      platform admin is the superuser across this whole platform.
    * A non-member gets 403, not 404. Labs are already listable by any
      authenticated user (``GET /labs``), so hiding their existence here would
      be theatre; the detail names the requirement instead.
    """

    def _dep(lab_id: str, current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_admin:
            return current_user
        role = get_lab_member_role(get_db_path(), lab_id, current_user.id)
        if role is None and _is_lab_pi(lab_id, current_user.id):
            role = "pi"  # PI recorded only as labs.pi_id (e.g. an admin created the lab)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"lab membership required ({' or '.join(allowed_roles)})",
            )
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' not permitted here",
            )
        return current_user

    return _dep


def require_lab_member():
    """Return a dependency that requires lab membership in any role.

    For read-ish lab endpoints (wiki, research impact): every role in
    ``lab_members`` is accepted, a platform admin is always allowed, and a
    non-member gets 403 with the requirement named — same reasoning as
    require_lab_role().
    """

    def _dep(lab_id: str, current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_admin:
            return current_user
        role = get_lab_member_role(get_db_path(), lab_id, current_user.id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="lab membership required (any role)",
            )
        return current_user

    return _dep
