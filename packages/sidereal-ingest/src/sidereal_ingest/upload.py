from __future__ import annotations

import asyncio
from pathlib import Path

import docx
import pypdf
from sidereal_core.models import DocumentDraft, DocumentKind, DocumentStatus

from sidereal_ingest.base import IngestError

SUFFIXES = (".txt", ".pdf", ".docx")


class UploadIngester:
    kind = DocumentKind.UPLOAD

    def supports(self, source: str) -> bool:
        return Path(source).suffix.lower() in SUFFIXES

    async def ingest(self, source: str) -> DocumentDraft:
        path = Path(source)
        suffix = path.suffix.lower()
        if suffix not in SUFFIXES:
            raise IngestError(f"{path.name}: unsupported upload type {suffix!r}")
        try:
            text = await asyncio.to_thread(_READERS[suffix], path)
        except OSError as exc:
            raise IngestError(f"{path.name}: {exc}") from exc
        return DocumentDraft(
            title=path.stem,
            kind=self.kind,
            text=text,
            status=DocumentStatus.READY,
            metadata={"filename": path.name, "format": suffix.lstrip(".")},
        )


def _read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def _read_pdf(path: Path) -> str:
    try:
        reader = pypdf.PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
    except pypdf.errors.PyPdfError as exc:
        raise IngestError(f"{path.name}: {exc}") from exc
    return "\n\n".join(page.strip() for page in pages if page.strip())


def _read_docx(path: Path) -> str:
    document = docx.Document(str(path))
    lines = [paragraph.text.strip() for paragraph in document.paragraphs]
    return "\n".join(line for line in lines if line)


_READERS = {".txt": _read_txt, ".pdf": _read_pdf, ".docx": _read_docx}
