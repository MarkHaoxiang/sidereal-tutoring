from __future__ import annotations

import io
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import pytest
from PIL import Image
from sidereal_core.models import Collection, DocumentKind, DocumentStatus
from sidereal_core.testing import FakeDirectus
from sidereal_ingest.base import IngestError
from sidereal_ingest.documents import (
    DocumentError,
    ScanSource,
    create_document,
    process_document,
)
from sidereal_ingest.scan import ScanFile, ScanIngester
from sidereal_ingest.transcribe import (
    Confidence,
    FakeTranscriber,
    Page,
    PaperQuestion,
    TranscribedQuestion,
    Transcriber,
    Transcription,
    TranscriptionResult,
)

PAPER_STRUCTURE: dict[str, Any] = {
    "title": "Pure Mathematics 1",
    "questions": [
        {"number": "1", "stem": "Solve $2 x + 3 = 11$.", "marks": 3, "parts": []},
        {"number": "2", "stem": "Differentiate $y = x^2$.", "marks": 2, "parts": []},
    ],
}
SOLUTIONS = Transcription(
    text="## Page 1\n$2 x = 8$\n$x = 4$",
    confidence=Confidence.HIGH,
    questions=(
        TranscribedQuestion(
            number="1", text="$2 x = 8$, so $x = 4$", confidence=Confidence.HIGH, note=None
        ),
    ),
)


def png(size: tuple[int, int] = (2400, 1000), colour: str = "white") -> bytes:
    image = Image.new("RGB", size, colour)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def pdf(pages: int = 2) -> bytes:
    """A PDF made here, so no fixture file is needed and no compiler is involved."""
    sheets = [Image.new("RGB", (1240, 1754), "white") for _ in range(pages)]
    buffer = io.BytesIO()
    sheets[0].save(buffer, format="PDF", save_all=True, append_images=sheets[1:])
    return buffer.getvalue()


class CostedTranscriber:
    """A transcriber that says what it cost, as the OpenRouter one does."""

    model = "vision-model"

    async def transcribe(
        self, pages: Sequence[Page], *, questions: Sequence[PaperQuestion] = ()
    ) -> TranscriptionResult:
        return TranscriptionResult(SOLUTIONS, self.model, {"calls": 1, "cost_usd": 0.5})


def scanner(transcriber: Transcriber | None = None, **kwargs: Any) -> ScanIngester:
    return ScanIngester(transcriber or FakeTranscriber(), **kwargs)


def test_an_image_is_downsized_to_a_jpeg() -> None:
    pages = scanner().pages([ScanFile("working.png", png())])

    assert len(pages) == 1
    assert pages[0].index == 1
    assert pages[0].jpeg.startswith(b"\xff\xd8\xff")
    assert max(Image.open(io.BytesIO(pages[0].jpeg)).size) == 1600


def test_a_small_image_is_not_enlarged() -> None:
    pages = scanner().pages([ScanFile("note.png", png(size=(300, 200)))])

    assert Image.open(io.BytesIO(pages[0].jpeg)).size == (300, 200)


def test_a_pdf_becomes_one_page_each_in_order() -> None:
    pages = scanner().pages([ScanFile("solutions.pdf", pdf(pages=3))])

    assert [page.index for page in pages] == [1, 2, 3]
    assert all(page.jpeg.startswith(b"\xff\xd8\xff") for page in pages)


def test_several_files_are_read_in_the_order_they_were_given() -> None:
    pages = scanner().pages(
        [
            ScanFile("one.png", png()),
            ScanFile("two.pdf", pdf(pages=2)),
            ScanFile("three.jpg", png()),
        ]
    )

    assert [page.index for page in pages] == [1, 2, 3, 4]


def test_a_file_that_is_not_a_scan_says_what_to_upload() -> None:
    with pytest.raises(IngestError, match="Upload a JPEG"):
        scanner().pages([ScanFile("notes.docx", b"PK\x03\x04")])


def test_bytes_that_are_not_an_image_say_so_plainly() -> None:
    with pytest.raises(IngestError, match="could not be read"):
        scanner().pages([ScanFile("photo.jpg", b"not an image")])


def test_a_file_that_is_not_a_pdf_says_so_plainly() -> None:
    with pytest.raises(IngestError, match="could not be opened as a PDF"):
        scanner().pages([ScanFile("solutions.pdf", b"not a pdf")])


def test_a_scan_past_the_page_cap_is_refused() -> None:
    with pytest.raises(IngestError, match="at most 2 pages"):
        scanner(max_pages=2).pages([ScanFile("solutions.pdf", pdf(pages=3))])


