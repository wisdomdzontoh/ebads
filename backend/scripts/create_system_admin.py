"""Bootstrap the first ``system_administrator`` account (docs/02 §2.3, operational necessity).

No HTTP path can create the first account: every ``/users`` route requires an existing
system_administrator or facility_administrator caller (FR16 — no self-service path grants
privilege), and registration/approval needs a system_administrator to approve it. That is
correct for every account *after* the first, but a fresh deployment starts with zero
accounts at all. This script is the one, deliberately out-of-band exception — run once
against the deployment's database, by whoever holds deploy access, not exposed over HTTP.

Idempotent by email: re-running against an existing address is a no-op unless ``--force``
resets its password (e.g. after a credential rotation).

    python -m scripts.create_system_admin --email admin@example.com --password <strong password>
"""

from __future__ import annotations

import argparse
import asyncio
import getpass

from sqlalchemy import select

from app.db.models.role import Role as RoleRow
from app.db.models.user_account import UserAccount
from app.db.session import get_engine, get_sessionmaker
from app.parameters import Role
from app.security.passwords import PasswordTooShortError, hash_password


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
        description="Bootstrap the first system_administrator account."
    )
    parser.add_argument("--email", required=True, help="Login email for the account.")
    parser.add_argument(
        "--password",
        help="Password (min 12 characters). Omit to be prompted without echoing it to the "
        "terminal/shell history.",
    )
    parser.add_argument(
        "--force", action="store_true", help="Reset the password if the account already exists."
    )
    args = parser.parse_args()
    password = args.password or getpass.getpass("Password: ")
    try:
        asyncio.run(_main(args.email, password, args.force))
    except PasswordTooShortError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
