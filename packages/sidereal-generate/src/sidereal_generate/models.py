"""What a generator is asked for, and what it must return."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field
from sidereal_core.models import Document, Student

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


class FeedbackOutput(BaseModel):
    model_config = _OUTPUT

    content: str


class PlanOutput(BaseModel):
    model_config = _OUTPUT

    title: str
    content: str
