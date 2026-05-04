import asyncio
import os
import sys

async def main():
    email = os.environ["ADMIN_BOOTSTRAP_EMAIL"]
    password = os.environ["ADMIN_BOOTSTRAP_PASSWORD"]
    db_url = os.environ["DATABASE_URL"]

    sys.path.insert(0, "/app")
    from src.models.admin import Admin
    from src.auth.utils import hash_password
    from src.db import Base
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select

    engine = create_async_engine(db_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        result = await db.execute(select(Admin).where(Admin.email == email))
        if result.scalar_one_or_none():
            print(f"Admin {email} already exists")
            return
        admin = Admin(email=email, password_hash=hash_password(password))
        db.add(admin)
        await db.commit()
        print(f"Admin {email} created")

asyncio.run(main())
