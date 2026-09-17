"""Handwritten pages: rasterised, downsized, and handed to a transcriber."""

from __future__ import annotations

import asyncio
import io
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pypdfium2
from PIL import Image, ImageOps, UnidentifiedImageError
from sidereal_core.models import DocumentDraft, DocumentKind, DocumentStatus

from sidereal_ingest.base import IngestError
from sidereal_ingest.transcribe import (
    Page,
    PaperQuestion,
    Transcriber,
    Transcription,
    TranscriptionResult,
)

IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif")
PDF_SUFFIXES = (".pdf",)
SUFFIXES = IMAGE_SUFFIXES + PDF_SUFFIXES

MAX_PAGES = 20
MAX_EDGE = 1600
RASTER_DPI = 150
JPEG_QUALITY = 80
PDF_POINTS_PER_INCH = 72.0
UNREADABLE = "Upload a JPEG, a PNG or a PDF."


@dataclass(frozen=True, slots=True)
class ScanFile:
    """One uploaded file, as Directus named it and as it arrived."""

    filename: str
    content: bytes


class ScanIngester:
    """Images or a PDF in, a transcription out. One `documents` row, however many pages."""

    kind = DocumentKind.SCAN

    def __init__(
        self,
        transcriber: Transcriber,
        *,
        max_pages: int = MAX_PAGES,
        max_edge: int = MAX_EDGE,
        dpi: float = RASTER_DPI,
    ) -> None:
        self._transcriber = transcriber
        self._max_pages = max_pages
        self._max_edge = max_edge
        self._dpi = dpi

    @property
    def model(self) -> str:
        return self._transcriber.model

    def supports(self, source: str) -> bool:
        return Path(source).suffix.lower() in SUFFIXES

    async def ingest(self, source: str) -> DocumentDraft:
        path = Path(source)
        try:
            content = await asyncio.to_thread(path.read_bytes)
        except OSError as exc:
            raise IngestError(f"{path.name} could not be opened ({exc.strerror or exc}).") from exc
        return await self.read([ScanFile(path.name, content)])

    async def transcribe(
        self, files: Sequence[ScanFile], *, questions: Sequence[PaperQuestion] = ()
    ) -> TranscriptionResult:
        pages = await asyncio.to_thread(self.pages, files)
        return await self._transcriber.transcribe(pages, questions=questions)

    async def read(
        self, files: Sequence[ScanFile], *, questions: Sequence[PaperQuestion] = ()
    ) -> DocumentDraft:
        """The row a scan fills: the transcription as text, and per question when asked for."""
        result = await self.transcribe(files, questions=questions)
        transcription = result.transcription
        return DocumentDraft(
            title=Path(files[0].filename).stem if files else "Scan",
            kind=self.kind,
            text=transcription.text,
            status=DocumentStatus.READY,
            transcription=per_question(transcription) if questions else None,
            metadata=_metadata(files, result),
        )

    def pages(self, files: Sequence[ScanFile]) -> list[Page]:
        """Every file's pages as JPEGs, in the order the files were given."""
        if not files:
            raise IngestError("A scan needs at least one page.")
        pages: list[Page] = []
        for file in files:
            for image in _images(file, self._dpi, self._max_pages):
                if len(pages) == self._max_pages:
                    raise IngestError(_too_many(self._max_pages))
                pages.append(Page(index=len(pages) + 1, jpeg=self._jpeg(image, file.filename)))
        return pages

    def _jpeg(self, image: Image.Image, filename: str) -> bytes:
        try:
            upright = ImageOps.exif_transpose(image)
            upright.thumbnail((self._max_edge, self._max_edge))
            buffer = io.BytesIO()
            upright.convert("RGB").save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        except (OSError, ValueError) as exc:
            raise IngestError(f"{filename} could not be read. {UNREADABLE}") from exc
        return buffer.getvalue()


def per_question(transcription: Transcription) -> dict[str, Any]:
    """The `transcription` column's shape: the working, question by question."""
    return {"questions": [question.model_dump(mode="json") for question in transcription.questions]}


def _too_many(cap: int) -> str:
    return f"A scan is at most {cap} pages; send the rest separately."


def _images(file: ScanFile, dpi: float, cap: int) -> list[Image.Image]:
    suffix = Path(file.filename).suffix.lower()
    if suffix in PDF_SUFFIXES:
        return _rasterise(file, dpi, cap)
    if suffix not in IMAGE_SUFFIXES:
        raise IngestError(f"{file.filename} is not a scan. {UNREADABLE}")
    try:
        return [Image.open(io.BytesIO(file.content))]
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise IngestError(f"{file.filename} could not be read. {UNREADABLE}") from exc


def _rasterise(file: ScanFile, dpi: float, cap: int) -> list[Image.Image]:
    """A PDF's pages as images, at the resolution handwriting stays legible at."""
    try:
        document = pypdfium2.PdfDocument(file.content)
        if len(document) > cap:
            raise IngestError(_too_many(cap))
        scale = dpi / PDF_POINTS_PER_INCH
        return [page.render(scale=scale).to_pil() for page in document]
    except pypdfium2.PdfiumError as exc:
        raise IngestError(f"{file.filename} could not be opened as a PDF.") from exc


def _metadata(files: Sequence[ScanFile], result: TranscriptionResult) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "filenames": [file.filename for file in files],
        "confidence": result.transcription.confidence.value,
        "model": result.model,
    }
    if result.usage is not None:
        metadata["usage"] = result.usage
    return metadata
