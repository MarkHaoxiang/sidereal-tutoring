from __future__ import annotations

from fastapi.testclient import TestClient
from sidereal_core.testing import FakeDirectus


def test_health_needs_no_token(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_answers_while_directus_is_down(
    client: TestClient, fake_directus: FakeDirectus
) -> None:
    fake_directus.unavailable = True

    assert client.get("/api/health").status_code == 200


def test_the_schema_names_every_route(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths) == {
        "/api/health",
        "/api/me",
        "/api/students/{student_id}/login",
        "/api/students/{student_id}/login/password",
        "/api/documents",
        "/api/documents/{document_id}/process",
        "/api/jobs/{kind}",
        "/api/jobs/{job_id}",
        "/api/typeset/preview",
        "/api/homework/{homework_id}/compile",
        "/api/admin/health",
        "/api/admin/tutors",
        "/api/admin/tutors/{user_id}",
        "/api/admin/tutors/{user_id}/password",
        "/api/admin/jobs",
    }
