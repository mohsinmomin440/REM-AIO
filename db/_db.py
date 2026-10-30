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
    _instance: Optional["Database"] = None
    _lock: asyncio.Lock
    db_path: str
    db: Optional[aiosqlite.Connection]

    def __new__(cls, db_path_name: str = "anti.db"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.db_path = str(db_path(db_path_name))
            cls._instance.db = None
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    async def connect(self, timeout: float = 30) -> aiosqlite.Connection:
        async with self._lock:
            if self.db is None:
                self.db = await aiosqlite.connect(self.db_path, timeout=timeout)
                await self.db.execute("PRAGMA journal_mode=WAL")
                await self.db.execute("PRAGMA busy_timeout=5000")
                await self.db.execute("PRAGMA foreign_keys=ON")
                await self.db.commit()
        return self.db

    async def ensure_connection(self) -> aiosqlite.Connection:
        if self.db is None:
            await self.connect()
        return self.db  # type: ignore[return-value]

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
            if self.db is not None:
                await self.db.close()
                self.db = None