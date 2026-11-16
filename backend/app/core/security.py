from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

ALGORITHM = "HS256"
ISSUER = "documind-ai"
AUDIENCE = "documind-api"
password_hash = PasswordHash.recommended()


def get_signing_secret() -> str:
    configured = settings.jwt_secret.get_secret_value() if settings.jwt_secret else ""
    if len(configured) < 32 or configured.startswith("change-me"):
        raise ValueError("Set JWT_SECRET to a private random value of at least 32 characters.")
    return configured


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    return password_hash.verify(password, encoded_hash)


def hash_refresh_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _create_token(*, user_id: UUID, session_id: UUID, token_type: str, expires_at: datetime) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "sid": str(session_id),
        "typ": token_type,
        "jti": str(uuid4()),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(claims, get_signing_secret(), algorithm=ALGORITHM)


def create_access_token(*, user_id: UUID, session_id: UUID) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_minutes)
    return _create_token(
        user_id=user_id, session_id=session_id, token_type="access", expires_at=expires_at
    )


def create_refresh_token(*, user_id: UUID, session_id: UUID, expires_at: datetime) -> str:
    return _create_token(
        user_id=user_id, session_id=session_id, token_type="refresh", expires_at=expires_at
    )


def decode_token(token: str, *, expected_type: str) -> dict[str, object]:
    claims = jwt.decode(
        token,
        get_signing_secret(),
        algorithms=[ALGORITHM],
        audience=AUDIENCE,
        issuer=ISSUER,
        options={"require": ["sub", "sid", "typ", "jti", "iat", "exp"]},
    )
    if claims.get("typ") != expected_type:
        raise jwt.InvalidTokenError("Unexpected token type.")
    UUID(str(claims["sub"]))
    UUID(str(claims["sid"]))
    return claims
