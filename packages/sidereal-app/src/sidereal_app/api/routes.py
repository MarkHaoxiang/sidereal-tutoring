from __future__ import annotations

import base64
from collections.abc import Mapping
from importlib.metadata import version
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response
from sidereal_core.canonical import RenderOutput
from sidereal_core.logins import (
    CallerRole,
    Identity,
    StudentLogin,
    create_login,
    identify,
    remove_login,
    reset_password,
)
from sidereal_core.models import (
    Collection,
    Document,
    GenerationJob,
    GenerationKind,
    Homework,
    HomeworkFormat,
    JobStatus,
    Paper,
)
from sidereal_core.students import visible_student
from sidereal_core.tutors import (
    DEFAULT_JOB_LIMIT,
    AdminHealth,
    AdminJob,
    TutorAccount,
    admin_health,
    create_tutor,
    list_jobs,
    list_tutors,
    remove_tutor,
    reset_tutor_password,
    set_tutor_status,
)
from sidereal_generate.jobs import JobInput, run_job, start_job
from sidereal_generate.papers import WorksheetResult, paper_worksheet, rerender_paper
from sidereal_generate.settings import generate_settings
from sidereal_generate.typst import recompile_homework
from sidereal_ingest.documents import create_document, process_document
from sidereal_ingest.submissions import transcribe_submission

from sidereal_app.api.errors import (
    ASSET_UNREADABLE,
    DOCUMENT_REQUIRED,
    FORMAT_UNSUPPORTED,
    PAGES_UNSUPPORTED,
    STUDENT_REQUIRED,
    TUTOR_ONLY,
    detail,
)
from sidereal_app.api.models import (
    DocumentRequest,
    Health,
    JobRequest,
    LoginRequest,
    PasswordRequest,
    QuestionRenderRequest,
    RenderRequest,
    TutorRequest,
    TutorStatusRequest,
    TypstPreview,
    TypstRender,
    TypstRequest,
    WorksheetRequest,
)
from sidereal_app.deps import (
    Admin,
    CurrentUser,
    Directus,
    GeneratorSet,
    IngesterSet,
    Scanner,
    Tutor,
    Typeset,
)

VERSION = version("sidereal-app")

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> Health:
    """Liveness only. It does not reach Directus, so it stays up while Directus is down."""
    return Health(status="ok")


@router.get("/me")
async def me(user: CurrentUser, client: Directus) -> Identity:
    """Who is calling: an admin by their policies, a student by a `students` row, else a tutor."""
    return await identify(client, user)


@router.get("/admin/health")
async def read_admin_health(admin: Admin, client: Directus, typeset: Typeset) -> AdminHealth:
    """Every service the practice runs on. A service that is down is `ok: false`, not an error."""
    settings = generate_settings()
    return await admin_health(
        client,
        typeset,
        api_version=VERSION,
        backend=settings.backend.value,
        model=settings.active_model,
    )


@router.get("/admin/tutors")
async def read_tutors(admin: Admin, client: Directus) -> list[TutorAccount]:
    return await list_tutors(client)


@router.post("/admin/tutors", status_code=201)
async def add_tutor(body: TutorRequest, admin: Admin, client: Directus) -> TutorAccount:
    return await create_tutor(client, body.email, body.password, body.first_name, body.last_name)


@router.post("/admin/tutors/{user_id}/password", status_code=204)
async def set_tutor_password(
    user_id: UUID, body: PasswordRequest, admin: Admin, client: Directus
) -> Response:
    await reset_tutor_password(client, user_id, body.password)
    return Response(status_code=204)


@router.patch("/admin/tutors/{user_id}")
async def change_tutor_status(
    user_id: UUID, body: TutorStatusRequest, admin: Admin, client: Directus
) -> TutorAccount:
    return await set_tutor_status(client, user_id, body.status)


@router.delete("/admin/tutors/{user_id}", status_code=204)
async def delete_tutor(user_id: UUID, admin: Admin, client: Directus) -> Response:
    """A tutor who still has students is a 409: reassigning them comes first."""
    await remove_tutor(client, user_id)
    return Response(status_code=204)


@router.get("/admin/jobs")
async def read_admin_jobs(
    admin: Admin,
    client: Directus,
    status: JobStatus | None = None,
    limit: int = DEFAULT_JOB_LIMIT,
) -> list[AdminJob]:
    return await list_jobs(client, status, limit)


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
    scanner: Scanner,
    background: BackgroundTasks,
) -> Document:
    """File the material as pending and answer immediately; the row carries the outcome."""
    if body.student_id is not None:
        await visible_student(client, body.student_id)
    document = await create_document(
        client,
        body.source.to_source(),
        title=body.title,
        student=body.student_id,
        session=body.session_id,
    )
    background.add_task(process_document, client, ingesters, document.id, scanner=scanner)
    return document


@router.post("/documents/{document_id}/process", status_code=202)
async def reprocess_document(
    document_id: UUID,
    user: CurrentUser,
    client: Directus,
    ingesters: IngesterSet,
    scanner: Scanner,
    background: BackgroundTasks,
) -> Document:
    """Read the material again — what a tutor's Retry on a failed row does."""
    document = await client.get_item(Collection.DOCUMENTS, Document, document_id)
    background.add_task(process_document, client, ingesters, document.id, scanner=scanner)
    return document


