from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Response
from sidereal_core.logins import (
    Identity,
    StudentLogin,
    create_login,
    identify,
    remove_login,
    reset_password,
)
from sidereal_core.models import Collection, Document, GenerationJob, GenerationKind
from sidereal_generate.jobs import JobInput, run_job, start_job
from sidereal_ingest.documents import create_document, process_document

from sidereal_app.api.models import (
    DocumentRequest,
    Health,
    JobRequest,
    LoginRequest,
    PasswordRequest,
)
from sidereal_app.deps import CurrentUser, Directus, GeneratorSet, IngesterSet

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> Health:
    """Liveness only. It does not reach Directus, so it stays up while Directus is down."""
    return Health(status="ok")


@router.get("/me")
async def me(user: CurrentUser, client: Directus) -> Identity:
    """Who is calling. A caller a `students` row points at is a student; anyone else is a tutor."""
    return await identify(client, user)


@router.post("/students/{student_id}/login", status_code=201)
async def add_student_login(
    student_id: UUID, body: LoginRequest, user: CurrentUser, client: Directus
) -> StudentLogin:
    return await create_login(client, student_id, body.email, body.password)


@router.post("/students/{student_id}/login/password", status_code=204)
async def set_student_password(
    student_id: UUID, body: PasswordRequest, user: CurrentUser, client: Directus
) -> Response:
    await reset_password(client, student_id, body.password)
    return Response(status_code=204)


@router.delete("/students/{student_id}/login", status_code=204)
async def remove_student_login(student_id: UUID, user: CurrentUser, client: Directus) -> Response:
    """The login goes; the student's work stays."""
    await remove_login(client, student_id)
    return Response(status_code=204)


@router.post("/documents", status_code=202)
async def add_document(
    body: DocumentRequest,
    user: CurrentUser,
    client: Directus,
    ingesters: IngesterSet,
    background: BackgroundTasks,
) -> Document:
    """File the material as pending and answer immediately; the row carries the outcome."""
    document = await create_document(
        client,
        body.source.to_source(),
        title=body.title,
        student=body.student_id,
        session=body.session_id,
    )
    background.add_task(process_document, client, ingesters, document.id)
    return document


@router.post("/documents/{document_id}/process", status_code=202)
async def reprocess_document(
    document_id: UUID,
    user: CurrentUser,
    client: Directus,
    ingesters: IngesterSet,
    background: BackgroundTasks,
) -> Document:
    """Read the material again — what a tutor's Retry on a failed row does."""
    document = await client.get_item(Collection.DOCUMENTS, Document, document_id)
    background.add_task(process_document, client, ingesters, document.id)
    return document


@router.post("/jobs/{kind}", status_code=202)
async def create_job(
    kind: GenerationKind,
    body: JobRequest,
    user: CurrentUser,
    client: Directus,
    generators: GeneratorSet,
    background: BackgroundTasks,
) -> GenerationJob:
    """Queue a generation and answer immediately; the job row carries the outcome."""
    job = await start_job(
        client,
        kind,
        JobInput(
            student=body.student_id,
            documents=tuple(body.document_ids),
            instructions=body.instructions,
            period_start=body.period_start,
            period_end=body.period_end,
        ),
        model=generators.for_kind(kind),
    )
    background.add_task(run_job, client, generators, job.id)
    return job


@router.get("/jobs/{job_id}")
async def read_job(job_id: UUID, user: CurrentUser, client: Directus) -> GenerationJob:
    return await client.get_item(Collection.GENERATION_JOBS, GenerationJob, job_id)
