from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sidereal_app.api.ratelimit import MAX_KEYS, KeyedLimiter
from sidereal_app.main import LOGIN_CHECK_BURST
from sidereal_core.models import Collection
from sidereal_core.testing import DEFAULT_TOKEN, FakeDirectus


@pytest.fixture(autouse=True)
def service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one place the app acts as itself: nobody signing in has a token to send."""
    monkeypatch.setenv("SIDEREAL_DIRECTUS_TOKEN", DEFAULT_TOKEN)


def status(client: TestClient, email: str) -> str:
    response = client.post("/api/auth/status", json={"email": email})
    assert response.status_code == 200
    return str(response.json()["status"])


def test_a_suspended_account_says_so_and_an_unknown_one_says_nothing_else(
    client: TestClient, fake_directus: FakeDirectus
) -> None:
    fake_directus.seed(
        Collection.DIRECTUS_USERS, {"email": "priya@sidereal.example.com", "status": "suspended"}
    )
    fake_directus.seed(
        Collection.DIRECTUS_USERS, {"email": "amara@sidereal.example.com", "status": "active"}
    )

    assert status(client, "priya@sidereal.example.com") == "suspended"
    assert status(client, "amara@sidereal.example.com") == "active"
    assert status(client, "nobody@sidereal.example.com") == "unknown"


def test_the_check_needs_no_token_of_the_callers_own(client: TestClient) -> None:
    response = client.post("/api/auth/status", json={"email": "amara@sidereal.example.com"})

    assert response.status_code == 200


def test_a_caller_asking_over_and_over_is_refused(client: TestClient) -> None:
    for _ in range(int(LOGIN_CHECK_BURST)):
        assert client.post("/api/auth/status", json={"email": "a@b.test"}).status_code == 200

    response = client.post("/api/auth/status", json={"email": "a@b.test"})

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "too_many_checks"


def test_without_an_account_of_its_own_the_app_says_it_cannot_check(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SIDEREAL_DIRECTUS_TOKEN", raising=False)

    response = client.post("/api/auth/status", json={"email": "a@b.test"})

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "service_token_missing"


def test_the_bucket_table_cannot_be_grown_from_outside() -> None:
    now = 0.0
    limiter = KeyedLimiter(rate=1.0, burst=1.0, clock=lambda: now)

    for key in range(MAX_KEYS + 10):
        assert limiter.allow(str(key))

    assert len(limiter._seen) == MAX_KEYS  # noqa: SLF001 - the cap is the point of the test.


def test_a_bucket_fills_again_as_time_passes() -> None:
    now = 0.0
    limiter = KeyedLimiter(rate=1.0, burst=1.0, clock=lambda: now)

    assert limiter.allow("here")
    assert not limiter.allow("here")
    now = 1.0
    assert limiter.allow("here")