@router.post("/jobs/{kind}", status_code=202)
async def create_job(
    kind: GenerationKind,
    body: JobRequest,
    user: CurrentUser,
    client: Directus,
    generators: GeneratorSet,
    typeset: Typeset,
    background: BackgroundTasks,
) -> GenerationJob:
    """Queue a generation and answer immediately; the job row carries the outcome."""
    _check_input(kind, body)
    if body.student_id is not None:
        await visible_student(client, body.student_id)
    job = await start_job(
        client,
        kind,
        JobInput(
            student=body.student_id,
            documents=tuple(body.document_ids),
            instructions=body.instructions,
            period_start=body.period_start,
            period_end=body.period_end,
            format=body.format,
            pages=body.pages,
        ),
        model=generators.for_kind(kind),
    )
    background.add_task(run_job, client, generators, job.id, typeset=typeset)
    return job


def _check_input(kind: GenerationKind, body: JobRequest) -> None:
    """What each kind is asked for, refused before a job row exists."""
    if body.format is HomeworkFormat.TYPST and kind is not GenerationKind.HOMEWORK:
        raise HTTPException(
            status_code=422,
            detail=detail(FORMAT_UNSUPPORTED, "Only homework can be written in Typst."),
        )
    if body.pages is not None and kind is not GenerationKind.PAPER_EXTRACT:
        raise HTTPException(
            status_code=422,
            detail=detail(PAGES_UNSUPPORTED, "Only extracting a paper can ask about pages."),
        )
    if kind is GenerationKind.PAPER_EXTRACT:
        if not 1 <= len(body.document_ids) <= 2:
            raise HTTPException(
                status_code=422,
                detail=detail(
                    DOCUMENT_REQUIRED,
                    "A paper is read from its own document, or two with its mark scheme second.",
                ),
            )
    elif body.student_id is None:
        raise HTTPException(
            status_code=422,
            detail=detail(STUDENT_REQUIRED, "Say which student this is for."),
        )


@router.post("/typeset/preview")
async def preview_typst(body: TypstRequest, tutor: Tutor, typeset: Typeset) -> TypstPreview:
    """A live preview while a tutor writes. Source that will not compile is a 422."""
    return TypstPreview(pages=await typeset.render_svg(body.source))


@router.post("/typeset/render")
async def render_canonical(body: RenderRequest, tutor: Tutor, typeset: Typeset) -> TypstRender:
    """A canonical structure previewed in the house style. Nothing is read or stored."""
    scheme = body.mark_scheme if isinstance(body, QuestionRenderRequest) else None
    assets = _asset_bytes(body.assets)
    if body.output is RenderOutput.SOURCE:
        source = await typeset.render(
            body.kind, body.document, RenderOutput.SOURCE, mark_scheme=scheme, assets=assets
        )
        return TypstRender(pages=[], source=source)
    pages = await typeset.render(
        body.kind, body.document, RenderOutput.SVG, mark_scheme=scheme, assets=assets
    )
    return TypstRender(pages=pages, source=None)


def _asset_bytes(assets: Mapping[str, str]) -> dict[str, bytes]:
    """The client encodes the bytes again; the caps are its own, and so is the 413."""
    decoded: dict[str, bytes] = {}
    for name, encoded in assets.items():
        try:
            decoded[name] = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=detail(ASSET_UNREADABLE, f"The asset {name!r} is not base64."),
            ) from exc
    return decoded


@router.post("/homework/{homework_id}/compile", status_code=202)
async def compile_homework(
    homework_id: UUID, tutor: Tutor, client: Directus, typeset: Typeset
) -> Homework:
    """Compile the row's `content` again. A failure sets `compile_error` and keeps the old PDF."""
    return await recompile_homework(client, typeset, homework_id)


@router.post("/homework/{homework_id}/transcribe")
async def transcribe_homework_submission(
    homework_id: UUID, user: CurrentUser, client: Directus, scanner: Scanner
) -> Homework:
    """Read the handed-in photo or PDF into `submission_transcription`, and answer with the row."""
    homework = await client.get_item(Collection.HOMEWORK, Homework, homework_id)
    identity = await identify(client, user)
    if identity.role is CallerRole.STUDENT and identity.student_id != homework.student:
        raise HTTPException(
            status_code=403,
            detail=detail(TUTOR_ONLY, "Only this student or their tutor can do this."),
        )
    return await transcribe_submission(client, scanner, homework_id)


@router.post("/papers/{paper_id}/render", status_code=202)
async def render_paper(
    paper_id: UUID,
    tutor: Tutor,
    client: Directus,
    typeset: Typeset,
    generators: GeneratorSet,
) -> Paper:
    """Render the stored structure again — what a tutor runs after reviewing an extraction.

    Maths the compiler refuses is repaired against its diagnostics before it gives up.
    """
    await client.get_item(Collection.PAPERS, Paper, paper_id)
    return await rerender_paper(client, typeset, paper_id, generators.paper)


@router.post("/papers/{paper_id}/worksheet")
async def paper_worksheet_pdf(
    paper_id: UUID, body: WorksheetRequest, tutor: Tutor, client: Directus, typeset: Typeset
) -> WorksheetResult:
    """Some of a paper's questions as a worksheet: the tutor's remix, filed as a PDF."""
    await client.get_item(Collection.PAPERS, Paper, paper_id)
    return await paper_worksheet(
        client,
        typeset,
        paper_id,
        body.question_numbers,
        student_id=body.student_id,
        title=body.title,
        due=body.due,
    )


@router.get("/jobs/{job_id}")
async def read_job(job_id: UUID, user: CurrentUser, client: Directus) -> GenerationJob:
    return await client.get_item(Collection.GENERATION_JOBS, GenerationJob, job_id)
