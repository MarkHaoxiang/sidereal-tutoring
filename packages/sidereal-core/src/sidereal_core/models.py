"""The shared vocabulary: one pydantic model per Directus collection."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Collection(StrEnum):
    STUDENTS = "students"
    SESSIONS = "sessions"
    DOCUMENTS = "documents"
    QUESTIONS = "questions"
    HOMEWORK = "homework"
    FEEDBACK = "feedback"
    PLANS = "plans"
    GENERATION_JOBS = "generation_jobs"
    HOMEWORK_QUESTIONS = "homework_questions"
    DIRECTUS_USERS = "directus_users"
    DIRECTUS_ROLES = "directus_roles"


class StudentStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class SessionStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DocumentKind(StrEnum):
    TRANSCRIPT = "transcript"
    WEB_PAGE = "web_page"
    QUESTION_BANK = "question_bank"
    UPLOAD = "upload"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class HomeworkStatus(StrEnum):
    DRAFT = "draft"
    ASSIGNED = "assigned"
    SUBMITTED = "submitted"
    MARKED = "marked"


class FeedbackStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"


class GenerationKind(StrEnum):
    HOMEWORK = "homework"
    FEEDBACK = "feedback"
    PLAN = "plan"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Draft(BaseModel):
    """Fields a caller supplies on creation. Directus owns the id and the audit trail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    def payload(self) -> dict[str, Any]:
        """The create/update body. `None` means "unset", not "write null"."""
        return self.model_dump(mode="json", exclude_none=True)


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    id: UUID
    date_created: datetime | None = None
    date_updated: datetime | None = None
    user_created: UUID | None = None
    user_updated: UUID | None = None


class DirectusUser(Record):
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    role: UUID | None = None
    status: str | None = None


class DirectusRole(Record):
    """A row of Directus's own `directus_roles`, read through `/roles`."""

    name: str
    description: str | None = None


class DirectusFile(Record):
    """A row of Directus's own `directus_files`, read through `/files/{id}`."""

    filename_download: str
    filename_disk: str | None = None
    title: str | None = None
    type: str | None = None
    filesize: int | None = None


class StudentDraft(Draft):
    name: str
    level: str | None = None
    subjects: list[str] = Field(default_factory=list)
    notes: str | None = None
    tutor: UUID | None = None
    user: UUID | None = None
    status: StudentStatus = StudentStatus.ACTIVE

    @field_validator("subjects", mode="before")
    @classmethod
    def _null_is_empty(cls, value: Any) -> Any:
        """A student with no subjects is `null` in Directus, not `[]`."""
        return [] if value is None else value


class Student(Record, StudentDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class SessionDraft(Draft):
    student: UUID
    tutor: UUID | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = None
    notes: str | None = None
    status: SessionStatus = SessionStatus.SCHEDULED


class Session(Record, SessionDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class DocumentDraft(Draft):
    title: str
    kind: DocumentKind
    source_url: str | None = None
    file: UUID | None = None
    text: str | None = None
    student: UUID | None = None
    session: UUID | None = None
    status: DocumentStatus = DocumentStatus.PENDING
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Document(Record, DocumentDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class QuestionDraft(Draft):
    text: str
    answer: str | None = None
    subject: str | None = None
    topic: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    document: UUID | None = None


class Question(Record, QuestionDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class HomeworkDraft(Draft):
    student: UUID
    session: UUID | None = None
    title: str
    content: str
    due_on: date | None = None
    status: HomeworkStatus = HomeworkStatus.DRAFT
    submission: str | None = None
    submitted_at: datetime | None = None
    generated_from: dict[str, Any] | None = None


class Homework(Record, HomeworkDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class HomeworkQuestionDraft(Draft):
    homework: UUID
    question: UUID
    sort: int | None = None


class HomeworkQuestion(Record, HomeworkQuestionDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class FeedbackDraft(Draft):
    student: UUID
    session: UUID | None = None
    content: str
    status: FeedbackStatus = FeedbackStatus.DRAFT
    generated_from: dict[str, Any] | None = None


class Feedback(Record, FeedbackDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class PlanDraft(Draft):
    student: UUID
    title: str
    content: str
    period_start: date | None = None
    period_end: date | None = None
    status: PlanStatus = PlanStatus.DRAFT
    generated_from: dict[str, Any] | None = None


class Plan(Record, PlanDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class GenerationJobDraft(Draft):
    kind: GenerationKind
    student: UUID | None = None
    status: JobStatus = JobStatus.QUEUED
    input: dict[str, Any] = Field(default_factory=dict)
    output_collection: str | None = None
    output_id: UUID | None = None
    error: str | None = None
    model: str | None = None


class GenerationJob(Record, GenerationJobDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")
