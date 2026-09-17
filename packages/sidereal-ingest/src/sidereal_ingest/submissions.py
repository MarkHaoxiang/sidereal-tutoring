"""A student's handed-in photo, read into typed text beside it."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sidereal_core.directus import DirectusClient
from sidereal_core.homework import ordered_questions
from sidereal_core.models import Collection, Homework

from sidereal_ingest.documents import DocumentError
from sidereal_ingest.scan import ScanFile, ScanIngester
from sidereal_ingest.transcribe import PaperQuestion, TranscriptionResult


async def transcribe_submission(
    client: DirectusClient, scanner: ScanIngester, homework_id: UUID
) -> Homework:
    """Read `submission_file` into `submission_transcription`, keyed by the homework's order."""
    homework = await client.get_item(Collection.HOMEWORK, Homework, homework_id)
    if homework.submission_file is None:
        raise DocumentError("Nothing has been handed in for this homework yet.")
    name, content = await client.download_file(homework.submission_file)
    questions = await _homework_questions(client, homework_id)
    result = await scanner.transcribe([ScanFile(name, content)], questions=questions)
    return await client.update_item(
        Collection.HOMEWORK,
        Homework,
        homework_id,
        {"submission_transcription": _transcription(result)},
    )


def _transcription(result: TranscriptionResult) -> dict[str, Any]:
    """One column holds the whole of it: a student may write this field and no other."""
    transcription = result.transcription
    payload: dict[str, Any] = {
        "text": transcription.text,
        "confidence": transcription.confidence.value,
        "questions": [question.model_dump(mode="json") for question in transcription.questions],
        "model": result.model,
    }
    if result.usage is not None:
        payload["usage"] = result.usage
    return payload


async def _homework_questions(
    client: DirectusClient, homework_id: UUID
) -> tuple[PaperQuestion, ...]:
    """The numbers the working may be filed under, in the order the homework was set."""
    return tuple(
        PaperQuestion(number=question.number or str(position), stem=question.text)
        for position, question in enumerate(await ordered_questions(client, homework_id), start=1)
    )
