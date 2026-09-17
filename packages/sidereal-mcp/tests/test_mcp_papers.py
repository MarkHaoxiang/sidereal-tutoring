from __future__ import annotations

from uuid import UUID

import pytest
from mcp_doubles import build_services, seed_student
from sidereal_core.models import Collection, JobStatus
from sidereal_core.testing import FakeDirectus, FakeTypeset
from sidereal_generate.papers import PaperError
from sidereal_mcp import tools

PAPER_TEXT = "1. Show that $1 + 1 = 2$.\n2. Differentiate $y = x^2$."


def seed_document(fake: FakeDirectus) -> UUID:
    row = fake.seed(
        Collection.DOCUMENTS,
        {"title": "Mock paper 1", "kind": "upload", "status": "ready", "text": PAPER_TEXT},
    )
    return UUID(row["id"])


async def test_extract_paper_runs_the_job_to_completion() -> None:
    fake = FakeDirectus()
    document_id = seed_document(fake)

    job = await tools.extract_paper(build_services(fake), document_id)

    assert job.status is JobStatus.SUCCEEDED
    assert job.output_collection == "papers"
    assert job.student is None
    paper = fake.rows(Collection.PAPERS)[0]
    assert paper["id"] == str(job.output_id)
    assert len(fake.rows(Collection.QUESTIONS)) == 2


async def test_extract_paper_passes_pages_into_the_job_input() -> None:
    fake = FakeDirectus()
    document_id = seed_document(fake)

    # `False` needs no PDF behind the document, unlike `True`: only the plumbing is under test.
    job = await tools.extract_paper(build_services(fake), document_id, pages=False)

    assert fake.rows(Collection.GENERATION_JOBS)[0]["input"]["pages"] is False
    assert job.status is JobStatus.SUCCEEDED


async def test_render_paper_replaces_the_pdfs_from_the_structure() -> None:
    fake = FakeDirectus()
    typeset = FakeTypeset()
    services = build_services(fake, typeset)
    job = await tools.extract_paper(services, seed_document(fake), seed_document(fake))
    assert job.output_id is not None

    paper = await tools.render_paper(services, job.output_id)

    assert paper.rendered_pdf is not None
    assert paper.mark_scheme_pdf is not None


async def test_a_worksheet_comes_back_as_its_source_and_a_filed_pdf() -> None:
    fake = FakeDirectus()
    typeset = FakeTypeset()
    services = build_services(fake, typeset)
    job = await tools.extract_paper(services, seed_document(fake))
    assert job.output_id is not None
    student_id = seed_student(fake)

    result = await tools.paper_worksheet_pdf(
        services, job.output_id, ["1"], student_id, "Week 3", None
    )

    assert "Week 3" in result.source
    assert fake.files[str(result.pdf_file_id)][1].startswith(b"%PDF")
    worksheet = [call for call in typeset.rendered if call["kind"] == "worksheet"][-1]
    assert [question["number"] for question in worksheet["document"]["questions"]] == ["1"]


async def test_a_worksheet_from_a_paper_with_no_structure_is_refused() -> None:
    fake = FakeDirectus()
    row = fake.seed(Collection.PAPERS, {"title": "Hand-filed", "status": "draft"})

    with pytest.raises(PaperError, match="no structure"):
        await tools.paper_worksheet_pdf(build_services(fake), UUID(row["id"]), ["1"])
