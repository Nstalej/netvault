"""
NetVault - Database Connection Manager & Migrations
"""
import aiosqlite
import logging
import os
from pathlib import Path
from typing import Optional, List, Any, Dict
from core.database.models import SCHEMA_SQL, INITIAL_SQL

logger = logging.getLogger("netvault.db")

class DatabaseManager:
    """Asynchronous SQLite connection manager with migration support"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Establish connection and ensure path exists"""
        db_dir = Path(self.db_path).parent
        if not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)
            
        if self._connection is None:
            self._connection = await aiosqlite.connect(self.db_path)
            self._connection.row_factory = aiosqlite.Row
            logger.info(f"Connected to database: {self.db_path}")
            
            # Auto-initialize and migrate
            await self._initialize()

    async def disconnect(self):
        """Close the database connection"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Database connection closed")

    async def _initialize(self):
        """Initialize schema and run migrations"""
        # Execute base schema
        await self._connection.executescript(SCHEMA_SQL)
        await self._connection.executescript(INITIAL_SQL)
        await self._connection.commit()
        
        # Check version and run migrations if needed
        version = await self.get_version()
        logger.info(f"Database version: {version}")
        
        # Simple migration logic (extendable in future phases)
        await self._migrate(version)

    async def get_version(self) -> int:
        """Get current database version from sys_config"""
        async with self._connection.execute(
            "SELECT value FROM sys_config WHERE key = 'db_version'"
        ) as cursor:
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

    async def _migrate(self, current_version: int):
        """Run version-based migrations"""
        # Example for future migrations:
        # if current_version < 2:
        #     await self._connection.execute("ALTER TABLE ...")
        #     await self._connection.execute("UPDATE sys_config SET value = '2' WHERE key = 'db_version'")
        pass

    async def execute(self, query: str, parameters: tuple = ()) -> Any:
        """Execute a single query (INSERT, UPDATE, DELETE)"""
        if not self._connection:
            await self.connect()
        async with self._connection.execute(query, parameters) as cursor:
            await self._connection.commit()
            return cursor.lastrowid

    async def fetch_one(self, query: str, parameters: tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch a single row as a dictionary"""
        if not self._connection:
            await self.connect()
        async with self._connection.execute(query, parameters) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(self, query: str, parameters: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all matching rows as a list of dictionaries"""
        if not self._connection:
            await self.connect()
        async with self._connection.execute(query, parameters) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
