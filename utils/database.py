from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

log = logging.getLogger(__name__)

DB_DIR = Path("db")


def db_path(name: str) -> Path:
    path = Path(name)
    if path.parent == Path("."):
        return DB_DIR / path.name
    return path


@asynccontextmanager
async def connect(
    name: str,
    *,
    timeout: float = 30.0,
    wal: bool = True,
) -> AsyncIterator[aiosqlite.Connection]:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    path = db_path(name)
    async with aiosqlite.connect(path, timeout=timeout) as db:
        if wal:
            await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db


async def execute_many(name: str, statements: list[str]) -> None:
    async with connect(name) as db:
        for statement in statements:
            await db.execute(statement)
        await db.commit()


async def open_connection(
    name: str,
    *,
    timeout: float = 30.0,
    wal: bool = True,
) -> aiosqlite.Connection:
    """Open a long-lived connection for cogs that keep `self.db` across requests."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    path = db_path(name)
    db = await aiosqlite.connect(path, timeout=timeout)
    if wal:
        await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


# Module-level cache of per-database instances
_database_instances: dict[str, "Database"] = {}


async def get_database(name: str = "anti.db") -> aiosqlite.Connection:
    """Get or create a Database instance for the given database name and return its connection."""
    from db._db import Database

    if name not in _database_instances:
        _database_instances[name] = Database(name)
    return await _database_instances[name].ensure_connection()


async def get_anti_db() -> aiosqlite.Connection:
    """Backward compatibility: return connection for anti.db."""
    return await get_database("anti.db")


async def close_shared_databases() -> None:
    """Close all long-lived shared database handles."""
    from db._db import Database
    for instance in _database_instances.values():
        await instance.close()
    _database_instances.clear()