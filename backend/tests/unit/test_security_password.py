"""Password hashing tests (docs/09-parameters.md §10)."""

from __future__ import annotations

import pytest

from app.security.passwords import PasswordTooShortError, hash_password, verify_password


def test_hash_then_verify_round_trips() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed) is True


def test_wrong_password_does_not_verify() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("wrong-password-entirely", hashed) is False


def test_hash_is_not_the_plaintext() -> None:
    plain = "correct-horse-battery-staple"
    assert hash_password(plain) != plain


def test_short_password_is_rejected() -> None:
    with pytest.raises(PasswordTooShortError):
        hash_password("short")


def test_malformed_hash_does_not_verify() -> None:
    assert verify_password("anything", "not-a-real-argon2-hash") is False
