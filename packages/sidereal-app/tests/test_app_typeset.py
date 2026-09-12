from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sidereal_core.models import Collection
from sidereal_core.testing import DEFAULT_USER_ID, FAIL_MARKER, FakeDirectus, FakeTypeset

STUDENT = UUID("11111111-1111-4111-8111-111111111111")
SOURCE = "#question[Factorise $x^2 - 5x + 6$.]\n#answerlines(4)\n"
BROKEN = f"#question[Factorise $x^2 - 5x + 6$.]\n{FAIL_MARKER}\n"


@pytest.fixture
def homework_id(fake_directus: FakeDirectus) -> UUID:
    stale = fake_directus.register_file("week-3.pdf", b"%PDF-old", media_type="application/pdf")
    row = fake_directus.seed(
        Collection.HOMEWORK,
        {
            "student": str(STUDENT),
            "title": "Quadratics: week 3",
            "content": SOURCE,
            "format": "typst",
            "pdf": stale,
            "compile_error": "the last attempt failed",
        },
    )
    return UUID(row["id"])


def make_student(fake_directus: FakeDirectus) -> None:
    """The caller's own `students` row: what makes `/api/me` answer `student`."""
    fake_directus.seed(Collection.STUDENTS, {"name": "A. Tutee", "user": str(DEFAULT_USER_ID)})


def test_preview_returns_one_svg_per_page(
    client: TestClient, fake_typeset: FakeTypeset, auth: dict[str, str]
) -> None:
    fake_typeset.pages = 2

    response = client.post("/api/typeset/preview", headers=auth, json={"source": SOURCE})

    assert response.status_code == 200
    pages = response.json()["pages"]
    assert len(pages) == 2
    assert pages[0].startswith("<svg")


def test_preview_of_source_that_will_not_compile_is_a_422_with_diagnostics(
    client: TestClient, auth: dict[str, str]
) -> None:
    response = client.post("/api/typeset/preview", headers=auth, json={"source": BROKEN})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "typeset_failed"
    assert [diagnostic["line"] for diagnostic in detail["diagnostics"]] == [2]


def test_a_student_may_not_preview(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    make_student(fake_directus)

    response = client.post("/api/typeset/preview", headers=auth, json={"source": SOURCE})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "tutor_only"


def test_a_typeset_service_that_is_down_is_a_503_that_names_it(
    client: TestClient, fake_typeset: FakeTypeset, auth: dict[str, str]
) -> None:
    fake_typeset.unavailable = True

    response = client.post("/api/typeset/preview", headers=auth, json={"source": SOURCE})

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "typeset_unavailable"
    assert "typeset service" in detail["message"]


def test_compiling_a_row_replaces_its_pdf_and_clears_the_error(
    client: TestClient, fake_directus: FakeDirectus, homework_id: UUID, auth: dict[str, str]
) -> None:
    response = client.post(f"/api/homework/{homework_id}/compile", headers=auth)

    assert response.status_code == 202
    body = response.json()
    assert body["compile_error"] is None
    assert fake_directus.files[body["pdf"]][1].startswith(b"%PDF-1.7")


def test_a_row_that_will_not_compile_keeps_its_pdf_and_reports_why(
    client: TestClient, fake_directus: FakeDirectus, homework_id: UUID, auth: dict[str, str]
) -> None:
    before = fake_directus.items[Collection.HOMEWORK][str(homework_id)]["pdf"]
    # A tutor edits `content` in Directus, then asks the app to compile it again.
    fake_directus.items[Collection.HOMEWORK][str(homework_id)]["content"] = BROKEN

    response = client.post(f"/api/homework/{homework_id}/compile", headers=auth)

    assert response.status_code == 202
    body = response.json()
    assert body["pdf"] == before
    assert "does-not-compile" in body["compile_error"]


def test_a_markdown_row_has_nothing_to_compile(
    client: TestClient, fake_directus: FakeDirectus, auth: dict[str, str]
) -> None:
    row = fake_directus.seed(
        Collection.HOMEWORK,
        {
            "student": str(STUDENT),
            "title": "Week 3",
            "content": "## Quadratics",
            "format": "markdown",
        },
    )

    response = client.post(f"/api/homework/{row['id']}/compile", headers=auth)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "format_unsupported"


def test_a_student_may_not_compile(
    client: TestClient, fake_directus: FakeDirectus, homework_id: UUID, auth: dict[str, str]
) -> None:
    make_student(fake_directus)

    response = client.post(f"/api/homework/{homework_id}/compile", headers=auth)

    assert response.status_code == 403


def test_a_typst_homework_job_writes_a_compiled_row(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    response = client.post(
        "/api/jobs/homework",
        headers=auth,
        json={"student_id": str(student_id), "format": "typst"},
    )

    assert response.status_code == 202
    job = fake_directus.rows(Collection.GENERATION_JOBS)[0]
    assert job["status"] == "succeeded"
    row = fake_directus.rows(Collection.HOMEWORK)[0]
    assert row["format"] == "typst"
    assert fake_directus.files[row["pdf"]][1].startswith(b"%PDF")


def test_only_homework_can_be_written_in_typst(
    client: TestClient, fake_directus: FakeDirectus, student_id: UUID, auth: dict[str, str]
) -> None:
    response = client.post(
        "/api/jobs/feedback",
        headers=auth,
        json={"student_id": str(student_id), "format": "typst"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "format_unsupported"
    assert fake_directus.rows(Collection.GENERATION_JOBS) == []
