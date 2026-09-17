"""The canonical document structures, mirroring `services/typeset/src/document.rs`.

Both sides forbid unknown fields, so a name that drifts is an error on the first render
rather than a value that silently disappears.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# The renderer's caps: nothing here can ask for what will not fit on A4.
MAX_ANSWER_LINES = 60
MAX_ANSWER_HEIGHT_MM = 250
MAX_ANSWER_OPTIONS = 26
MAX_GRID_ROWS = 40
MAX_GRID_COLS = 26
MAX_TABLE_ROWS = 40
MAX_TABLE_COLS = 12
MAX_FIGURE_WIDTH_MM = 165

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


class AnswerKind(StrEnum):
    LINES = "lines"
    BOX = "box"
    MULTIPLE_CHOICE = "multiple_choice"
    ESSAY = "essay"
    GRID = "grid"
    TABLE = "table"
    NONE = "none"


def _capped(value: int | None) -> int | None:
    if value is not None and not 0 <= value <= MAX_ANSWER_LINES:
        raise ValueError(f"answer_lines is 0 to {MAX_ANSWER_LINES}")
    return value


def _extent(value: int | None, maximum: int, name: str) -> None:
    if value is None:
        raise ValueError(f"{name}: this answer type needs both rows and cols")
    if not 1 <= value <= maximum:
        raise ValueError(f"{name}: 1 to {maximum}")


def _one_spelling(answer_lines: int | None, answer: CanonicalAnswer | None) -> None:
    if answer_lines is not None and answer is not None:
        raise ValueError("answer_lines is the deprecated spelling of answer; send one or the other")


class CanonicalAnswerOption(BaseModel):
    model_config = _CANONICAL

    label: str | None = None
    text: str


class CanonicalAnswer(BaseModel):
    """The space a student writes in. `type` decides which of the other fields are read."""

    model_config = _CANONICAL

    type: AnswerKind
    lines: int | None = None
    options: tuple[CanonicalAnswerOption, ...] = ()
    height_mm: int | None = None
    rows: int | None = None
    cols: int | None = None

    @model_validator(mode="after")
    def _within_the_page(self) -> Self:
        match self.type:
            case AnswerKind.LINES:
                if self.lines is not None and self.lines > MAX_ANSWER_LINES:
                    raise ValueError(f"lines: at most {MAX_ANSWER_LINES} ruled lines")
            case AnswerKind.BOX | AnswerKind.ESSAY:
                if self.height_mm is not None and self.height_mm > MAX_ANSWER_HEIGHT_MM:
                    raise ValueError(f"height_mm: at most {MAX_ANSWER_HEIGHT_MM} mm")
            case AnswerKind.MULTIPLE_CHOICE:
                if not 1 <= len(self.options) <= MAX_ANSWER_OPTIONS:
                    raise ValueError(f"options: 1 to {MAX_ANSWER_OPTIONS} options")
            case AnswerKind.GRID:
                _extent(self.rows, MAX_GRID_ROWS, "rows")
                _extent(self.cols, MAX_GRID_COLS, "cols")
            case AnswerKind.TABLE:
                _extent(self.rows, MAX_TABLE_ROWS, "rows")
                _extent(self.cols, MAX_TABLE_COLS, "cols")
            case AnswerKind.NONE:
                pass
        return self


class CanonicalPassageBlock(BaseModel):
    model_config = _CANONICAL

    type: Literal["passage"] = "passage"
    title: str | None = None
    text: str


class CanonicalPassageRefBlock(BaseModel):
    """Points at a `CanonicalPaper.passages` entry, printed once at the start of the paper."""

    model_config = _CANONICAL

    type: Literal["passage_ref"] = "passage_ref"
    id: str


class CanonicalCodeBlock(BaseModel):
    model_config = _CANONICAL

    type: Literal["code"] = "code"
    language: str | None = None
    text: str


class CanonicalTableBlock(BaseModel):
    model_config = _CANONICAL

    type: Literal["table"] = "table"
    caption: str | None = None
    header: tuple[str, ...] | None = None
    rows: tuple[tuple[str, ...], ...] = ()

    @model_validator(mode="after")
    def _rectangular(self) -> Self:
        if self.header:
            columns = len(self.header)
        elif self.rows and self.rows[0]:
            columns = len(self.rows[0])
        else:
            raise ValueError("rows: a table needs a header or at least one row")
        if columns > MAX_TABLE_COLS:
            raise ValueError(f"header: at most {MAX_TABLE_COLS} columns")
        if len(self.rows) > MAX_TABLE_ROWS:
            raise ValueError(f"rows: at most {MAX_TABLE_ROWS} rows")
        for index, row in enumerate(self.rows):
            if len(row) != columns:
                raise ValueError(
                    f"rows[{index}]: {len(row)} cells where the table has {columns} columns"
                )
        return self


class CanonicalFigureBlock(BaseModel):
    """`asset` names one of the render request's assets, never a path."""

    model_config = _CANONICAL

    type: Literal["figure"] = "figure"
    asset: str
    caption: str | None = None
    width_mm: int | None = None

    @model_validator(mode="after")
    def _within_the_column(self) -> Self:
        if self.width_mm is not None and not 1 <= self.width_mm <= MAX_FIGURE_WIDTH_MM:
            raise ValueError(f"width_mm: 1 to {MAX_FIGURE_WIDTH_MM} mm, the text column")
        return self


