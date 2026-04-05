"""Auth routes: login and logout."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from ...auth import create_token, verify_password
from ...crud.users import get_user_by_username
from ...db import get_db, get_db_path
from ..deps import get_current_user
from ..schemas import LoginRequest, TokenResponse

router = APIRouter()
_TOKEN_TTL_HOURS = 24


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    """Authenticate user and return session token."""
    user = get_user_by_username(get_db_path(), body.username)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    token = create_token()
    expires_at = (datetime.now(UTC) + timedelta(hours=_TOKEN_TTL_HOURS)).isoformat()
    with get_db(get_db_path()) as conn:
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
            (token, user.id, expires_at),
        )
    return TokenResponse(
        token=token, user_id=user.id, username=user.username, is_admin=user.is_admin
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user=Depends(get_current_user)):
    """Invalidate all tokens for the current user."""
    with get_db(get_db_path()) as conn:
        conn.execute("DELETE FROM auth_tokens WHERE user_id = ?", (current_user.id,))
