from __future__ import annotations

from pathlib import Path

import pytest
from sidereal_core.models import DocumentKind
from sidereal_ingest.base import IngestError
from sidereal_ingest.upload import UploadIngester

FIXTURES = Path(__file__).parent / "fixtures"


async def test_txt_upload() -> None:
    draft = await UploadIngester().ingest(str(FIXTURES / "tutor-notes.txt"))

    assert draft.kind is DocumentKind.UPLOAD
    assert draft.title == "tutor-notes"
    assert draft.text is not None
    assert draft.text.startswith("Needs more practice")


async def test_pdf_upload() -> None:
    draft = await UploadIngester().ingest(str(FIXTURES / "question-bank.pdf"))

    assert draft.text == "   Quadratic equations: practice set\n   Solve x^2 - 5x + 6 = 0"
    assert draft.metadata["format"] == "pdf"


async def test_docx_upload() -> None:
    draft = await UploadIngester().ingest(str(FIXTURES / "session-notes.docx"))

    assert draft.text == (
        "Session notes\nReviewed factorising quadratics.\nNext: completing the square."
    )


async def test_unsupported_suffix() -> None:
    with pytest.raises(IngestError):
        await UploadIngester().ingest(str(FIXTURES / "lesson.vtt"))


async def test_a_corrupt_pdf_is_an_ingest_error(tmp_path: Path) -> None:
    broken = tmp_path / "broken.pdf"
    broken.write_text("not a pdf at all")

    with pytest.raises(IngestError):
        await UploadIngester().ingest(str(broken))
