"""The one place a `documents` row is written, and driven to `ready` or `failed`."""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import ValidationError
from sidereal_core.canonical import CanonicalPaper
from sidereal_core.directus import DirectusClient, DirectusClientError, DirectusError
from sidereal_core.models import (
    Collection,
    Document,
    DocumentDraft,
    DocumentKind,
    DocumentPage,
    DocumentPageDraft,
    DocumentStatus,
    Paper,
)

from sidereal_ingest.base import Ingester, IngestError, pick
from sidereal_ingest.scan import ScanFile, ScanIngester
from sidereal_ingest.transcribe import PaperQuestion
from sidereal_ingest.transcript import SUFFIXES as TRANSCRIPT_SUFFIXES
from sidereal_ingest.upload import SUFFIXES as UPLOAD_SUFFIXES

FILE_SUFFIXES = tuple(dict.fromkeys(UPLOAD_SUFFIXES + TRANSCRIPT_SUFFIXES))
TRANSCRIPT_ONLY_SUFFIXES = tuple(s for s in TRANSCRIPT_SUFFIXES if s not in UPLOAD_SUFFIXES)

_AUTO_TITLE = "title_source"
_PATH = "path"


class DocumentError(Exception):
    """A failure already phrased for the tutor who will read it."""


@dataclass(frozen=True, slots=True)
class FileSource:
    """A file uploaded to Directus; its bytes come back through the caller's own token."""

    file_id: UUID


@dataclass(frozen=True, slots=True)
class ScanSource:
    """Handwritten pages, in the order they are to be read, and the paper they answer."""

    file_ids: tuple[UUID, ...]
    paper_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class UrlSource:
    url: str


@dataclass(frozen=True, slots=True)
class TextSource:
    text: str


@dataclass(frozen=True, slots=True)
class PathSource:
    """A file already on this machine, which only a local caller can name."""

    path: str


type Source = FileSource | ScanSource | UrlSource | TextSource | PathSource


async def create_document(
    client: DirectusClient,
    source: Source,
    *,
    title: str | None = None,
    kind: DocumentKind | None = None,
    student: UUID | None = None,
    session: UUID | None = None,
) -> Document:
    """Write the pending row. `process_document` is what fills in its text."""
    draft = await _pending(client, source, title, kind)
    document = await client.create_item(
        Collection.DOCUMENTS,
        Document,
        draft.model_copy(update={"student": student, "session": session}),
    )
    if isinstance(source, ScanSource):
        await _link_pages(client, document.id, source.file_ids)
    return document


async def process_document(
    client: DirectusClient,
    ingesters: Sequence[Ingester],
    document_id: UUID,
    *,
    scanner: ScanIngester | None = None,
) -> Document:
    """Take a row to `ready` or `failed`. Never raises for a source it could not read."""
    document = await client.get_item(Collection.DOCUMENTS, Document, document_id)
    await _patch(client, document_id, {"status": DocumentStatus.PROCESSING.value, "error": None})
    try:
        draft = await _read(client, ingesters, document, scanner)
    except Exception as exc:  # noqa: BLE001 - the row carries the failure, it does not raise it.
        return await _patch(
            client,
            document_id,
            {"status": DocumentStatus.FAILED.value, "error": _message(exc, document)},
        )
    return await _patch(
        client,
        document_id,
        {**_extracted(document, draft), "status": DocumentStatus.READY.value, "error": None},
    )


async def _pending(
    client: DirectusClient, source: Source, title: str | None, kind: DocumentKind | None
) -> DocumentDraft:
    metadata: dict[str, Any] = {} if title is not None else {_AUTO_TITLE: "auto"}
    match source:
        case FileSource(file_id=file_id):
            filename = (await client.get_file(file_id)).filename_download
            return DocumentDraft(
                title=title or Path(filename).stem,
                kind=kind or _kind_for(filename),
                file=file_id,
                metadata={**metadata, "filename": filename},
            )
        case ScanSource(file_ids=file_ids, paper_id=paper_id):
            if not file_ids:
                raise DocumentError("A scan needs at least one page.")
            filename = (await client.get_file(file_ids[0])).filename_download
            return DocumentDraft(
                title=title or Path(filename).stem,
                kind=kind or DocumentKind.SCAN,
                paper=paper_id,
                metadata={**metadata, "filename": filename},
            )
        case PathSource(path=path):
            return DocumentDraft(
                title=title or Path(path).stem,
                kind=kind or _kind_for(path),
                metadata={**metadata, _PATH: path, "filename": Path(path).name},
            )
        case UrlSource(url=url):
            return DocumentDraft(
                title=title or _host(url),
                kind=kind or DocumentKind.WEB_PAGE,
                source_url=url,
                metadata=metadata,
            )
        case TextSource(text=text):
            return DocumentDraft(
                title=title or f"Pasted text {datetime.now(UTC).date().isoformat()}",
                kind=kind or DocumentKind.UPLOAD,
                text=text,
                metadata=metadata,
            )


