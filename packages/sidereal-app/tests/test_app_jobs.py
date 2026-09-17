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


def test_a_retry_queues_the_same_input_again(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    first = client.post(
        "/api/jobs/feedback", headers=auth, json={"student_id": str(student_id)}
    ).json()

    response = client.post(f"/api/jobs/{first['id']}/retry", headers=auth)

    assert response.status_code == 202
    again = response.json()
    assert again["id"] != first["id"]
    assert again["input"] == first["input"]
    assert len(fake_directus.rows(Collection.GENERATION_JOBS)) == 2


def test_feedback_takes_the_hand_ins_it_is_about(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    homework = fake_directus.seed(
        Collection.HOMEWORK,
        {"student": str(student_id), "title": "Moments", "content": "", "status": "submitted"},
    )

    response = client.post(
        "/api/jobs/feedback",
        headers=auth,
        json={"student_id": str(student_id), "homework_ids": [homework["id"]]},
    )

    assert response.status_code == 202
    assert fake_directus.rows(Collection.FEEDBACK)[0]["homework"] == homework["id"]


def test_only_feedback_is_written_about_a_hand_in(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    homework = fake_directus.seed(
        Collection.HOMEWORK, {"student": str(student_id), "title": "Moments", "content": ""}
    )

    response = client.post(
        "/api/jobs/plan",
        headers=auth,
        json={"student_id": str(student_id), "homework_ids": [homework["id"]]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "homework_unsupported"
    assert not fake_directus.rows(Collection.GENERATION_JOBS)


def test_a_retry_of_a_deleted_students_job_is_refused_in_words(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    """The live failure: a raw Directus foreign key reached the toast and nothing was queued."""
    first = client.post(
        "/api/jobs/feedback", headers=auth, json={"student_id": str(student_id)}
    ).json()
    client.delete(f"/api/students/{student_id}", headers=auth)
    queued = len(fake_directus.rows(Collection.GENERATION_JOBS))

    response = client.post(f"/api/jobs/{first['id']}/retry", headers=auth)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "student_gone"
    assert response.json()["detail"]["message"] == (
        "That job's student no longer exists, so it cannot be run again."
    )
    assert len(fake_directus.rows(Collection.GENERATION_JOBS)) == queued


def test_the_admin_jobs_listing_still_names_a_deleted_students_work(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    client.post("/api/jobs/feedback", headers=auth, json={"student_id": str(student_id)})
    fake_directus.admin = True

    client.delete(f"/api/students/{student_id}", headers=auth)
    rows = client.get("/api/admin/jobs", headers=auth).json()

    assert [row["student_name"] for row in rows] == ["A. Tutee"]
