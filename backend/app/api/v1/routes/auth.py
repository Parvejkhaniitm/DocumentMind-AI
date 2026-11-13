from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import AuthenticatedSession, get_authenticated_session
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_signing_secret,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.session import get_db
from app.models.auth_session import AuthSession
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutResponse,
    RefreshRequest,
    TokenPair,
    UserCreate,
    UserRead,
)

router = APIRouter(prefix="/auth")
CurrentDb = Annotated[Session, Depends(get_db)]


def _issue_tokens(user_id: UUID, session_id: UUID, refresh_expires_at: datetime) -> TokenPair:
    try:
        access_token = create_access_token(user_id=user_id, session_id=session_id)
        refresh_token = create_refresh_token(
            user_id=user_id, session_id=session_id, expires_at=refresh_expires_at
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured. Set a private JWT_SECRET first.",
        ) from exc
    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: CurrentDb) -> User:
    user = User(
        email=str(payload.email).strip().lower(),
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        ) from exc
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: CurrentDb) -> TokenPair:
    user = db.scalar(select(User).where(User.email == str(payload.email).strip().lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.refresh_token_days)
    auth_session = AuthSession(user_id=user.id, expires_at=expires_at)
    db.add(auth_session)
    db.flush()
    try:
        tokens = _issue_tokens(user.id, auth_session.id, expires_at)
    except HTTPException:
        db.rollback()
        raise
    auth_session.refresh_token_hash = hash_refresh_token(tokens.refresh_token)
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: CurrentDb) -> TokenPair:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        get_signing_secret()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured. Set a private JWT_SECRET first.",
        ) from exc

    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
        user_id = UUID(str(claims["sub"]))
        session_id = UUID(str(claims["sid"]))
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise unauthorized from None

    now = datetime.now(timezone.utc)
    auth_session = db.scalar(select(AuthSession).where(AuthSession.id == session_id))
    if auth_session is None:
        raise unauthorized
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if (
        auth_session.user_id != user_id
        or auth_session.revoked_at is not None
        or expires_at <= now
        or auth_session.refresh_token_hash is None
        or not compare_digest(
            auth_session.refresh_token_hash, hash_refresh_token(payload.refresh_token)
        )
    ):
        raise unauthorized

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise unauthorized
    tokens = _issue_tokens(user.id, auth_session.id, expires_at)
    result = db.execute(
        update(AuthSession)
        .where(
            AuthSession.id == session_id,
            AuthSession.refresh_token_hash == hash_refresh_token(payload.refresh_token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
        .values(refresh_token_hash=hash_refresh_token(tokens.refresh_token))
    )
    if result.rowcount != 1:
        db.rollback()
        raise unauthorized
    db.commit()
    return tokens


@router.post("/logout", response_model=LogoutResponse)
def logout(
    db: CurrentDb,
    authenticated: Annotated[AuthenticatedSession, Depends(get_authenticated_session)],
) -> LogoutResponse:
    authenticated.session.revoked_at = datetime.now(timezone.utc)
    authenticated.session.refresh_token_hash = None
    db.commit()
    return LogoutResponse()


@router.get("/me", response_model=UserRead)
def get_me(
    authenticated: Annotated[AuthenticatedSession, Depends(get_authenticated_session)],
) -> User:
    return authenticated.user
