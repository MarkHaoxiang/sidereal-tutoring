"""What a generator is asked for, and what it must return."""

from __future__ import annotations

import math
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sidereal_core.canonical import CanonicalMarkScheme, CanonicalPaper
from sidereal_core.models import Document, HomeworkFormat, Student

# Every output field is required, optional ones nullable: a strict tool schema has no
# optional properties, and "the model did not say" must stay distinguishable from "".
_OUTPUT = ConfigDict(frozen=True, extra="forbid")


class GenerationRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    student: Student
    documents: tuple[Document, ...] = ()
    instructions: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    # Homework only: it decides whether `content` comes back as markdown or as a Typst body.
    format: HomeworkFormat = HomeworkFormat.MARKDOWN


class GeneratedQuestion(BaseModel):
    model_config = _OUTPUT

    text: str
    answer: str | None
    topic: str | None
    difficulty: int | None = Field(ge=1, le=5)


class HomeworkOutput(BaseModel):
    model_config = _OUTPUT

    title: str
    content: str
    questions: tuple[GeneratedQuestion, ...]


class FigureRequest(BaseModel):
    """Where one drawn thing sits on a page image, and which node of the paper needs it."""

    model_config = _OUTPUT

    page: int
    # A plain array: a tuple or a length-bounded list carries the array keywords a strict
    # structured-output schema refuses.
    bbox: list[float]
    caption: str | None
    question_number: str
    part_label: str | None

    @field_validator("bbox")
    @classmethod
    def _is_a_box(cls, value: list[float]) -> list[float]:
        if len(value) != 4 or not all(math.isfinite(number) for number in value):
            raise ValueError("bbox: four finite numbers, x0, y0, x1, y1")
        return value

    @property
    def region(self) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = self.bbox
        return x0, y0, x1, y1


class PaperExtraction(BaseModel):
    """What the paper call returns. The mark scheme is a call and a schema of its own."""

    model_config = _OUTPUT

    paper: CanonicalPaper
    # Required like every other output field: an omitted key must be a validation error, never
    # an empty list a paper with figures is indistinguishable from.
    figures: tuple[FigureRequest, ...]


class MarkSchemeExtraction(BaseModel):
    model_config = _OUTPUT

    mark_scheme: CanonicalMarkScheme


class FeedbackOutput(BaseModel):
    model_config = _OUTPUT

    content: str


class PlanOutput(BaseModel):
    model_config = _OUTPUT

    title: str
    content: str
