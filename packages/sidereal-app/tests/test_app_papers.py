from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sidereal_app.deps import get_generators, get_http_client, get_ingesters, get_typeset
from sidereal_app.main import create_app
from sidereal_core.canonical import CanonicalPaper
from sidereal_core.models import Collection, Document
from sidereal_core.testing import DEFAULT_USER_ID, FakeDirectus, FakeTypeset
from sidereal_generate.base import GenerationError, GenerationNotConfiguredError
from sidereal_generate.fake import FakePaperExtractor
from sidereal_generate.jobs import Generators
from sidereal_generate.models import MarkSchemeExtraction
from sidereal_generate.usage import UsageTally
from sidereal_ingest.base import Ingester

PAPER_TEXT = "1. Show that $1 + 1 = 2$.\n2. Differentiate $y = x^2$."
MISSING_QUESTION = "The mark scheme has no answer for question 2."


class IncompleteMarkScheme(FakePaperExtractor):
    """A mark scheme that stays short of the paper's own questions, even after a retry."""

    async def extract_mark_scheme(
        self, document: Document, paper: CanonicalPaper, *, usage: UsageTally | None = None
    ) -> MarkSchemeExtraction:
        raise GenerationError(MISSING_QUESTION)


class Unconfigured(FakePaperExtractor):
    """The backend with no key, so nothing was asked of it."""

    async def extract_mark_scheme(
        self, document: Document, paper: CanonicalPaper, *, usage: UsageTally | None = None
    ) -> MarkSchemeExtraction:
        raise GenerationNotConfiguredError("OPENROUTER_API_KEY is not set.")


def client_with(
    fake_directus: FakeDirectus,
    fake_typeset: FakeTypeset,
    generators: Generators,
    ingesters: Sequence[Ingester],
) -> TestClient:
    """A client whose paper extractor is swapped for one that fails, to reach the handler."""
    app = create_app()
    pool = httpx.AsyncClient(transport=fake_directus.transport())
    app.dependency_overrides[get_http_client] = lambda: pool
    app.dependency_overrides[get_generators] = lambda: generators
    app.dependency_overrides[get_ingesters] = lambda: ingesters
    app.dependency_overrides[get_typeset] = lambda: fake_typeset.client()
    return TestClient(app)


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
    # One document and no mark scheme, so the mark-scheme call was never made.
    assert paper["mark_scheme_pdf"] is None


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


def test_a_paper_extract_job_records_pages_on_its_input(
    client: TestClient,
    fake_directus: FakeDirectus,
    document_id: UUID,
    auth: dict[str, str],
) -> None:
    response = client.post(
        "/api/jobs/paper_extract",
        headers=auth,
        json={"document_ids": [str(document_id)], "pages": True},
    )

    assert response.status_code == 202
    job = fake_directus.rows(Collection.GENERATION_JOBS)[0]
    assert job["input"]["pages"] is True


