"""What reads handwriting off a page, and what it must answer with."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

FAKE_MODEL = "fake"
FAKE_PREFIX = "[fake]"

# Every field is required and the optional ones nullable: a strict schema has no optional
# properties, and "the model said nothing" must stay apart from "".
_OUTPUT = ConfigDict(frozen=True, extra="forbid")


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class Page:
    """One page of a scan, as the JPEG a transcriber is given."""

    index: int
    jpeg: bytes


@dataclass(frozen=True, slots=True)
class PaperQuestion:
    """A question the pages may answer, as the paper words it."""

    number: str
    stem: str | None = None


class TranscribedQuestion(BaseModel):
    model_config = _OUTPUT

    number: str
    text: str
    confidence: Confidence
    note: str | None


class Transcription(BaseModel):
    """What was written: the whole of it as markdown, and per question when one was asked for."""

    model_config = _OUTPUT

    text: str
    confidence: Confidence
    questions: tuple[TranscribedQuestion, ...] = ()


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """The transcription, and what the call that produced it cost."""

    transcription: Transcription
    model: str
    usage: dict[str, Any] | None = None


@runtime_checkable
class Transcriber(Protocol):
    """Pages in, a transcription out. The implementation is where the model calls live."""

    @property
    def model(self) -> str: ...

    async def transcribe(
        self, pages: Sequence[Page], *, questions: Sequence[PaperQuestion] = ()
    ) -> TranscriptionResult: ...


@dataclass(slots=True)
class FakeTranscriber:
    """Reads nothing. Its answer says so, and never passes as a student's own work."""

    transcription: Transcription | None = None
    model: str = FAKE_MODEL
    pages: list[Page] = field(default_factory=list)
    questions: list[PaperQuestion] = field(default_factory=list)

    async def transcribe(
        self, pages: Sequence[Page], *, questions: Sequence[PaperQuestion] = ()
    ) -> TranscriptionResult:
        self.pages.extend(pages)
        self.questions.extend(questions)
        transcription = self.transcription or _fake(pages, questions)
        return TranscriptionResult(transcription=transcription, model=self.model, usage=None)


def _fake(pages: Sequence[Page], questions: Sequence[PaperQuestion]) -> Transcription:
    return Transcription(
        text=(f"{FAKE_PREFIX} {len(pages)} page(s) were not read: the fake transcriber is in use."),
        confidence=Confidence.LOW,
        questions=tuple(
            TranscribedQuestion(
                number=question.number,
                text=f"{FAKE_PREFIX} nothing was read for question {question.number}.",
                confidence=Confidence.LOW,
                note=None,
            )
            for question in questions
        ),
    )
