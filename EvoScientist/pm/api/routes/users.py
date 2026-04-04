"""User management routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth import hash_password
from ...crud.users import (
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    update_user_password,
)
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_admin
from ..schemas import UpdatePasswordRequest, UserCreate, UserResponse

router = APIRouter()


def _to_response(u: User) -> UserResponse:
    return UserResponse(id=u.id, username=u.username, email=u.email, is_admin=u.is_admin, created_at=u.created_at)


@router.get("", response_model=list[UserResponse])
def list_all_users(_admin: User = Depends(require_admin)):
    """List all users (admin only)."""
    return [_to_response(u) for u in list_users(get_db_path())]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_new_user(body: UserCreate, _admin: User = Depends(require_admin)):
    """Create a new user (admin only)."""
    try:
        user = create_user(get_db_path(), username=body.username, password_hash=hash_password(body.password), email=body.email)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists") from exc
    return _to_response(user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return _to_response(current_user)


@router.put("/me", response_model=UserResponse)
def update_me(body: UpdatePasswordRequest, current_user: User = Depends(get_current_user)):
    """Update own password."""
    update_user_password(get_db_path(), current_user.id, hash_password(body.new_password))
    updated = get_user_by_id(get_db_path(), current_user.id)
    return _to_response(updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_user(user_id: str, _admin: User = Depends(require_admin)):
    """Delete a user (admin only)."""
    if not delete_user(get_db_path(), user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