def test_pages_is_refused_on_any_other_kind(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    response = client.post(
        "/api/jobs/homework", headers=auth, json={"student_id": str(student_id), "pages": False}
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "pages_unsupported"
    assert fake_directus.rows(Collection.GENERATION_JOBS) == []


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


def test_a_mark_scheme_that_stays_incomplete_is_paper_unusable(
    fake_directus: FakeDirectus,
    fake_typeset: FakeTypeset,
    generators: Generators,
    ingesters: Sequence[Ingester],
    document_id: UUID,
    auth: dict[str, str],
) -> None:
    """`extract_mark_scheme` calls generate directly: `GenerationError` must still reach 422."""
    with client_with(
        fake_directus,
        fake_typeset,
        dataclasses.replace(generators, paper=IncompleteMarkScheme()),
        ingesters,
    ) as client:
        extract(client, auth, document_id)
        paper = fake_directus.rows(Collection.PAPERS)[0]

        response = client.post(
            f"/api/papers/{paper['id']}/extract_mark_scheme",
            headers=auth,
            json={"document_id": str(document_id)},
        )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["code"] == "paper_unusable"
    assert body["detail"]["message"] == MISSING_QUESTION


def test_generation_with_no_key_is_a_service_problem_not_a_bad_paper(
    fake_directus: FakeDirectus,
    fake_typeset: FakeTypeset,
    generators: Generators,
    ingesters: Sequence[Ingester],
    document_id: UUID,
    auth: dict[str, str],
) -> None:
    """A missing key is an administrator's problem: it must not read as `paper_unusable`."""
    with client_with(
        fake_directus,
        fake_typeset,
        dataclasses.replace(generators, paper=Unconfigured()),
        ingesters,
    ) as client:
        extract(client, auth, document_id)
        paper = fake_directus.rows(Collection.PAPERS)[0]

        response = client.post(
            f"/api/papers/{paper['id']}/extract_mark_scheme",
            headers=auth,
            json={"document_id": str(document_id)},
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "generation_not_configured"


def test_re_extracting_a_mark_scheme_answers_with_the_updated_paper(
    client: TestClient,
    fake_directus: FakeDirectus,
    fake_typeset: FakeTypeset,
    document_id: UUID,
    auth: dict[str, str],
) -> None:
    extract(client, auth, document_id)
    paper = fake_directus.rows(Collection.PAPERS)[0]
    structure = paper["structure"]
    scheme = fake_directus.seed(
        Collection.DOCUMENTS,
        {"title": "Mark scheme", "kind": "upload", "status": "ready", "text": "1 (a) 3x^2 (2)"},
    )

    response = client.post(
        f"/api/papers/{paper['id']}/extract_mark_scheme",
        headers=auth,
        json={"document_id": scheme["id"]},
    )

    assert response.status_code == 202
    body = response.json()
    assert [question["number"] for question in body["mark_scheme"]["questions"]] == ["1", "2"]
    assert fake_directus.files[body["mark_scheme_pdf"]][1].startswith(b"%PDF")
    assert body["generated_from"]["mark_scheme_document"] == scheme["id"]
    # The scheme alone was re-read: the paper's own structure is what it already was.
    assert body["structure"] == structure
    rendered = [call for call in fake_typeset.rendered if call["kind"] == "mark_scheme"][-1]
    assert [question["number"] for question in rendered["document"]["questions"]] == ["1", "2"]


def test_a_mark_scheme_for_a_paper_the_caller_cannot_see_is_directuss_own_answer(
    client: TestClient, document_id: UUID, auth: dict[str, str]
) -> None:
    response = client.post(
        f"/api/papers/{UUID(int=9)}/extract_mark_scheme",
        headers=auth,
        json={"document_id": str(document_id)},
    )

    assert response.status_code == 404


def test_a_student_may_not_re_extract_a_mark_scheme(
    client: TestClient, fake_directus: FakeDirectus, document_id: UUID, auth: dict[str, str]
) -> None:
    extract(client, auth, document_id)
    paper = fake_directus.rows(Collection.PAPERS)[0]
    make_student(fake_directus)

    response = client.post(
        f"/api/papers/{paper['id']}/extract_mark_scheme",
        headers=auth,
        json={"document_id": str(document_id)},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "tutor_only"


@pytest.mark.parametrize("body", [None, {}, {"document_id": "not-a-uuid"}, {"document": "1"}])
def test_a_mark_scheme_needs_one_document_id(
    client: TestClient,
    fake_directus: FakeDirectus,
    document_id: UUID,
    auth: dict[str, str],
    body: dict[str, str] | None,
) -> None:
    extract(client, auth, document_id)
    paper = fake_directus.rows(Collection.PAPERS)[0]

    response = client.post(
        f"/api/papers/{paper['id']}/extract_mark_scheme", headers=auth, json=body
    )

    assert response.status_code == 422
    assert paper["mark_scheme_pdf"] is None


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
