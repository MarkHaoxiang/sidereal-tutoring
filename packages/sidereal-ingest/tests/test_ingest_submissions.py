from __future__ import annotations

import io
from collections.abc import Sequence
from uuid import UUID, uuid4

import pytest
from PIL import Image
from sidereal_core.models import Collection
from sidereal_core.testing import FakeDirectus
from sidereal_ingest.documents import DocumentError
from sidereal_ingest.scan import ScanIngester
from sidereal_ingest.submissions import transcribe_submission
from sidereal_ingest.transcribe import (
    Confidence,
    FakeTranscriber,
    Page,
    PaperQuestion,
    TranscribedQuestion,
    Transcription,
    TranscriptionResult,
)

HANDED_IN = Transcription(
    text="$x = 4$",
    confidence=Confidence.MEDIUM,
    questions=(
        TranscribedQuestion(number="1", text="$x = 4$", confidence=Confidence.MEDIUM, note=None),
    ),
)


class CostedTranscriber:
    """A transcriber that says what it cost, as the OpenRouter one does."""

    model = "vision-model"

    async def transcribe(
        self, pages: Sequence[Page], *, questions: Sequence[PaperQuestion] = ()
    ) -> TranscriptionResult:
        return TranscriptionResult(HANDED_IN, self.model, {"calls": 1, "cost_usd": 0.5})


def jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (400, 300), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


def seed_homework(fake: FakeDirectus, *, file_id: str | None) -> UUID:
    homework = fake.seed(
        Collection.HOMEWORK,
        {
            "student": str(uuid4()),
            "title": "Week 3",
            "content": "## Week 3",
            "submission_file": file_id,
            "generated_from": {"job": "a-job", "usage": {"calls": 1}},
        },
    )
    for position, (number, text) in enumerate([("1", "Solve $2 x = 8$."), ("2", "Find $x^2$.")], 1):
        question = fake.seed(Collection.QUESTIONS, {"number": number, "text": text})
        fake.seed(
            Collection.HOMEWORK_QUESTIONS,
            {"homework": homework["id"], "question": question["id"], "sort": position},
        )
    return UUID(str(homework["id"]))


async def test_a_handed_in_photo_is_read_beside_the_homework_questions() -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("handin.jpg", jpeg(), media_type="image/jpeg")
    homework_id = seed_homework(fake, file_id=file_id)
    transcriber = FakeTranscriber(transcription=HANDED_IN)

    async with fake.client() as client:
        homework = await transcribe_submission(client, ScanIngester(transcriber), homework_id)

    assert [question.number for question in transcriber.questions] == ["1", "2"]
    assert transcriber.questions[0].stem == "Solve $2 x = 8$."
    assert homework.submission_transcription == {
        "text": "$x = 4$",
        "confidence": "medium",
        "questions": [{"number": "1", "text": "$x = 4$", "confidence": "medium", "note": None}],
        "model": "fake",
    }
    assert homework.submission is None


async def test_what_the_call_cost_is_filed_in_the_one_column_a_student_may_write() -> None:
    fake = FakeDirectus()
    file_id = fake.register_file("handin.jpg", jpeg(), media_type="image/jpeg")
    homework_id = seed_homework(fake, file_id=file_id)
    services = ScanIngester(CostedTranscriber())

    async with fake.client() as client:
        homework = await transcribe_submission(client, services, homework_id)

    assert homework.submission_transcription is not None
    assert homework.submission_transcription["model"] == "vision-model"
    assert homework.submission_transcription["usage"] == {"calls": 1, "cost_usd": 0.5}
    # The generation's own provenance is untouched: transcribing never writes that field.
    assert homework.generated_from == {"job": "a-job", "usage": {"calls": 1}}
    assert all(b"generated_from" not in (request.content or b"") for request in fake.requests)


async def test_a_homework_with_nothing_handed_in_says_so() -> None:
    fake = FakeDirectus()
    homework_id = seed_homework(fake, file_id=None)

    async with fake.client() as client:
        with pytest.raises(DocumentError, match="handed in"):
            await transcribe_submission(client, ScanIngester(FakeTranscriber()), homework_id)
