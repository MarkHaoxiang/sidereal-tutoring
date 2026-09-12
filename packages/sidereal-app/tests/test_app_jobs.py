from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sidereal_core.models import Collection
from sidereal_core.testing import FakeDirectus


def test_posting_a_job_runs_it_and_writes_the_artefact(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    document = fake_directus.seed(
        Collection.DOCUMENTS, {"title": "Lesson 3", "kind": "transcript", "text": "Body."}
    )

    response = client.post(
        "/api/jobs/homework",
        headers=auth,
        json={
            "student_id": str(student_id),
            "document_ids": [document["id"]],
            "instructions": "Six questions.",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["model"] == "fake-homework"

    # The background task has run by the time TestClient returns.
    job = fake_directus.rows(Collection.GENERATION_JOBS)[0]
    assert job["status"] == "succeeded"
    assert job["output_collection"] == "homework"
    assert fake_directus.rows(Collection.HOMEWORK)[0]["title"] == "Quadratics: week 3"


def test_reading_a_job_reports_the_outcome(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    created = client.post(
        "/api/jobs/feedback", headers=auth, json={"student_id": str(student_id)}
    ).json()

    response = client.get(f"/api/jobs/{created['id']}", headers=auth)

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["output_collection"] == "feedback"


def test_an_unknown_kind_is_rejected_before_directus(
    client: TestClient, student_id: UUID, auth: dict[str, str]
) -> None:
    response = client.post("/api/jobs/quiz", headers=auth, json={"student_id": str(student_id)})

    assert response.status_code == 422
