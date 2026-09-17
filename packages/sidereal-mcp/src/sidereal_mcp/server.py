"""The MCP surface. Every tool here is a one-line delegation to `sidereal_mcp.tools`."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import date
from uuid import UUID

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from sidereal_core.directus import DirectusError
from sidereal_core.logins import Identity, StudentLogin
from sidereal_core.models import (
    Document,
    DocumentKind,
    GenerationJob,
    Homework,
    HomeworkFormat,
    JobStatus,
    Paper,
    Student,
    StudentStatus,
)
from sidereal_core.tutors import AdminHealth, AdminJob, TutorAccount, TutorStatus
from sidereal_generate.papers import WorksheetResult

from sidereal_mcp import tools
from sidereal_mcp.services import (
    ServicePool,
    Services,
    ServicesFor,
    build_pool,
    build_services,
)
from sidereal_mcp.settings import mcp_address, serves_http

SERVER_NAME = "sidereal-tutoring"
UNAUTHORIZED = 401
NO_CREDENTIALS = (
    "This call carried no Directus token. Reconnect with "
    '`--header "Authorization: Bearer <your Directus token>"`.'
)
REJECTED = "Directus rejected that token. A new one comes from your administrator."

Resolve = Callable[[Context], Services]


def create_server(services: Services | None = None) -> MCPServer:
    """The stdio server: one `Services`, on the environment's token, for every caller."""
    resolved = services if services is not None else build_services()
    return _register(lambda _ctx: resolved)


def create_http_server(services_for: ServicesFor) -> MCPServer:
    """The HTTP server: the request's own bearer token is the caller, and the only identity."""
    return _register(lambda ctx: services_for(_bearer(ctx)))


