#!/usr/bin/env python3
"""Seed admin user from environment variables."""
import asyncio
import os
import sys

sys.path.insert(0, "/app")

from argon2 import PasswordHasher
from sqlalchemy import select
from src.db import AsyncSessionLocal
from src.models.admin import Admin


async def main():
    email = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "admin@example.com")
    password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "admin123")

    ph = PasswordHasher()
    password_hash = ph.hash(password)

    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(Admin).where(Admin.email == email))
        if existing.scalar_one_or_none():
            print(f"Admin {email} already exists, skipping.")
            return

        admin = Admin(email=email, password_hash=password_hash)
        session.add(admin)
        await session.commit()
        print(f"Admin {email} created successfully.")


if __name__ == "__main__":
    asyncio.run(main())
