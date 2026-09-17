from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sidereal_core.canonical import (
    CanonicalMarkScheme,
    CanonicalMarkSchemeQuestion,
    CanonicalMarkup,
    CanonicalPaper,
    CanonicalQuestion,
    CanonicalWorksheet,
    RenderKind,
    RenderOutput,
)
from sidereal_core.logins import AccountStatus
from sidereal_core.models import HomeworkFormat
from sidereal_core.tutors import TutorStatus
from sidereal_ingest.documents import FileSource, ScanSource, TextSource, UrlSource
from sidereal_ingest.web import SCHEMES


class Health(BaseModel):
    status: Literal["ok"]


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str


class AccountState(BaseModel):
    """All anyone refused at sign-in is told: whether that account may sign in at all."""

    status: AccountStatus


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # `paper_extract` is the one kind with no student: a paper is library material.
    student_id: UUID | None = None
    document_ids: list[UUID] = []
    # Feedback only: the hand-ins it is about, questions, answers and marks included.
    homework_ids: list[UUID] = []
    instructions: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    format: HomeworkFormat = HomeworkFormat.MARKDOWN
    pages: bool | None = None


class WorksheetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_numbers: list[str] = Field(min_length=1)
    student_id: UUID | None = None
    title: str | None = None
    due: date | None = None


class MarkSchemeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: UUID


class TypstRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str


class TypstPreview(BaseModel):
    """One SVG per page, ready to drop into the tutor's editor."""

    pages: list[str]


class RenderBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: Literal[RenderOutput.SVG, RenderOutput.SOURCE] = RenderOutput.SVG
    assets: dict[str, str] = Field(default_factory=dict)


class PaperRenderRequest(RenderBase):
    kind: Literal[RenderKind.PAPER]
    document: CanonicalPaper


class MarkSchemeRenderRequest(RenderBase):
    kind: Literal[RenderKind.MARK_SCHEME]
    document: CanonicalMarkScheme


class WorksheetRenderRequest(RenderBase):
    kind: Literal[RenderKind.WORKSHEET]
    document: CanonicalWorksheet


class QuestionRenderRequest(RenderBase):
    kind: Literal[RenderKind.QUESTION]
    document: CanonicalQuestion
    mark_scheme: CanonicalMarkSchemeQuestion | None = None


class MarkupRenderRequest(RenderBase):
    kind: Literal[RenderKind.MARKUP]
    document: CanonicalMarkup


type RenderRequest = Annotated[
    PaperRenderRequest
    | MarkSchemeRenderRequest
    | WorksheetRenderRequest
    | QuestionRenderRequest
    | MarkupRenderRequest,
    Field(discriminator="kind"),
]


class TypstRender(BaseModel):
    """`pages` is empty when `output` is `source`, and `source` is null when it is `svg`."""

    pages: list[str]
    source: str | None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class PasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str


class TutorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str
    first_name: str | None = None
    last_name: str | None = None


class TutorStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TutorStatus


class FileSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["file"]
    file_id: UUID

    def to_source(self) -> FileSource:
        return FileSource(self.file_id)


class UrlSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["url"]
    url: str

    @field_validator("url")
    @classmethod
    def _http_only(cls, url: str) -> str:
        if not url.startswith(SCHEMES):
            raise ValueError("a link must start with http:// or https://")
        return url

    def to_source(self) -> UrlSource:
        return UrlSource(self.url)


class ScanSourceRequest(BaseModel):
    """Handwritten pages, in reading order, and the paper they answer when they answer one."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["scan"]
    file_ids: list[UUID] = Field(min_length=1)
    paper_id: UUID | None = None

    def to_source(self) -> ScanSource:
        return ScanSource(tuple(self.file_ids), self.paper_id)


class TextSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["text"]
    text: str

    def to_source(self) -> TextSource:
        return TextSource(self.text)


type DocumentSourceRequest = Annotated[
    FileSourceRequest | ScanSourceRequest | UrlSourceRequest | TextSourceRequest,
    Field(discriminator="type"),
]


class DocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID | None = None
    session_id: UUID | None = None
    title: str | None = None
    source: DocumentSourceRequest
