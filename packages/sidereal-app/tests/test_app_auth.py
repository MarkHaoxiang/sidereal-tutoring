from __future__ import annotations

from fastapi.testclient import TestClient
from sidereal_core.testing import FakeDirectus

JOB_ID = "11111111-1111-4111-8111-111111111111"


def test_no_token_is_401_with_a_code(client: TestClient) -> None:
    response = client.get(f"/api/jobs/{JOB_ID}")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "missing_token"


def test_a_rejected_token_is_401_with_a_code(client: TestClient) -> None:
    response = client.get(f"/api/jobs/{JOB_ID}", headers={"Authorization": "Bearer wrong"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_token"


def test_an_unreachable_directus_is_503_with_a_code(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    fake_directus.unavailable = True

    response = client.get(f"/api/jobs/{JOB_ID}", headers=auth)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "directus_unavailable"


def test_an_accepted_token_reaches_the_route(client: TestClient, auth: dict[str, str]) -> None:
    response = client.get(f"/api/jobs/{JOB_ID}", headers=auth)

    assert response.status_code == 404
    assert response.json()["code"] == "directus_rejected"


def test_directus_failing_after_auth_is_503_from_the_handler(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    fake_directus.unavailable_after = 1

    response = client.get(f"/api/jobs/{JOB_ID}", headers=auth)

    assert response.status_code == 503
    assert response.json()["code"] == "directus_unavailable"
