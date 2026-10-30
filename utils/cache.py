from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Small in-memory TTL cache for hot-path lookups."""

    __slots__ = ("_ttl", "_maxsize", "_data", "_lock")

    def __init__(self, ttl: float = 30.0, maxsize: int = 4096) -> None:
        self._ttl = ttl
        self._maxsize = maxsize
        self._data: OrderedDict[str, tuple[float, T]] = OrderedDict()
        self._lock = asyncio.Lock()

    def _purge_expired(self, now: float) -> None:
        expired = [key for key, (expires, _) in self._data.items() if expires <= now]
        for key in expired:
            self._data.pop(key, None)

    async def get(self, key: str) -> T | None:
        now = time.monotonic()
        async with self._lock:
            self._purge_expired(now)
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if expires <= now:
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return value

    async def set(self, key: str, value: T) -> None:
        now = time.monotonic()
        async with self._lock:
            self._purge_expired(now)
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (now + self._ttl, value)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    async def invalidate(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._data.clear()