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
    PAPERS = "papers"
    HOMEWORK = "homework"
    FEEDBACK = "feedback"
    PLANS = "plans"
    TOPICS = "topics"
    GENERATION_JOBS = "generation_jobs"
    HOMEWORK_QUESTIONS = "homework_questions"
    DOCUMENT_PAGES = "document_pages"
    DOCUMENT_TOPICS = "document_topics"
    QUESTION_TOPICS = "question_topics"
    HOMEWORK_TOPICS = "homework_topics"
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
    SCAN = "scan"


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


class HomeworkFormat(StrEnum):
    MARKDOWN = "markdown"
    TYPST = "typst"


class FeedbackStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"


class PlanStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"


class PaperStatus(StrEnum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    ARCHIVED = "archived"


class GenerationKind(StrEnum):
    HOMEWORK = "homework"
    FEEDBACK = "feedback"
    PLAN = "plan"
    PAPER_EXTRACT = "paper_extract"


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
    last_access: datetime | None = None
    # Not a column: Directus keeps it on the policies behind a user and their role, and only
    # `DirectusClient.me()` resolves it. Everywhere else it stays False.
    admin_access: bool = False


class DirectusRole(Record):
    """A row of Directus's own `directus_roles`, read through `/roles`."""

    name: str
    description: str | None = None


class DirectusServerInfo(BaseModel):
    """What `/server/info` says about the Directus behind the app."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    version: str | None = None


class DirectusLicense(BaseModel):
    """`/license`, which only an admin may read."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str | None = None
    status: str | None = None


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
    # A scan of handwritten solutions: the paper they answer, and the working read off the
    # pages question by question. `text` is the whole transcription either way.
    paper: UUID | None = None
    transcription: dict[str, Any] | None = None


class Document(Record, DocumentDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class DocumentPageDraft(Draft):
    """One page of a scan: the file, and where it sits in the document."""

    document: UUID
    file: UUID
    sort: int | None = None


class DocumentPage(Record, DocumentPageDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class QuestionDraft(Draft):
    text: str
    answer: str | None = None
    subject: str | None = None
    topic: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    document: UUID | None = None
    # A question taken from a paper: `parts` and `mark_scheme` are its slice of the
    # paper's `structure`, which stays the source of truth.
    paper: UUID | None = None
    number: str | None = None
    marks: int | None = None
    answer_lines: int | None = None
    parts: list[dict[str, Any]] | None = None
    mark_scheme: dict[str, Any] | None = None


class Question(Record, QuestionDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class PaperDraft(Draft):
    title: str
    source: str | None = None
    board: str | None = None
    year: int | None = None
    time_minutes: int | None = None
    total_marks: int | None = None
    instructions: str | None = None
    status: PaperStatus = PaperStatus.DRAFT
    document: UUID | None = None
    rendered_pdf: UUID | None = None
    mark_scheme_pdf: UUID | None = None
    structure: dict[str, Any] | None = None
    mark_scheme: dict[str, Any] | None = None
    generated_from: dict[str, Any] | None = None


class Paper(Record, PaperDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class HomeworkDraft(Draft):
    student: UUID
    session: UUID | None = None
    title: str
    content: str
    format: HomeworkFormat = HomeworkFormat.MARKDOWN
    pdf: UUID | None = None
    submission_file: UUID | None = None
    compile_error: str | None = None
    due_on: date | None = None
    status: HomeworkStatus = HomeworkStatus.DRAFT
    submission: str | None = None
    submission_transcription: dict[str, Any] | None = None
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


class TopicDraft(Draft):
    name: str
    parent: UUID | None = None
    description: str | None = None
    sort: int | None = None


class Topic(Record, TopicDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class DocumentTopicDraft(Draft):
    document: UUID
    topic: UUID
    sort: int | None = None


class DocumentTopic(Record, DocumentTopicDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class QuestionTopicDraft(Draft):
    question: UUID
    topic: UUID
    sort: int | None = None


class QuestionTopic(Record, QuestionTopicDraft):
    model_config = ConfigDict(frozen=True, extra="ignore")


class HomeworkTopicDraft(Draft):
    homework: UUID
    topic: UUID
    sort: int | None = None


class HomeworkTopic(Record, HomeworkTopicDraft):
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
