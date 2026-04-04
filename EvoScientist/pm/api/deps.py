"""FastAPI dependencies for authentication and role-based access control."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from ..auth import validate_token
from ..crud.projects import get_member_role
from ..crud.users import get_user_by_id
from ..db import get_db_path
from ..models import User


def _extract_token(authorization: str = Header(...)) -> str:
    """Parse Bearer token from Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    return authorization.removeprefix("Bearer ").strip()


def get_current_user(token: str = Depends(_extract_token)) -> User:
    """Resolve the current user from the Bearer token. Raises 401 if invalid."""
    user_id = validate_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = get_user_by_id(get_db_path(), user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Raises 403 if current user is not admin."""
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_project_role(*allowed_roles: str):
    """Return a dependency that checks the caller's role in a project."""
    def _dep(project_id: str, current_user: User = Depends(get_current_user)) -> User:
        role = get_member_role(get_db_path(), project_id, current_user.id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
        if role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{role}' not permitted here")
        return current_user
    return _dep
