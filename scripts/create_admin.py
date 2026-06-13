#!/usr/bin/env python3
"""Create the first production organization and owner account."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import re
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT))

from app.config import get_settings  # noqa: E402
from app.models.user import Organization, User  # noqa: E402
from app.security.hashing import hash_password  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Creative Loop owner account."
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True, help="Full name of the owner")
    parser.add_argument(
        "--organization", required=True, help="Organization display name"
    )
    parser.add_argument(
        "--slug", required=True, help="Lowercase organization identifier"
    )
    return parser.parse_args()


async def create_admin(args: argparse.Namespace, password: str) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as db:
        existing_user = await db.scalar(
            select(User).where(User.email == args.email.lower())
        )
        if existing_user:
            raise SystemExit(f"User {args.email} already exists.")

        organization = await db.scalar(
            select(Organization).where(Organization.slug == args.slug)
        )
        if organization is None:
            organization = Organization(
                name=args.organization,
                slug=args.slug,
                status="active",
                metadata_={"created_by": "create_admin.py"},
            )
            db.add(organization)
            await db.flush()

        user = User(
            organization_id=organization.id,
            email=args.email.lower(),
            hashed_password=hash_password(password),
            full_name=args.name,
            role="owner",
            is_active=True,
            metadata_={"created_by": "create_admin.py"},
        )
        db.add(user)
        await db.commit()
        print(f"Owner created: {user.email} ({organization.name})")

    await engine.dispose()


def main() -> None:
    args = parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}[a-z0-9]", args.slug):
        raise SystemExit("--slug must use lowercase letters, numbers, and hyphens.")

    password = getpass.getpass("Password (minimum 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters.")

    asyncio.run(create_admin(args, password))


if __name__ == "__main__":
    main()
