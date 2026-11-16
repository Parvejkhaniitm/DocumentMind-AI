from uuid import uuid4

import jwt
import pytest
from pydantic import SecretStr

from app.core import security


def test_password_hash_verifies_only_the_original_password() -> None:
    encoded = security.hash_password("correct horse battery staple")

    assert encoded != "correct horse battery staple"
    assert security.verify_password("correct horse battery staple", encoded)
    assert not security.verify_password("incorrect password", encoded)


def test_access_token_round_trips_and_cannot_be_used_as_refresh_token(monkeypatch) -> None:
    monkeypatch.setattr(
        security.settings, "jwt_secret", SecretStr("test-secret-that-is-at-least-32-bytes-long")
    )
    user_id, session_id = uuid4(), uuid4()
    token = security.create_access_token(user_id=user_id, session_id=session_id)

    claims = security.decode_token(token, expected_type="access")
    assert claims["sub"] == str(user_id)
    assert claims["sid"] == str(session_id)
    with pytest.raises(jwt.InvalidTokenError):
        security.decode_token(token, expected_type="refresh")


def test_signing_rejects_placeholder_secret(monkeypatch) -> None:
    monkeypatch.setattr(
        security.settings, "jwt_secret", SecretStr("change-me-with-a-long-random-value")
    )

    with pytest.raises(ValueError, match="private random value"):
        security.get_signing_secret()


def test_refresh_token_hash_is_one_way_digest() -> None:
    token = "private-refresh-token"

    digest = security.hash_refresh_token(token)
    assert digest != token
    assert len(digest) == 64
    assert digest == security.hash_refresh_token(token)