def test_pages_across_files_count_towards_the_same_cap() -> None:
    with pytest.raises(IngestError, match="at most 2 pages"):
        scanner(max_pages=2).pages([ScanFile("a.png", png())] * 3)


async def test_notes_carry_the_transcription_as_text_and_no_per_question_mapping() -> None:
    transcriber = FakeTranscriber()

    draft = await scanner(transcriber).read([ScanFile("notes.png", png())])

    assert draft.kind is DocumentKind.SCAN
    assert draft.title == "notes"
    assert draft.transcription is None
    assert draft.text is not None
    assert draft.metadata["filenames"] == ["notes.png"]
    assert draft.metadata["confidence"] == Confidence.LOW.value
    assert [page.index for page in transcriber.pages] == [1]


async def test_a_scan_of_a_directus_file_is_linked_in_order_and_transcribed() -> None:
    fake = FakeDirectus()
    first = fake.register_file("page-1.png", png(), media_type="image/png")
    second = fake.register_file("page-2.png", png(), media_type="image/png")
    transcriber = FakeTranscriber()

    async with fake.client() as client:
        created = await create_document(
            client, ScanSource((UUID(first), UUID(second))), title="Week 3 working"
        )
        document = await process_document(client, [], created.id, scanner=scanner(transcriber))

    assert created.kind is DocumentKind.SCAN
    assert created.status is DocumentStatus.PENDING
    assert [(row["file"], row["sort"]) for row in fake.rows(Collection.DOCUMENT_PAGES)] == [
        (first, 1),
        (second, 2),
    ]
    assert document.status is DocumentStatus.READY
    assert document.title == "Week 3 working"
    assert document.transcription is None
    assert len(transcriber.pages) == 2


async def test_solutions_to_a_paper_are_filed_question_by_question() -> None:
    fake = FakeDirectus()
    paper = fake.seed(Collection.PAPERS, {"title": "Pure 1", "structure": PAPER_STRUCTURE})
    file_id = fake.register_file("solutions.png", png(), media_type="image/png")
    transcriber = FakeTranscriber(transcription=SOLUTIONS)

    async with fake.client() as client:
        created = await create_document(
            client, ScanSource((UUID(file_id),), UUID(str(paper["id"])))
        )
        document = await process_document(client, [], created.id, scanner=scanner(transcriber))

    assert created.paper == UUID(str(paper["id"]))
    assert [question.number for question in transcriber.questions] == ["1", "2"]
    assert transcriber.questions[0].stem == "Solve $2 x + 3 = 11$."
    assert document.text == SOLUTIONS.text
    assert document.transcription == {
        "questions": [
            {"number": "1", "text": "$2 x = 8$, so $x = 4$", "confidence": "high", "note": None}
        ]
    }


async def test_what_the_transcription_cost_is_filed_on_the_row() -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("page.png", png(), media_type="image/png")

    async with fake.client() as client:
        created = await create_document(client, ScanSource((UUID(file_id),)))
        document = await process_document(
            client, [], created.id, scanner=scanner(CostedTranscriber())
        )

    assert document.metadata["usage"] == {"calls": 1, "cost_usd": 0.5}
    assert document.metadata["model"] == "vision-model"


async def test_a_scan_with_no_transcriber_fails_with_a_sentence_a_tutor_can_act_on() -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("page.png", png(), media_type="image/png")

    async with fake.client() as client:
        created = await create_document(client, ScanSource((UUID(file_id),)))
        document = await process_document(client, [], created.id)

    assert document.status is DocumentStatus.FAILED
    assert document.error == "Handwriting scans are not set up on this server."


async def test_an_unreadable_page_fails_with_the_sentence_the_scanner_wrote() -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("page.jpg", b"not an image", media_type="image/jpeg")

    async with fake.client() as client:
        created = await create_document(client, ScanSource((UUID(file_id),)))
        document = await process_document(client, [], created.id, scanner=scanner())

    assert document.status is DocumentStatus.FAILED
    assert document.error == "page.jpg could not be read. Upload a JPEG, a PNG or a PDF."


async def test_a_scan_of_no_files_is_refused_before_a_row_exists() -> None:
    fake = FakeDirectus()

    async with fake.client() as client:
        with pytest.raises(DocumentError, match="at least one page"):
            await create_document(client, ScanSource(()))

    assert fake.rows(Collection.DOCUMENTS) == []
