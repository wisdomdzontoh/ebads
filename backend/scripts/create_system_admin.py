"""Bootstrap the first ``system_administrator`` account (docs/02 §2.3, operational necessity).

No HTTP path can create the first account: every ``/users`` route requires an existing
system_administrator or facility_administrator caller (FR16 — no self-service path grants
privilege), and registration/approval needs a system_administrator to approve it. That is
correct for every account *after* the first, but a fresh deployment starts with zero
accounts at all. This script is the one, deliberately out-of-band exception — run once
against the deployment's database, by whoever holds deploy access, not exposed over HTTP.

Idempotent by email: re-running against an existing address is a no-op unless ``--force``
resets its password (e.g. after a credential rotation).

    python -m scripts.create_system_admin --email admin@ebads-hq.com --password <strong password>

Also runnable bare (no flags) as an unconditional step in a container's start command, for
platforms with no shell/exec access (e.g. Render's free tier — DEPLOYMENT.md). In that mode
it reads ``SEED_ADMIN_EMAIL``/``SEED_ADMIN_PASSWORD`` instead of prompting, and exits 0 as a
no-op if neither is set, so it is always safe to chain into ``CMD`` — see backend/Dockerfile.
Seeding never overwrites an existing account's password (no ``--force``), so rotating the
password afterward through any other path sticks across redeploys.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from app.db.models.role import Role as RoleRow
from app.db.models.user_account import UserAccount
from app.db.session import get_engine, get_sessionmaker
from app.parameters import Role
from app.security.passwords import PasswordTooShortError, hash_password

# Same check the /auth/login schema applies (app/api/schemas/auth.py::LoginRequest.email) —
# validating here, not just accepting any string, stops this script from ever bootstrapping
# an account that Pydantic's EmailStr would then refuse to let log in.
_EMAIL_ADAPTER: TypeAdapter[str] = TypeAdapter(EmailStr)


async def _create_or_update(email: str, password: str, force: bool) -> str:
    async with get_sessionmaker()() as session:
        role_row = await session.scalar(
            select(RoleRow).where(RoleRow.name == Role.SYSTEM_ADMINISTRATOR)
        )
        if role_row is None:
            raise RuntimeError(
                "role 'system_administrator' is not seeded — run migrations first "
                "(alembic upgrade head)"
            )

        existing = await session.scalar(select(UserAccount).where(UserAccount.email == email))
        if existing is not None:
            if not force:
                return f"{email} already exists — pass --force to reset its password"
            existing.password_hash = hash_password(password)
            await session.commit()
            return f"password reset for existing system_administrator {email}"

        user = UserAccount(
            email=email,
            password_hash=hash_password(password),
            role_id=role_row.id,
            facility_id=None,
        )
        session.add(user)
        await session.commit()
        return f"created system_administrator {email}"


async def _main(email: str, password: str, force: bool) -> None:
    message = await _create_or_update(email, password, force)
    await get_engine().dispose()
    print(message)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap the first system_administrator account. Bare invocation (no "
        "flags) reads SEED_ADMIN_EMAIL/SEED_ADMIN_PASSWORD and no-ops if neither is set."
    )
    parser.add_argument(
        "--email", help="Login email for the account. Falls back to $SEED_ADMIN_EMAIL."
    )
    parser.add_argument(
        "--password",
        help="Password (min 12 characters). Falls back to $SEED_ADMIN_PASSWORD; with neither "
        "and --email given explicitly, you are prompted without it echoing to the terminal.",
    )
    parser.add_argument(
        "--force", action="store_true", help="Reset the password if the account already exists."
    )
    args = parser.parse_args()
    # True for a human running this deliberately; False for an unconditional container CMD step.
    explicit = args.email is not None

    email_raw = args.email or os.environ.get("SEED_ADMIN_EMAIL")
    if not email_raw:
        print("SEED_ADMIN_EMAIL not set and --email not given; skipping system admin seed")
        return
    try:
        email = _EMAIL_ADAPTER.validate_python(email_raw)
    except ValidationError as exc:
        raise SystemExit(f"invalid email address {email_raw!r}: {exc.errors()[0]['msg']}") from exc

    password = args.password or os.environ.get("SEED_ADMIN_PASSWORD")
    if not password:
        if not explicit:
            raise SystemExit(
                "SEED_ADMIN_EMAIL is set but SEED_ADMIN_PASSWORD is not — set both or neither"
            )
        password = getpass.getpass("Password: ")

    try:
        asyncio.run(_main(email, password, args.force))
    except PasswordTooShortError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
