"""A refusal, not a wait: an endpoint anyone may call must not become a way to read a table."""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field

# Above this the oldest caller is forgotten, so the table cannot be grown from outside.
MAX_KEYS = 10_000


@dataclass
class KeyedLimiter:
    """One token bucket per caller. `clock` is injected so tests need no wall time."""

    rate: float
    burst: float
    clock: Callable[[], float] = time.monotonic
    _seen: OrderedDict[str, tuple[float, float]] = field(
        init=False, default_factory=OrderedDict[str, tuple[float, float]]
    )

    def allow(self, key: str) -> bool:
        now = self.clock()
        tokens, updated = self._seen.pop(key, (self.burst, now))
        tokens = min(self.burst, tokens + (now - updated) * self.rate)
        allowed = tokens >= 1.0
        self._seen[key] = (tokens - 1.0 if allowed else tokens, now)
        while len(self._seen) > MAX_KEYS:
            self._seen.popitem(last=False)
        return allowed
