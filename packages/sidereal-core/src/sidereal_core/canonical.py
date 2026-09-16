"""The canonical document structures, mirroring `services/typeset/src/document.rs`.

Both sides forbid unknown fields, so a name that drifts is an error on the first render
rather than a value that silently disappears.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

# The renderer's cap: a page holds about thirty-five ruled lines.
MAX_ANSWER_LINES = 60

# Optional fields carry defaults so a structure a tutor edited by hand still reads. The
# strict tool schema an extractor sends is built from these models, not stored on them.
_CANONICAL = ConfigDict(frozen=True, extra="forbid")


class RenderKind(StrEnum):
    PAPER = "paper"
    MARK_SCHEME = "mark_scheme"
    WORKSHEET = "worksheet"
    QUESTION = "question"
    MARKUP = "markup"


class RenderOutput(StrEnum):
    PDF = "pdf"
    SVG = "svg"
    SOURCE = "source"


def _capped(value: int | None) -> int | None:
    if value is not None and not 0 <= value <= MAX_ANSWER_LINES:
        raise ValueError(f"answer_lines is 0 to {MAX_ANSWER_LINES}")
    return value


class CanonicalSubPart(BaseModel):
    """`(a)` then `(i)`: parts nest one level, so a part of a part holds none of its own."""

    model_config = _CANONICAL

    label: str
    text: str
    marks: int | None = None
    answer_lines: int | None = None

    _cap = field_validator("answer_lines")(_capped)


class CanonicalPart(BaseModel):
    model_config = _CANONICAL

    label: str
    text: str
    marks: int | None = None
    answer_lines: int | None = None
    parts: tuple[CanonicalSubPart, ...] = ()

    _cap = field_validator("answer_lines")(_capped)


class CanonicalQuestion(BaseModel):
    model_config = _CANONICAL

    number: str
    stem: str | None = None
    marks: int | None = None
    parts: tuple[CanonicalPart, ...] = ()
    answer_lines: int | None = None

    _cap = field_validator("answer_lines")(_capped)


class CanonicalPaper(BaseModel):
    model_config = _CANONICAL

    title: str
    source: str | None = None
    board: str | None = None
    year: int | None = None
    time_minutes: int | None = None
    total_marks: int | None = None
    instructions: str | None = None
    questions: tuple[CanonicalQuestion, ...] = ()


class CanonicalMarkSchemePart(BaseModel):
    model_config = _CANONICAL

    label: str
    answer: str
    marks: int | None = None
    notes: str | None = None


class CanonicalMarkSchemeQuestion(BaseModel):
    model_config = _CANONICAL

    number: str
    parts: tuple[CanonicalMarkSchemePart, ...] = ()
    answer: str | None = None
    notes: str | None = None


class CanonicalMarkScheme(BaseModel):
    model_config = _CANONICAL

    title: str
    questions: tuple[CanonicalMarkSchemeQuestion, ...] = ()


class CanonicalWorksheet(BaseModel):
    model_config = _CANONICAL

    title: str
    student: str | None = None
    due: str | None = None
    intro: str | None = None
    questions: tuple[CanonicalQuestion, ...] = ()


class CanonicalMarkup(BaseModel):
    """Typst markup on its own, for a fragment that has no structure to walk."""

    model_config = _CANONICAL

    text: str


type CanonicalDocument = (
    CanonicalPaper | CanonicalMarkScheme | CanonicalWorksheet | CanonicalQuestion | CanonicalMarkup
)