async def _read(
    client: DirectusClient,
    ingesters: Sequence[Ingester],
    document: Document,
    scanner: ScanIngester | None = None,
) -> DocumentDraft | None:
    """The draft to fill the row from, or `None` when the row already holds its text."""
    if document.kind is DocumentKind.SCAN:
        return await _transcribe(client, scanner, document)
    if document.file is not None:
        # Directus keeps the bytes and the row keeps the text, so the copy only has to
        # live as long as the read.
        with tempfile.TemporaryDirectory(prefix="sidereal-ingest-") as scratch:
            copy = await _download(client, document.file, Path(scratch))
            return await _ingest_file(ingesters, copy)
    if document.source_url is not None:
        return await pick(ingesters, document.source_url).ingest(document.source_url)
    path = document.metadata.get(_PATH)
    if isinstance(path, str):
        return await _ingest_file(ingesters, Path(path))
    if document.text:
        return None
    raise DocumentError("There is nothing to read here: no file, no link and no text.")


async def _transcribe(
    client: DirectusClient, scanner: ScanIngester | None, document: Document
) -> DocumentDraft:
    """A scan's pages, read in order. The bytes never reach the disk."""
    if scanner is None:
        raise DocumentError("Handwriting scans are not set up on this server.")
    files = [
        ScanFile(*await client.download_file(file_id))
        for file_id in await _page_files(client, document.id)
    ]
    if not files:
        raise DocumentError("That scan has no pages.")
    return await scanner.read(files, questions=await _paper_questions(client, document.paper))


async def _page_files(client: DirectusClient, document_id: UUID) -> list[UUID]:
    """The scan's files in the order the tutor put them in."""
    pages = await client.list_items(
        Collection.DOCUMENT_PAGES,
        DocumentPage,
        filter={"document": {"_eq": str(document_id)}},
        sort=["sort"],
    )
    return [page.file for page in sorted(pages, key=lambda page: page.sort or 0)]


async def _paper_questions(
    client: DirectusClient, paper_id: UUID | None
) -> tuple[PaperQuestion, ...]:
    """The numbers and stems a solutions scan is matched against."""
    if paper_id is None:
        return ()
    paper = await client.get_item(Collection.PAPERS, Paper, paper_id)
    if paper.structure is None:
        raise DocumentError("That paper has no questions yet, so the pages cannot be matched.")
    try:
        structure = CanonicalPaper.model_validate(paper.structure)
    except ValidationError as exc:
        raise DocumentError("That paper's questions could not be read.") from exc
    return tuple(
        PaperQuestion(number=question.number, stem=question.stem)
        for question in structure.questions
    )


async def _link_pages(client: DirectusClient, document_id: UUID, file_ids: Sequence[UUID]) -> None:
    """The junction rows the `pages` alias reads, in the order the pages were given."""
    for position, file_id in enumerate(file_ids, start=1):
        await client.create_item(
            Collection.DOCUMENT_PAGES,
            DocumentPage,
            DocumentPageDraft(document=document_id, file=file_id, sort=position),
        )


async def _download(client: DirectusClient, file_id: UUID, directory: Path) -> Path:
    filename, content = await client.download_file(file_id)
    path = directory / _safe_name(filename, file_id)
    await asyncio.to_thread(path.write_bytes, content)
    return path


async def _ingest_file(ingesters: Sequence[Ingester], path: Path) -> DocumentDraft:
    if path.suffix.lower() not in FILE_SUFFIXES:
        raise DocumentError(
            f"{path.name} cannot be read. Upload one of: {', '.join(FILE_SUFFIXES)}."
        )
    return await pick(ingesters, str(path)).ingest(str(path))


def _extracted(document: Document, draft: DocumentDraft | None) -> dict[str, Any]:
    metadata = {key: value for key, value in document.metadata.items() if key != _AUTO_TITLE}
    fields: dict[str, Any] = {"metadata": metadata}
    if draft is None:
        return fields
    metadata.update(draft.metadata)
    fields["text"] = draft.text
    if draft.transcription is not None:
        fields["transcription"] = draft.transcription
    auto = document.metadata.get(_AUTO_TITLE) == "auto"
    if auto and draft.title and draft.title != document.source_url:
        fields["title"] = draft.title
    return fields


def _message(exc: BaseException, document: Document) -> str:
    """What the tutor reads in `error`: what failed, and what they can do about it."""
    match exc:
        case DocumentError():
            return str(exc)
        case IngestError() if document.kind is DocumentKind.SCAN:
            return str(exc)
        case IngestError() if document.source_url is not None:
            return (
                f"The link could not be fetched (HTTP {exc.status})."
                if exc.status is not None
                else "The link could not be fetched — the site did not answer."
            )
        case IngestError():
            return f"The file could not be read ({exc})."
        case DirectusError():
            return (
                f"The file could not be downloaded from your material library (HTTP {exc.status})."
            )
        case DirectusClientError():
            return "The file could not be downloaded: the material library is not reachable."
        case OSError():
            return f"The file could not be saved to this machine ({exc.strerror or exc})."
        case _:
            return f"Processing stopped unexpectedly ({type(exc).__name__})."


async def _patch(client: DirectusClient, document_id: UUID, data: dict[str, Any]) -> Document:
    return await client.update_item(Collection.DOCUMENTS, Document, document_id, data)


def _kind_for(filename: str) -> DocumentKind:
    suffix = Path(filename).suffix.lower()
    return DocumentKind.TRANSCRIPT if suffix in TRANSCRIPT_ONLY_SUFFIXES else DocumentKind.UPLOAD


def _safe_name(filename: str, file_id: UUID) -> str:
    """Directus stores the name the tutor's browser sent; it is not a path we may follow."""
    name = Path(filename.replace("\\", "/")).name.strip()
    return name if name not in ("", ".", "..") else str(file_id)


def _host(url: str) -> str:
    return urlsplit(url).netloc or url