# A plain union, never `Field(discriminator=...)`: a discriminated union is `oneOf` in JSON
# schema, which strict structured output refuses. The `type` literals do the same work.
type CanonicalBlock = (
    CanonicalPassageBlock
    | CanonicalPassageRefBlock
    | CanonicalCodeBlock
    | CanonicalTableBlock
    | CanonicalFigureBlock
)


class CanonicalPassage(BaseModel):
    model_config = _CANONICAL

    id: str
    title: str | None = None
    text: str


class CanonicalSubPart(BaseModel):
    model_config = _CANONICAL

    label: str
    text: str
    marks: int | None = None
    answer_lines: int | None = None
    answer: CanonicalAnswer | None = None
    blocks: tuple[CanonicalBlock, ...] = ()

    _cap = field_validator("answer_lines")(_capped)

    @model_validator(mode="after")
    def _one_answer_spelling(self) -> Self:
        _one_spelling(self.answer_lines, self.answer)
        return self


class CanonicalPart(BaseModel):
    """`(a)` then `(i)`: parts nest one level."""

    model_config = _CANONICAL

    label: str
    text: str
    marks: int | None = None
    answer_lines: int | None = None
    answer: CanonicalAnswer | None = None
    blocks: tuple[CanonicalBlock, ...] = ()
    parts: tuple[CanonicalSubPart, ...] = ()

    _cap = field_validator("answer_lines")(_capped)

    @model_validator(mode="after")
    def _one_answer_spelling(self) -> Self:
        _one_spelling(self.answer_lines, self.answer)
        return self


class CanonicalQuestion(BaseModel):
    model_config = _CANONICAL

    number: str
    stem: str | None = None
    marks: int | None = None
    parts: tuple[CanonicalPart, ...] = ()
    answer_lines: int | None = None
    answer: CanonicalAnswer | None = None
    blocks: tuple[CanonicalBlock, ...] = ()

    _cap = field_validator("answer_lines")(_capped)

    @model_validator(mode="after")
    def _one_answer_spelling(self) -> Self:
        _one_spelling(self.answer_lines, self.answer)
        return self


class CanonicalSection(BaseModel):
    """A run of questions under one heading; `choose` is how many the student answers."""

    model_config = _CANONICAL

    title: str | None = None
    instructions: str | None = None
    choose: int | None = None
    questions: tuple[CanonicalQuestion, ...] = ()

    @model_validator(mode="after")
    def _choice_is_answerable(self) -> Self:
        if self.choose is not None and not 1 <= self.choose <= len(self.questions):
            raise ValueError(
                f"choose: the section offers {len(self.questions)} questions, "
                f"so {self.choose} cannot be chosen"
            )
        return self


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
    sections: tuple[CanonicalSection, ...] = ()
    passages: tuple[CanonicalPassage, ...] = ()


class CanonicalMarkSchemePart(BaseModel):
    model_config = _CANONICAL

    label: str
    answer: str
    marks: int | None = None
    notes: str | None = None
    blocks: tuple[CanonicalBlock, ...] = ()


class CanonicalMarkSchemeQuestion(BaseModel):
    model_config = _CANONICAL

    number: str
    parts: tuple[CanonicalMarkSchemePart, ...] = ()
    answer: str | None = None
    notes: str | None = None
    blocks: tuple[CanonicalBlock, ...] = ()


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
