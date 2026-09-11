from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Rate limit for outbound fetches. `clock`/`sleep` are injected so tests need no wall time."""

    rate: float
    capacity: float = 1.0
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    _tokens: float = field(init=False)
    _updated: float = field(init=False)
    _lock: asyncio.Lock = field(init=False, default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        if self.rate <= 0 or self.capacity <= 0:
            raise ValueError("a token bucket needs a positive rate and capacity")
        self._tokens = self.capacity
        self._updated = self.clock()

    async def acquire(self, tokens: float = 1.0) -> None:
        if tokens > self.capacity:
            raise ValueError(f"{tokens} tokens never fit in a bucket of {self.capacity}")
        async with self._lock:
            while True:
                now = self.clock()
                self._tokens = min(self.capacity, self._tokens + (now - self._updated) * self.rate)
                self._updated = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                await self.sleep((tokens - self._tokens) / self.rate)
