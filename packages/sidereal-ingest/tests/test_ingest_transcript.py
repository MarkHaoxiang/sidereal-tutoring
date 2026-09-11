from __future__ import annotations

from pathlib import Path

import pytest
from sidereal_core.models import DocumentKind, DocumentStatus
from sidereal_ingest.base import IngestError
from sidereal_ingest.transcript import TranscriptIngester, strip_timestamps

FIXTURES = Path(__file__).parent / "fixtures"


async def test_vtt_keeps_speech_and_drops_everything_else() -> None:
    draft = await TranscriptIngester().ingest(str(FIXTURES / "lesson.vtt"))

    assert draft.kind is DocumentKind.TRANSCRIPT
    assert draft.status is DocumentStatus.READY
    assert draft.title == "lesson"
    assert draft.text == (
        "Today we are factorising quadratics.\n"
        "Start by looking for two numbers that multiply to six."
    )
    assert draft.metadata == {"filename": "lesson.vtt", "format": "vtt"}


async def test_srt_comma_timings_are_stripped() -> None:
    draft = await TranscriptIngester().ingest(str(FIXTURES / "lesson.srt"))

    assert draft.text == ("Let's look at the homework first.\nQuestion three asked for the roots.")


async def test_plain_text_transcript_loses_its_leading_stamps() -> None:
    draft = await TranscriptIngester().ingest(str(FIXTURES / "lesson.txt"))

    assert draft.text == (
        "Tutor: We will start with the recap.\nStudent: I got stuck on question two."
    )


def test_supports_only_transcript_suffixes() -> None:
    ingester = TranscriptIngester()

    assert ingester.supports("a/b/lesson.VTT")
    assert not ingester.supports("a/b/lesson.pdf")


async def test_an_unsupported_suffix_is_an_ingest_error() -> None:
    with pytest.raises(IngestError):
        await TranscriptIngester().ingest("lesson.pdf")


async def test_a_missing_file_is_an_ingest_error(tmp_path: Path) -> None:
    with pytest.raises(IngestError):
        await TranscriptIngester().ingest(str(tmp_path / "absent.vtt"))


def test_hour_length_timings_are_recognised() -> None:
    raw = "00:00:01.000 --> 00:00:04.000\nspeech\n1:02:03.500 --> 1:02:05.000\nmore"

    assert strip_timestamps(raw) == "speech\nmore"
