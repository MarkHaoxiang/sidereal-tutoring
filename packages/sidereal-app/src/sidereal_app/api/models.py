from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sidereal_ingest.documents import FileSource, TextSource, UrlSource
from sidereal_ingest.web import SCHEMES


class Health(BaseModel):
    status: Literal["ok"]


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID
    document_ids: list[UUID] = []
    instructions: str | None = None
    period_start: date | None = None
    period_end: date | None = None


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


class TextSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["text"]
    text: str

    def to_source(self) -> TextSource:
        return TextSource(self.text)


type DocumentSourceRequest = Annotated[
    FileSourceRequest | UrlSourceRequest | TextSourceRequest, Field(discriminator="type")
]


class DocumentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: UUID | None = None
    session_id: UUID | None = None
    title: str | None = None
    source: DocumentSourceRequest
