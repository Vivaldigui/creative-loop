"""Unit tests for security modules."""
from __future__ import annotations

import pytest

from app.security.hashing import hash_password, verify_password
from app.security.jwt import create_access_token, decode_access_token


def test_hash_and_verify():
    h = hash_password("mysecret")
    assert verify_password("mysecret", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token("user-id-123", "org-id-abc", "owner")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-id-123"
    assert payload["org"] == "org-id-abc"
    assert payload["role"] == "owner"


def test_jwt_invalid():
    with pytest.raises(ValueError):
        decode_access_token("totally.invalid.token")
