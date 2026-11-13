from dataclasses import dataclass
from typing import Annotated
from uuid import UUID
from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.auth_session import AuthSession
from app.models.user import User
from app.core.security import decode_token, get_signing_secret

bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[Session, Depends(get_db)]


@dataclass(frozen=True)
class AuthenticatedSession:
    user: User
    session: AuthSession


def get_authenticated_session(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedSession:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        get_signing_secret()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured. Set a private JWT_SECRET first.",
        ) from exc

    try:
        claims = decode_token(credentials.credentials, expected_type="access")
        user_id = UUID(str(claims["sub"]))
        session_id = UUID(str(claims["sid"]))
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise unauthorized from None

    auth_session = db.scalar(select(AuthSession).where(AuthSession.id == session_id))
    user = db.scalar(select(User).where(User.id == user_id))
    if (
        auth_session is None
        or user is None
        or auth_session.user_id != user.id
        or auth_session.revoked_at is not None
    ):
        raise unauthorized

    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        raise unauthorized
    return AuthenticatedSession(user=user, session=auth_session)


def get_current_user(
    authenticated: Annotated[AuthenticatedSession, Depends(get_authenticated_session)],
) -> User:
    return authenticated.user