def _register(resolve: Resolve) -> MCPServer:
    server = MCPServer(name=SERVER_NAME)

    @asynccontextmanager
    async def caller(ctx: Context) -> AsyncIterator[Services]:
        """This call's services, and a refused token in words the caller can act on."""
        try:
            yield resolve(ctx)
        except DirectusError as exc:
            if exc.status == UNAUTHORIZED:
                raise ToolError(REJECTED) from exc
            raise

    @server.tool()
    async def list_students(
        ctx: Context, status: StudentStatus | None = None, limit: int = tools.DEFAULT_LIMIT
    ) -> list[Student]:
        """List students by name, optionally only those with a given status."""
        async with caller(ctx) as services:
            return await tools.list_students(services, status, limit)

    @server.tool()
    async def get_student(ctx: Context, student_id: UUID) -> Student:
        """Read one student by id."""
        async with caller(ctx) as services:
            return await tools.get_student(services, student_id)

    @server.tool()
    async def whoami(ctx: Context) -> Identity:
        """Who this call's token belongs to: their role, and the student row it is, if it is one."""
        async with caller(ctx) as services:
            return await tools.whoami(services)

    @server.tool()
    async def create_student_login(
        ctx: Context, student_id: UUID, email: str, password: str
    ) -> StudentLogin:
        """Give a student a login in the Student role. The password is shared out of band."""
        async with caller(ctx) as services:
            return await tools.create_student_login(services, student_id, email, password)

    @server.tool()
    async def reset_student_password(ctx: Context, student_id: UUID, password: str) -> StudentLogin:
        """Set a new password on a student's existing login."""
        async with caller(ctx) as services:
            return await tools.reset_student_password(services, student_id, password)

    @server.tool()
    async def remove_student_login(ctx: Context, student_id: UUID) -> Student:
        """Delete a student's login. Their work stays; only the way in goes."""
        async with caller(ctx) as services:
            return await tools.remove_student_login(services, student_id)

    @server.tool()
    async def list_documents(
        ctx: Context,
        student_id: UUID | None = None,
        kind: DocumentKind | None = None,
        limit: int = tools.DEFAULT_LIMIT,
    ) -> list[Document]:
        """List ingested documents, most recently created first."""
        async with caller(ctx) as services:
            return await tools.list_documents(services, student_id, kind, limit)

    @server.tool()
    async def ingest_source(
        ctx: Context,
        source: str,
        kind: DocumentKind | None = None,
        student_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> Document:
        """Ingest a transcript path, an http(s) URL or an upload path into a document row."""
        async with caller(ctx) as services:
            return await tools.ingest_source(services, source, kind, student_id, session_id)

    @server.tool()
    async def scan_pages(
        ctx: Context,
        file_ids: Sequence[UUID],
        paper_id: UUID | None = None,
        student_id: UUID | None = None,
        session_id: UUID | None = None,
        title: str | None = None,
    ) -> Document:
        """Transcribe uploaded handwritten pages into a document row, in the order given.

        `paper_id` is the paper the pages answer, and makes the row carry the working
        question by question.
        """
        async with caller(ctx) as services:
            return await tools.scan_pages(
                services, file_ids, paper_id, student_id, session_id, title
            )

    @server.tool()
    async def transcribe_submission(ctx: Context, homework_id: UUID) -> Homework:
        """Read a student's handed-in photo or PDF into the homework's submission_transcription."""
        async with caller(ctx) as services:
            return await tools.transcribe_submission(services, homework_id)

    @server.tool()
    async def generate_homework(
        ctx: Context,
        student_id: UUID,
        document_ids: Sequence[UUID] = (),
        instructions: str | None = None,
        format: HomeworkFormat = HomeworkFormat.MARKDOWN,  # noqa: A002 - the domain's field name.
    ) -> GenerationJob:
        """Generate homework for a student. `typst` compiles it to a PDF; the job carries the id."""
        async with caller(ctx) as services:
            return await tools.generate_homework(
                services, student_id, document_ids, instructions, format
            )

    @server.tool()
    async def extract_paper(
        ctx: Context,
        document_id: UUID,
        mark_scheme_id: UUID | None = None,
        pages: bool | None = None,
    ) -> GenerationJob:
        """Read a ready document into a paper: its structure, its PDFs and its question rows.

        `mark_scheme_id` is the paper's mark scheme, when it was filed as its own document.
        `pages` sends the source PDF's pages as images too: `true` always, `false` never, and
        the default `null` decides from the PDF itself.
        """
        async with caller(ctx) as services:
            return await tools.extract_paper(services, document_id, mark_scheme_id, pages)

    @server.tool()
    async def render_paper(ctx: Context, paper_id: UUID) -> Paper:
        """Render a paper's stored structure again, replacing both of its PDFs."""
        async with caller(ctx) as services:
            return await tools.render_paper(services, paper_id)

    @server.tool()
    async def paper_worksheet(
        ctx: Context,
        paper_id: UUID,
        question_numbers: Sequence[str],
        student_id: UUID | None = None,
        title: str | None = None,
        due: date | None = None,
    ) -> WorksheetResult:
        """Some of a paper's questions, in the order given, as one worksheet PDF."""
        async with caller(ctx) as services:
            return await tools.paper_worksheet_pdf(
                services, paper_id, question_numbers, student_id, title, due
            )

    @server.tool()
    async def preview_typst(ctx: Context, source: str) -> list[str]:
        """Render Typst source to one SVG per page, to check it before it is saved."""
        async with caller(ctx) as services:
            return await tools.preview_typst(services, source)

    @server.tool()
    async def compile_homework(ctx: Context, homework_id: UUID) -> Homework:
        """Compile a Typst homework's content again, replacing its PDF or setting compile_error."""
        async with caller(ctx) as services:
            return await tools.compile_homework(services, homework_id)

    @server.tool()
    async def generate_feedback(
        ctx: Context,
        student_id: UUID,
        document_ids: Sequence[UUID] = (),
        instructions: str | None = None,
    ) -> GenerationJob:
        """Generate feedback for a student. The returned job carries the new row's id."""
        async with caller(ctx) as services:
            return await tools.generate_feedback(services, student_id, document_ids, instructions)

    @server.tool()
    async def generate_plan(
        ctx: Context,
        student_id: UUID,
        document_ids: Sequence[UUID] = (),
        instructions: str | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> GenerationJob:
        """Generate a study plan for a student over a period."""
        async with caller(ctx) as services:
            return await tools.generate_plan(
                services, student_id, document_ids, instructions, period_start, period_end
            )

    @server.tool()
    async def list_generation_jobs(
        ctx: Context, status: JobStatus | None = None, limit: int = tools.DEFAULT_LIMIT
    ) -> list[GenerationJob]:
        """List generation jobs, most recent first."""
        async with caller(ctx) as services:
            return await tools.list_generation_jobs(services, status, limit)

    @server.tool()
    async def update_generation_job(
        ctx: Context, job_id: UUID, status: JobStatus, error: str | None = None
    ) -> GenerationJob:
        """Set a job's status, and its error when it failed."""
        async with caller(ctx) as services:
            return await tools.update_generation_job(services, job_id, status, error)

    @server.tool()
    async def list_tutors(ctx: Context) -> list[TutorAccount]:
        """The practice's tutors, each with how many students they hold. Admin only."""
        async with caller(ctx) as services:
            return await tools.list_tutors(services)

    @server.tool()
    async def create_tutor(
        ctx: Context,
        email: str,
        password: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> TutorAccount:
        """Add a tutor in the Tutor role. The password is shared out of band. Admin only."""
        async with caller(ctx) as services:
            return await tools.create_tutor(services, email, password, first_name, last_name)

    @server.tool()
    async def reset_tutor_password(ctx: Context, user_id: UUID, password: str) -> TutorAccount:
        """Set a new password on a tutor's account. Admin only."""
        async with caller(ctx) as services:
            return await tools.reset_tutor_password(services, user_id, password)

    @server.tool()
    async def set_tutor_status(ctx: Context, user_id: UUID, status: TutorStatus) -> TutorAccount:
        """Suspend or reactivate a tutor. Their students and their work are untouched."""
        async with caller(ctx) as services:
            return await tools.set_tutor_status(services, user_id, status)

    @server.tool()
    async def remove_tutor(ctx: Context, user_id: UUID) -> None:
        """Delete a tutor's account. A tutor who still has students must be reassigned first."""
        async with caller(ctx) as services:
            await tools.remove_tutor(services, user_id)

    @server.tool()
    async def list_jobs(
        ctx: Context, status: JobStatus | None = None, limit: int = tools.DEFAULT_LIMIT
    ) -> list[AdminJob]:
        """Generation jobs across every tutor, with the student and their tutor. Admin only."""
        async with caller(ctx) as services:
            return await tools.list_jobs(services, status, limit)

    @server.tool()
    async def admin_health(ctx: Context) -> AdminHealth:
        """Directus, the API, typeset, the generation backend and the practice's counts."""
        async with caller(ctx) as services:
            return await tools.admin_health(services)

    return server


def _bearer(ctx: Context) -> str:
    """The caller's token, as they sent it. Client-supplied: Directus, not this server, judges it."""
    scheme, _, token = (ctx.headers or {}).get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ToolError(NO_CREDENTIALS)
    return token.strip()


async def _serve_http(pool: ServicePool, host: str, port: int) -> None:
    try:
        await create_http_server(pool.for_token).run_streamable_http_async(host=host, port=port)
    finally:
        await pool.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="sidereal-mcp", description=__doc__)
    parser.add_argument(
        "--http",
        action="store_true",
        help="serve Streamable HTTP on SIDEREAL_MCP_ADDR instead of stdio",
    )
    if parser.parse_args().http or serves_http():
        address = mcp_address()
        asyncio.run(_serve_http(build_pool(), address.host, address.port))
    else:
        create_server().run()
