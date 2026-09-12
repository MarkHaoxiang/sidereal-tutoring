from __future__ import annotations

from datetime import date
from uuid import UUID

import httpx
import pytest
from mcp_doubles import FIXTURES, build_services, seed_student
from sidereal_core.models import (
    Collection,
    DocumentKind,
    DocumentStatus,
    HomeworkFormat,
    JobStatus,
    StudentStatus,
)
from sidereal_core.students import StudentNotVisibleError
from sidereal_core.testing import FakeDirectus, FakeTypeset
from sidereal_mcp import tools


async def test_list_students_filters_by_status() -> None:
    fake = FakeDirectus()
    fake.seed(Collection.STUDENTS, {"name": "Active", "status": "active"})
    fake.seed(Collection.STUDENTS, {"name": "Paused", "status": "paused"})

    paused = await tools.list_students(build_services(fake), StudentStatus.PAUSED)

    assert [student.name for student in paused] == ["Paused"]


async def test_list_documents_filters_by_student_and_kind() -> None:
    fake = FakeDirectus()
    student_id = seed_student(fake)
    fake.seed(
        Collection.DOCUMENTS,
        {"title": "Lesson", "kind": "transcript", "student": str(student_id)},
    )
    fake.seed(Collection.DOCUMENTS, {"title": "Page", "kind": "web_page"})

    mine = await tools.list_documents(build_services(fake), student_id, DocumentKind.TRANSCRIPT)

    assert [document.title for document in mine] == ["Lesson"]


async def test_ingest_a_transcript_file_writes_a_ready_document() -> None:
    fake = FakeDirectus()
    student_id = seed_student(fake)

    document = await tools.ingest_source(
        build_services(fake), str(FIXTURES / "lesson-4.vtt"), student_id=student_id
    )

    assert document.kind is DocumentKind.TRANSCRIPT
    assert document.text == "We looked at indices."
    assert document.student == student_id
    assert document.status.value == "ready"


async def test_ingest_a_url_and_file_it_under_an_overridden_kind() -> None:
    document = await tools.ingest_source(
        build_services(FakeDirectus()),
        "https://example.test/indices",
        kind=DocumentKind.QUESTION_BANK,
    )

    assert document.kind is DocumentKind.QUESTION_BANK
    assert document.source_url == "https://example.test/indices"
    assert document.text == "Powers of ten."


async def test_generate_homework_runs_the_job_to_completion() -> None:
    fake = FakeDirectus()
    student_id = seed_student(fake)
    document = fake.seed(
        Collection.DOCUMENTS, {"title": "Lesson", "kind": "transcript", "text": "Body."}
    )

    job = await tools.generate_homework(
        build_services(fake), student_id, [UUID(document["id"])], "Six questions."
    )

    assert job.status is JobStatus.SUCCEEDED
    assert job.output_collection == "homework"
    assert job.model == "fake-homework"
    assert fake.rows(Collection.HOMEWORK)[0]["title"] == "Quadratics: week 3"


async def test_generating_typst_homework_leaves_a_compiled_pdf_on_the_row() -> None:
    fake = FakeDirectus()
    student_id = seed_student(fake)

    job = await tools.generate_homework(
        build_services(fake), student_id, format=HomeworkFormat.TYPST
    )

    assert job.status is JobStatus.SUCCEEDED
    row = fake.rows(Collection.HOMEWORK)[0]
    assert row["format"] == "typst"
    assert fake.files[row["pdf"]][1].startswith(b"%PDF")


async def test_previewing_typst_returns_one_svg_per_page() -> None:
    typeset = FakeTypeset(pages=2)

    pages = await tools.preview_typst(build_services(FakeDirectus(), typeset), "= Week 3\n")

    assert len(pages) == 2
    assert pages[0].startswith("<svg")


async def test_generate_feedback_and_plan() -> None:
    fake = FakeDirectus()
    student_id = seed_student(fake)
    services = build_services(fake)

    feedback = await tools.generate_feedback(services, student_id)
    plan = await tools.generate_plan(
        services, student_id, period_start=date(2026, 1, 5), period_end=date(2026, 2, 16)
    )

    assert feedback.output_collection == "feedback"
    assert plan.output_collection == "plans"


async def test_list_and_update_generation_jobs() -> None:
    fake = FakeDirectus()
    student_id = seed_student(fake)
    services = build_services(fake)
    job = await tools.generate_feedback(services, student_id)

    queued = await tools.list_generation_jobs(services, JobStatus.QUEUED)
    succeeded = await tools.list_generation_jobs(services, JobStatus.SUCCEEDED)
    reopened = await tools.update_generation_job(
        services, job.id, JobStatus.FAILED, "tutor rejected it"
    )

    assert queued == []
    assert [row.id for row in succeeded] == [job.id]
    assert reopened.status is JobStatus.FAILED
    assert reopened.error == "tutor rejected it"


async def test_an_unroutable_source_comes_back_as_a_failed_row() -> None:
    document = await tools.ingest_source(build_services(FakeDirectus()), "notes.md")

    assert document.status is DocumentStatus.FAILED
    assert document.error is not None
    assert document.error.startswith("notes.md cannot be read.")


class Scoped(FakeDirectus):
    """A Directus that hides every `students` row but one, the way a tutor's rules do."""

    def __init__(self) -> None:
        super().__init__()
        self.mine = str(self.seed(Collection.STUDENTS, {"name": "Mine"})["id"])
        self.theirs = str(self.seed(Collection.STUDENTS, {"name": "Another tutor's"})["id"])

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith("/items/students/") and not path.endswith(self.mine):
            return httpx.Response(
                403, json={"errors": [{"message": "no", "extensions": {"code": "FORBIDDEN"}}]}
            )
        return super().handle(request)


async def test_nothing_is_filed_against_a_student_the_token_cannot_see() -> None:
    fake = Scoped()
    services = build_services(fake)

    with pytest.raises(StudentNotVisibleError):
        await tools.ingest_source(
            services, "https://example.test/indices", student_id=UUID(fake.theirs)
        )
    with pytest.raises(StudentNotVisibleError):
        await tools.generate_homework(services, UUID(fake.theirs))

    assert fake.rows(Collection.DOCUMENTS) == []
    assert fake.rows(Collection.GENERATION_JOBS) == []
