"""
Create the initial NetVault admin user.

Usage:
  python scripts/create_admin.py
"""

import asyncio

from core.config import get_config
from core.database import crud
from core.database.db import DatabaseManager
from core.database.models import UserRole
from core.security import get_password_hash


async def create_initial_admin() -> None:
    settings = get_config()
    db = DatabaseManager(settings.database.db_path)
    await db.connect()

    try:
        existing = await crud.get_user_by_email(db, "admin@netvault.local")
        if existing:
            print("Admin user already exists.")
            return

        await crud.create_user(
            db,
            email="admin@netvault.local",
            hashed_password=get_password_hash("NetVault2025!"),
            full_name="NetVault Admin",
            role=UserRole.ADMIN.value,
            locale="en",
        )
        print("Admin created: admin@netvault.local / NetVault2025!")
        print("Change the default password after first login.")
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(create_initial_admin())
