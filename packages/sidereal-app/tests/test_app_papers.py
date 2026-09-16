from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sidereal_core.models import Collection
from sidereal_core.testing import DEFAULT_USER_ID, FakeDirectus, FakeTypeset

PAPER_TEXT = "1. Show that $1 + 1 = 2$.\n2. Differentiate $y = x^2$."


@pytest.fixture
def document_id(fake_directus: FakeDirectus) -> UUID:
    row = fake_directus.seed(
        Collection.DOCUMENTS,
        {"title": "Mock paper 1", "kind": "upload", "status": "ready", "text": PAPER_TEXT},
    )
    return UUID(row["id"])


def make_student(fake_directus: FakeDirectus) -> None:
    """The caller's own `students` row: what makes the app answer `student`."""
    fake_directus.seed(Collection.STUDENTS, {"name": "A. Tutee", "user": str(DEFAULT_USER_ID)})


def extract(client: TestClient, auth: dict[str, str], document_id: UUID) -> dict[str, Any]:
    response = client.post(
        "/api/jobs/paper_extract", headers=auth, json={"document_ids": [str(document_id)]}
    )
    assert response.status_code == 202
    return dict(response.json())


def test_a_paper_extract_job_needs_no_student_and_writes_the_paper(
    client: TestClient, fake_directus: FakeDirectus, document_id: UUID, auth: dict[str, str]
) -> None:
    job = extract(client, auth, document_id)

    assert job["status"] == "queued"
    assert job["student"] is None

    # The background task has run by the time TestClient returns.
    finished = fake_directus.rows(Collection.GENERATION_JOBS)[0]
    assert finished["status"] == "succeeded"
    assert finished["output_collection"] == "papers"

    paper = fake_directus.rows(Collection.PAPERS)[0]
    assert paper["status"] == "draft"
    assert [question["number"] for question in fake_directus.rows(Collection.QUESTIONS)] == [
        "1",
        "2",
    ]
    assert fake_directus.files[paper["rendered_pdf"]][1].startswith(b"%PDF")
    assert fake_directus.files[paper["mark_scheme_pdf"]][1].startswith(b"%PDF")


@pytest.mark.parametrize("documents", [[], ["a", "b", "b"]])
def test_a_paper_extract_job_takes_one_document_or_two(
    client: TestClient,
    fake_directus: FakeDirectus,
    document_id: UUID,
    auth: dict[str, str],
    documents: list[str],
) -> None:
    ids = [str(document_id) if value == "a" else str(UUID(int=7)) for value in documents]

    response = client.post("/api/jobs/paper_extract", headers=auth, json={"document_ids": ids})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "document_required"
    assert fake_directus.rows(Collection.GENERATION_JOBS) == []


def test_a_paper_extract_job_accepts_a_mark_scheme_beside_the_paper(
    client: TestClient,
    fake_directus: FakeDirectus,
    document_id: UUID,
    auth: dict[str, str],
) -> None:
    scheme = fake_directus.seed(
        Collection.DOCUMENTS,
        {"title": "Mark scheme", "kind": "upload", "status": "ready", "text": "1 (a) 3x^2 (2)"},
    )

    response = client.post(
        "/api/jobs/paper_extract",
        headers=auth,
        json={"document_ids": [str(document_id), scheme["id"]]},
    )

    assert response.status_code == 202
    job = fake_directus.rows(Collection.GENERATION_JOBS)[0]
    assert job["input"]["documents"] == [str(document_id), scheme["id"]]


def test_every_other_kind_still_needs_a_student(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    response = client.post("/api/jobs/homework", headers=auth, json={})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "student_required"
    assert fake_directus.rows(Collection.GENERATION_JOBS) == []


def test_rendering_a_paper_again_replaces_its_pdfs(
    client: TestClient,
    fake_directus: FakeDirectus,
    fake_typeset: FakeTypeset,
    document_id: UUID,
    auth: dict[str, str],
) -> None:
    extract(client, auth, document_id)
    paper = fake_directus.rows(Collection.PAPERS)[0]
    before = paper["rendered_pdf"]
    paper["structure"]["questions"][0]["stem"] = "Corrected stem."

    response = client.post(f"/api/papers/{paper['id']}/render", headers=auth)

    assert response.status_code == 202
    assert response.json()["rendered_pdf"] != before
    rendered = [call for call in fake_typeset.rendered if call["kind"] == "paper"][-1]
    assert rendered["document"]["questions"][0]["stem"] == "Corrected stem."


def test_a_paper_with_no_structure_says_so(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    row = fake_directus.seed(Collection.PAPERS, {"title": "Hand-filed", "status": "draft"})

    response = client.post(f"/api/papers/{row['id']}/render", headers=auth)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "paper_unusable"


def test_a_worksheet_takes_the_questions_asked_for_and_files_a_pdf(
    client: TestClient,
    fake_directus: FakeDirectus,
    fake_typeset: FakeTypeset,
    document_id: UUID,
    auth: dict[str, str],
) -> None:
    extract(client, auth, document_id)
    paper = fake_directus.rows(Collection.PAPERS)[0]
    student = fake_directus.seed(Collection.STUDENTS, {"name": "A. Tutee"})

    response = client.post(
        f"/api/papers/{paper['id']}/worksheet",
        headers=auth,
        json={
            "question_numbers": ["2"],
            "student_id": student["id"],
            "title": "Week 3",
            "due": "2026-09-25",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert fake_directus.files[body["pdf_file_id"]][1].startswith(b"%PDF")
    worksheet = [call for call in fake_typeset.rendered if call["kind"] == "worksheet"][-1]
    assert [question["number"] for question in worksheet["document"]["questions"]] == ["2"]
    assert worksheet["document"]["student"] == "A. Tutee"
    assert worksheet["document"]["due"] == "2026-09-25"


def test_a_worksheet_with_no_questions_is_refused_before_directus(
    client: TestClient, fake_directus: FakeDirectus, document_id: UUID, auth: dict[str, str]
) -> None:
    extract(client, auth, document_id)
    paper = fake_directus.rows(Collection.PAPERS)[0]

    response = client.post(
        f"/api/papers/{paper['id']}/worksheet", headers=auth, json={"question_numbers": []}
    )

    assert response.status_code == 422


def test_a_student_may_not_render_or_remix_a_paper(
    client: TestClient, fake_directus: FakeDirectus, document_id: UUID, auth: dict[str, str]
) -> None:
    extract(client, auth, document_id)
    paper = fake_directus.rows(Collection.PAPERS)[0]
    make_student(fake_directus)

    rendered = client.post(f"/api/papers/{paper['id']}/render", headers=auth)
    worksheet = client.post(
        f"/api/papers/{paper['id']}/worksheet", headers=auth, json={"question_numbers": ["1"]}
    )

    assert rendered.status_code == 403
    assert rendered.json()["detail"]["code"] == "tutor_only"
    assert worksheet.status_code == 403


def test_a_paper_the_caller_cannot_see_is_directuss_own_answer(
    client: TestClient, auth: dict[str, str]
) -> None:
    response = client.post(f"/api/papers/{UUID(int=9)}/render", headers=auth)

    assert response.status_code == 404
