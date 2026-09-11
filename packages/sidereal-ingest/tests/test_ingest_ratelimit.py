from __future__ import annotations

import pytest
from sidereal_ingest.ratelimit import TokenBucket


def bucket(now: list[float], slept: list[float], **kwargs: float) -> TokenBucket:
    async def sleep(seconds: float) -> None:
        slept.append(seconds)
        now[0] += seconds

    return TokenBucket(clock=lambda: now[0], sleep=sleep, **kwargs)


async def test_the_first_burst_is_free_up_to_capacity() -> None:
    now: list[float] = [0.0]
    slept: list[float] = []
    limiter = bucket(now, slept, rate=1.0, capacity=3.0)

    for _ in range(3):
        await limiter.acquire()

    assert slept == []


async def test_an_empty_bucket_waits_for_one_token() -> None:
    now: list[float] = [0.0]
    slept: list[float] = []
    limiter = bucket(now, slept, rate=2.0, capacity=1.0)

    await limiter.acquire()
    await limiter.acquire()

    assert slept == [0.5]


async def test_tokens_refill_with_elapsed_time() -> None:
    now: list[float] = [0.0]
    slept: list[float] = []
    limiter = bucket(now, slept, rate=1.0, capacity=1.0)

    await limiter.acquire()
    now[0] += 5.0
    await limiter.acquire()

    assert slept == []


def test_a_non_positive_rate_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive rate"):
        TokenBucket(rate=0.0)


async def test_asking_for_more_than_the_bucket_holds_is_rejected() -> None:
    with pytest.raises(ValueError, match="never fit"):
        await TokenBucket(rate=1.0, capacity=1.0).acquire(2.0)
