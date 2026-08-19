"""Password hashing — argon2id (docs/09-parameters.md §10).

Thin wrapper over ``argon2-cffi`` so the rest of the codebase never imports the library
directly and the hashing scheme stays a one-place change.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.parameters import MIN_PASSWORD_LENGTH

_hasher = PasswordHasher()


class PasswordTooShortError(ValueError):
    """Raised when a candidate password is shorter than ``MIN_PASSWORD_LENGTH``."""


def hash_password(plain: str) -> str:
    """Hash ``plain`` with argon2id, enforcing ``MIN_PASSWORD_LENGTH`` first."""
    if len(plain) < MIN_PASSWORD_LENGTH:
        raise PasswordTooShortError(
            f"password must be at least {MIN_PASSWORD_LENGTH} characters"
        )
    return _hasher.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    """Return True if ``plain`` matches ``password_hash``; never raises on mismatch.

    ``VerificationError`` covers a wrong password; ``InvalidHashError`` covers a stored
    hash that is not valid argon2id output — both mean "not authenticated", not a crash.
    """
    try:
        return _hasher.verify(password_hash, plain)
    except (VerificationError, InvalidHashError):
        return False
