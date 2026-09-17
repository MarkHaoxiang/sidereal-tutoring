from __future__ import annotations

import io
from uuid import UUID

import pytest
from mcp_doubles import build_services, seed_student
from PIL import Image
from sidereal_core.models import Collection, DocumentKind, DocumentStatus
from sidereal_core.testing import FakeDirectus
from sidereal_ingest.documents import DocumentError
from sidereal_ingest.transcribe import Confidence, FakeTranscriber, Transcription
from sidereal_mcp import tools

WORKING = Transcription(text="$x = 4$", confidence=Confidence.HIGH, questions=())


def png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (600, 400), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def scan_file(fake: FakeDirectus, name: str = "page-1.png") -> UUID:
    return UUID(fake.register_file(name, png(), media_type="image/png"))


async def test_scan_pages_files_the_pages_and_returns_a_ready_document() -> None:
    fake = FakeDirectus()
    student_id = seed_student(fake)
    transcriber = FakeTranscriber(transcription=WORKING)
    services = build_services(fake, transcriber=transcriber)

    document = await tools.scan_pages(
        services,
        [scan_file(fake, "page-1.png"), scan_file(fake, "page-2.png")],
        student_id=student_id,
        title="Week 3 working",
    )

    assert document.kind is DocumentKind.SCAN
    assert document.status is DocumentStatus.READY
    assert document.text == "$x = 4$"
    assert document.student == student_id
    assert [row["sort"] for row in fake.rows(Collection.DOCUMENT_PAGES)] == [1, 2]
    assert len(transcriber.pages) == 2


async def test_scan_pages_of_a_paper_comes_back_question_by_question() -> None:
    fake = FakeDirectus()
    paper = fake.seed(
        Collection.PAPERS,
        {"title": "Pure 1", "structure": {"title": "Pure 1", "questions": [{"number": "1"}]}},
    )
    services = build_services(fake)

    document = await tools.scan_pages(services, [scan_file(fake)], paper_id=UUID(str(paper["id"])))

    assert document.paper == UUID(str(paper["id"]))
    assert document.transcription is not None
    assert [question["number"] for question in document.transcription["questions"]] == ["1"]


async def test_a_scan_that_cannot_be_read_comes_back_as_a_failed_row() -> None:
    fake = FakeDirectus()
    file_id = UUID(fake.register_file("page.jpg", b"not an image", media_type="image/jpeg"))
    services = build_services(fake)

    document = await tools.scan_pages(services, [file_id])

    assert document.status is DocumentStatus.FAILED
    assert document.error is not None
    assert "Upload a JPEG" in document.error


async def test_transcribe_submission_writes_the_typed_version_beside_the_photo() -> None:
    fake = FakeDirectus()
    student_id = seed_student(fake)
    homework = fake.seed(
        Collection.HOMEWORK,
        {
            "student": str(student_id),
            "title": "Week 3",
            "content": "## Week 3",
            "submission_file": str(scan_file(fake, "handin.jpg")),
        },
    )
    services = build_services(fake, transcriber=FakeTranscriber(transcription=WORKING))

    updated = await tools.transcribe_submission(services, UUID(str(homework["id"])))

    assert updated.submission_transcription is not None
    assert updated.submission_transcription["text"] == "$x = 4$"
    assert updated.submission_transcription["confidence"] == "high"


async def test_transcribing_a_homework_with_no_hand_in_says_so() -> None:
    fake = FakeDirectus()
    homework = fake.seed(
        Collection.HOMEWORK,
        {"student": str(seed_student(fake)), "title": "Week 3", "content": "## Week 3"},
    )
    services = build_services(fake)

    with pytest.raises(DocumentError, match="handed in"):
        await tools.transcribe_submission(services, UUID(str(homework["id"])))
