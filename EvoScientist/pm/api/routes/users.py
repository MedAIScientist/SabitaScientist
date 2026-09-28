"""User management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...auth import hash_password
from ...crud.users import (
    create_user,
    delete_user,
    get_user_by_id,
    list_users,
    search_users,
    update_user_password,
)
from ...db import get_db_path
from ...models import User
from ..deps import get_current_user, require_admin
from ..schemas import (
    UpdatePasswordRequest,
    UserCreate,
    UserResponse,
    UserSearchResult,
    UserUpdate,
)

router = APIRouter()


def _to_response(u: User) -> UserResponse:
    return UserResponse(
        id=u.id,
        username=u.username,
        email=u.email,
        is_admin=u.is_admin,
        created_at=u.created_at,
    )


@router.get("", response_model=list[UserResponse])
def list_all_users(_admin: User = Depends(require_admin)):
    """List all users (admin only)."""
    return [_to_response(u) for u in list_users(get_db_path()) if not u.username.startswith("_")]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_new_user(body: UserCreate, _admin: User = Depends(require_admin)):
    """Create a new user (admin only)."""
    try:
        user = create_user(
            get_db_path(),
            username=body.username,
            password_hash=hash_password(body.password),
            email=body.email,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already exists"
        ) from exc
    return _to_response(user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return _to_response(current_user)


@router.put("/me", response_model=UserResponse)
def update_me(
    body: UpdatePasswordRequest, current_user: User = Depends(get_current_user)
):
    """Update own password."""
    update_user_password(
        get_db_path(), current_user.id, hash_password(body.new_password)
    )
    updated = get_user_by_id(get_db_path(), current_user.id)
    return _to_response(updated)


@router.get("/search", response_model=list[UserSearchResult])
def search_users_endpoint(
    q: str = Query(default="", max_length=64),
    _current_user: User = Depends(get_current_user),
):
    """Search users by username substring. Accessible to any authenticated user."""
    if len(q) < 1:
        return []
    return [
        UserSearchResult(id=u.id, username=u.username)
        for u in search_users(get_db_path(), q)
    ]


@router.put("/{user_id}", response_model=UserResponse)
def update_existing_user(
    user_id: str,
    body: UserUpdate,
    _admin: User = Depends(require_admin),
):
    """Update user info (admin only)."""
    from ...crud.users import update_user

    user = update_user(
        get_db_path(),
        user_id=user_id,
        username=body.username,
        email=body.email,
        is_admin=body.is_admin,
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_response(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_user(user_id: str, _admin: User = Depends(require_admin)):
    """Delete a user (admin only)."""
    from ...platform_push import push_researcher

    db = get_db_path()
    # The address has to be read BEFORE the delete: it is the key the platform
    # holds this person's entitlements under, and deleting the row takes it
    # away. The push that follows says "no projects", which is what strips
    # their access at the next session mint.
    gone = get_user_by_id(db, user_id)
    email = gone.email if gone else None
    if not delete_user(db, user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if email:
        push_researcher(db, email)


@router.get("/setup/status")
def setup_status():
    """Return whether the system has been bootstrapped (any users exist)."""
    users = list_users(get_db_path())
    return {"needs_setup": len(users) == 0}


@router.post(
    "/setup/admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def create_admin(body: UserCreate):
    """Create the first admin account. Returns 409 if any users already exist."""
    if list_users(get_db_path()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="System already bootstrapped"
        )
    user = create_user(
        get_db_path(),
        username=body.username,
        password_hash=hash_password(body.password),
        email=body.email,
        is_admin=True,
    )
    return _to_response(user)
