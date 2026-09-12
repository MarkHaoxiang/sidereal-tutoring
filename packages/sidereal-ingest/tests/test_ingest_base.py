from __future__ import annotations

from pathlib import Path

import pytest
from sidereal_ingest import default_ingesters
from sidereal_ingest.base import IngestError, pick
from sidereal_ingest.transcript import TranscriptIngester
from sidereal_ingest.upload import UploadIngester
from sidereal_ingest.web import WebPageIngester

FIXTURES = Path(__file__).parent / "fixtures"


class NullFetcher:
    async def fetch(self, url: str) -> str:
        return ""


def test_pick_routes_by_source() -> None:
    ingesters = default_ingesters(NullFetcher())

    assert isinstance(pick(ingesters, "https://example.test/x"), WebPageIngester)
    assert isinstance(pick(ingesters, str(FIXTURES / "question-bank.pdf")), UploadIngester)
    assert isinstance(pick(ingesters, str(FIXTURES / "lesson.vtt")), TranscriptIngester)
    # `.txt` is claimed by both; the order `default_ingesters` builds is the tie-break.
    assert isinstance(pick(ingesters, str(FIXTURES / "lesson.txt")), TranscriptIngester)


def test_pick_raises_when_nothing_matches() -> None:
    with pytest.raises(IngestError, match="no ingester"):
        pick(default_ingesters(NullFetcher()), "notes.md")
