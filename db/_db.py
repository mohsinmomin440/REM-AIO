from __future__ import annotations

import asyncio
import logging
import random
from typing import Callable, Optional, TypeVar

import aiosqlite

from utils.database import db_path

log = logging.getLogger(__name__)
T = TypeVar("T")


class Database:
    """Per-database connection manager. Not a singleton - each database gets its own instance."""

    def __init__(self, db_path_name: str = "anti.db"):
        self.db_path = str(db_path(db_path_name))
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self, timeout: float = 30) -> aiosqlite.Connection:
        async with self._lock:
            if self._db is None:
                self._db = await aiosqlite.connect(self.db_path, timeout=timeout)
                await self._db.execute("PRAGMA journal_mode=WAL")
                await self._db.execute("PRAGMA busy_timeout=5000")
                await self._db.execute("PRAGMA foreign_keys=ON")
                await self._db.commit()
        return self._db

    async def ensure_connection(self) -> aiosqlite.Connection:
        if self._db is None:
            await self.connect()
        return self._db  # type: ignore[return-value]

    async def execute_with_retries(
        self,
        func: Callable[[], T],
        retries: int = 5,
        delay: float = 1,
    ) -> T:
        for attempt in range(retries):
            try:
                return await func()
            except aiosqlite.OperationalError as exc:
                if "database is locked" not in str(exc).lower():
                    raise
                sleep_time = delay * (2 ** attempt) + random.uniform(0, 1)
                log.warning("Database locked — retrying in %.2fs", sleep_time)
                await asyncio.sleep(sleep_time)
        raise RuntimeError("Database operation failed after max retries.")

    async def close(self) -> None:
        async with self._lock:
            if self._db is not None:
                await self._db.close()
                self._db = None