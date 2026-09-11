from __future__ import annotations

import asyncio
import re
from pathlib import Path

from sidereal_core.models import DocumentDraft, DocumentKind, DocumentStatus

from sidereal_ingest.base import IngestError

SUFFIXES = (".vtt", ".srt", ".txt")

_CUE_TIMING = re.compile(r"^\s*(?:\d+:)?\d{1,2}:\d{2}[.,]\d{1,3}\s*-->")
_CUE_NUMBER = re.compile(r"^\s*\d+\s*$")
_LEADING_STAMP = re.compile(r"^\s*[\[(]?(?:\d+:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?[\])]?\s*[-:]?\s*")
_INLINE_TAG = re.compile(r"<[^>]*>")


class TranscriptIngester:
    kind = DocumentKind.TRANSCRIPT

    def supports(self, source: str) -> bool:
        return Path(source).suffix.lower() in SUFFIXES

    async def ingest(self, source: str) -> DocumentDraft:
        path = Path(source)
        if not self.supports(source):
            raise IngestError(f"{path.name}: not a transcript file")
        try:
            raw = await asyncio.to_thread(path.read_text, encoding="utf-8", errors="replace")
        except OSError as exc:
            raise IngestError(f"{path.name}: {exc}") from exc
        return DocumentDraft(
            title=path.stem,
            kind=self.kind,
            text=strip_timestamps(raw),
            status=DocumentStatus.READY,
            metadata={"filename": path.name, "format": path.suffix.lower().lstrip(".")},
        )


def strip_timestamps(raw: str) -> str:
    """Cue timings, cue numbers and caption markup out; the spoken words in order in."""
    lines: list[str] = []
    for original in raw.splitlines():
        line = original.strip()
        if not line or line.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        if _CUE_TIMING.match(line) or _CUE_NUMBER.match(line):
            continue
        line = _INLINE_TAG.sub("", _LEADING_STAMP.sub("", line)).strip()
        # Rolling captions repeat the previous line as they scroll.
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return "\n".join(lines)
