"""Every MCP tool's body. Thin: each one calls core, ingest or generate and returns a model."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from enum import Enum
from importlib.metadata import version
from typing import Any
from uuid import UUID

from sidereal_core import logins, tutors
from sidereal_core.logins import Identity, StudentLogin
from sidereal_core.models import (
    Collection,
    Document,
    DocumentKind,
    GenerationJob,
    GenerationKind,
    Homework,
    HomeworkFormat,
    JobStatus,
    Paper,
    Student,
    StudentStatus,
)
from sidereal_core.students import visible_student
from sidereal_core.tutors import AdminHealth, AdminJob, TutorAccount, TutorStatus
from sidereal_generate.jobs import JobInput, run_job, start_job
from sidereal_generate.papers import WorksheetResult, paper_worksheet, rerender_paper
from sidereal_generate.settings import generate_settings
from sidereal_generate.typst import recompile_homework
from sidereal_ingest.documents import PathSource, UrlSource, create_document, process_document
from sidereal_ingest.web import SCHEMES

from sidereal_mcp.services import Services

DEFAULT_LIMIT = 50
VERSION = version("sidereal-mcp")


async def list_students(
    services: Services, status: StudentStatus | None = None, limit: int = DEFAULT_LIMIT
) -> list[Student]:
    return await services.directus.list_items(
        Collection.STUDENTS, Student, filter=_eq(status=status), limit=limit, sort=["name"]
    )


async def get_student(services: Services, student_id: UUID) -> Student:
    return await services.directus.get_item(Collection.STUDENTS, Student, student_id)


async def whoami(services: Services) -> Identity:
    return await logins.whoami(services.directus)


async def create_student_login(
    services: Services, student_id: UUID, email: str, password: str
) -> StudentLogin:
    return await logins.create_login(services.directus, student_id, email, password)


async def reset_student_password(
    services: Services, student_id: UUID, password: str
) -> StudentLogin:
    return await logins.reset_password(services.directus, student_id, password)


async def remove_student_login(services: Services, student_id: UUID) -> Student:
    return await logins.remove_login(services.directus, student_id)


async def list_documents(
    services: Services,
    student_id: UUID | None = None,
    kind: DocumentKind | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[Document]:
    return await services.directus.list_items(
        Collection.DOCUMENTS,
        Document,
        filter=_eq(student=student_id, kind=kind),
        limit=limit,
        sort=["-date_created"],
    )


async def ingest_source(
    services: Services,
    source: str,
    kind: DocumentKind | None = None,
    student_id: UUID | None = None,
    session_id: UUID | None = None,
) -> Document:
    """Turn a transcript file, URL or upload into a `documents` row, read to completion.

    `kind` overrides how the row is filed; which ingester runs is decided by `source`. A
    source that could not be read comes back as a `failed` row carrying the reason.
    """
    if student_id is not None:
        await visible_student(services.directus, student_id)
    document = await create_document(
        services.directus,
        UrlSource(source) if source.startswith(SCHEMES) else PathSource(source),
        kind=kind,
        student=student_id,
        session=session_id,
    )
    return await process_document(services.directus, services.ingesters, document.id)


async def generate_homework(
    services: Services,
    student_id: UUID,
    document_ids: Sequence[UUID] = (),
    instructions: str | None = None,
    format: HomeworkFormat = HomeworkFormat.MARKDOWN,  # noqa: A002 - the domain's field name.
) -> GenerationJob:
    return await _generate(
        services,
        GenerationKind.HOMEWORK,
        JobInput(
            student=student_id,
            documents=tuple(document_ids),
            instructions=instructions,
            format=format,
        ),
    )


async def extract_paper(services: Services, document_id: UUID) -> GenerationJob:
    """Read one ready document into a `papers` row, its PDFs and its `questions` rows."""
    return await _generate(
        services, GenerationKind.PAPER_EXTRACT, JobInput(documents=(document_id,))
    )


async def render_paper(services: Services, paper_id: UUID) -> Paper:
    return await rerender_paper(services.directus, services.typeset, paper_id)


async def paper_worksheet_pdf(
    services: Services,
    paper_id: UUID,
    question_numbers: Sequence[str],
    student_id: UUID | None = None,
    title: str | None = None,
    due: date | None = None,
) -> WorksheetResult:
    return await paper_worksheet(
        services.directus,
        services.typeset,
        paper_id,
        question_numbers,
        student_id=student_id,
        title=title,
        due=due,
    )


async def preview_typst(services: Services, source: str) -> list[str]:
    """Render Typst source to one SVG per page. Source that will not compile raises."""
    return await services.typeset.render_svg(source)


async def compile_homework(services: Services, homework_id: UUID) -> Homework:
    return await recompile_homework(services.directus, services.typeset, homework_id)


async def generate_feedback(
    services: Services,
    student_id: UUID,
    document_ids: Sequence[UUID] = (),
    instructions: str | None = None,
) -> GenerationJob:
    return await _generate(
        services,
        GenerationKind.FEEDBACK,
        JobInput(student=student_id, documents=tuple(document_ids), instructions=instructions),
    )


async def generate_plan(
    services: Services,
    student_id: UUID,
    document_ids: Sequence[UUID] = (),
    instructions: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> GenerationJob:
    return await _generate(
        services,
        GenerationKind.PLAN,
        JobInput(
            student=student_id,
            documents=tuple(document_ids),
            instructions=instructions,
            period_start=period_start,
            period_end=period_end,
        ),
    )


async def list_generation_jobs(
    services: Services, status: JobStatus | None = None, limit: int = DEFAULT_LIMIT
) -> list[GenerationJob]:
    return await services.directus.list_items(
        Collection.GENERATION_JOBS,
        GenerationJob,
        filter=_eq(status=status),
        limit=limit,
        sort=["-date_created"],
    )


async def update_generation_job(
    services: Services, job_id: UUID, status: JobStatus, error: str | None = None
) -> GenerationJob:
    return await services.directus.update_item(
        Collection.GENERATION_JOBS,
        GenerationJob,
        job_id,
        {"status": status.value, "error": error},
    )


async def list_tutors(services: Services) -> list[TutorAccount]:
    return await tutors.list_tutors(services.directus)


async def create_tutor(
    services: Services,
    email: str,
    password: str,
    first_name: str | None = None,
    last_name: str | None = None,
) -> TutorAccount:
    return await tutors.create_tutor(services.directus, email, password, first_name, last_name)


async def reset_tutor_password(services: Services, user_id: UUID, password: str) -> TutorAccount:
    return await tutors.reset_tutor_password(services.directus, user_id, password)


async def set_tutor_status(services: Services, user_id: UUID, status: TutorStatus) -> TutorAccount:
    return await tutors.set_tutor_status(services.directus, user_id, status)


async def remove_tutor(services: Services, user_id: UUID) -> None:
    await tutors.remove_tutor(services.directus, user_id)


async def list_jobs(
    services: Services, status: JobStatus | None = None, limit: int = DEFAULT_LIMIT
) -> list[AdminJob]:
    return await tutors.list_jobs(services.directus, status, limit)


async def admin_health(services: Services) -> AdminHealth:
    settings = generate_settings()
    return await tutors.admin_health(
        services.directus,
        services.typeset,
        api_version=VERSION,
        backend=settings.backend.value,
        model=settings.model,
    )


async def _generate(services: Services, kind: GenerationKind, job_input: JobInput) -> GenerationJob:
    # Directus cannot check a create through a relation, so the student is read first.
    if job_input.student is not None:
        await visible_student(services.directus, job_input.student)
    job = await start_job(
        services.directus, kind, job_input, model=services.generators.for_kind(kind)
    )
    return await run_job(services.directus, services.generators, job.id, typeset=services.typeset)


def _eq(**fields: object) -> dict[str, Any] | None:
    """Directus `_eq` clauses for the arguments that were actually given."""
    clauses = {
        name: {"_eq": value.value if isinstance(value, Enum) else str(value)}
        for name, value in fields.items()
        if value is not None
    }
    return clauses or None
