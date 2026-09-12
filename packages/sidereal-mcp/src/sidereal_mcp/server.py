"""The MCP surface. Every tool here is a one-line delegation to `sidereal_mcp.tools`."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from mcp.server.mcpserver import MCPServer
from sidereal_core.logins import Identity, StudentLogin
from sidereal_core.models import (
    Document,
    DocumentKind,
    GenerationJob,
    Homework,
    HomeworkFormat,
    JobStatus,
    Student,
    StudentStatus,
)
from sidereal_core.tutors import AdminHealth, AdminJob, TutorAccount, TutorStatus

from sidereal_mcp import tools
from sidereal_mcp.services import Services, build_services

SERVER_NAME = "sidereal-tutoring"


def create_server(services: Services | None = None) -> MCPServer:
    resolved = services if services is not None else build_services()
    server = MCPServer(name=SERVER_NAME)

    @server.tool()
    async def list_students(
        status: StudentStatus | None = None, limit: int = tools.DEFAULT_LIMIT
    ) -> list[Student]:
        """List students by name, optionally only those with a given status."""
        return await tools.list_students(resolved, status, limit)

    @server.tool()
    async def get_student(student_id: UUID) -> Student:
        """Read one student by id."""
        return await tools.get_student(resolved, student_id)

    @server.tool()
    async def whoami() -> Identity:
        """Who this server's token belongs to, and the student row it is, if it is one."""
        return await tools.whoami(resolved)

    @server.tool()
    async def create_student_login(student_id: UUID, email: str, password: str) -> StudentLogin:
        """Give a student a login in the Student role. The password is shared out of band."""
        return await tools.create_student_login(resolved, student_id, email, password)

    @server.tool()
    async def reset_student_password(student_id: UUID, password: str) -> StudentLogin:
        """Set a new password on a student's existing login."""
        return await tools.reset_student_password(resolved, student_id, password)

    @server.tool()
    async def remove_student_login(student_id: UUID) -> Student:
        """Delete a student's login. Their work stays; only the way in goes."""
        return await tools.remove_student_login(resolved, student_id)

    @server.tool()
    async def list_documents(
        student_id: UUID | None = None,
        kind: DocumentKind | None = None,
        limit: int = tools.DEFAULT_LIMIT,
    ) -> list[Document]:
        """List ingested documents, most recently created first."""
        return await tools.list_documents(resolved, student_id, kind, limit)

    @server.tool()
    async def ingest_source(
        source: str,
        kind: DocumentKind | None = None,
        student_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> Document:
        """Ingest a transcript path, an http(s) URL or an upload path into a document row."""
        return await tools.ingest_source(resolved, source, kind, student_id, session_id)

    @server.tool()
    async def generate_homework(
        student_id: UUID,
        document_ids: Sequence[UUID] = (),
        instructions: str | None = None,
        format: HomeworkFormat = HomeworkFormat.MARKDOWN,  # noqa: A002 - the domain's field name.
    ) -> GenerationJob:
        """Generate homework for a student. `typst` compiles it to a PDF; the job carries the id."""
        return await tools.generate_homework(
            resolved, student_id, document_ids, instructions, format
        )

    @server.tool()
    async def preview_typst(source: str) -> list[str]:
        """Render Typst source to one SVG per page, to check it before it is saved."""
        return await tools.preview_typst(resolved, source)

    @server.tool()
    async def compile_homework(homework_id: UUID) -> Homework:
        """Compile a Typst homework's content again, replacing its PDF or setting compile_error."""
        return await tools.compile_homework(resolved, homework_id)

    @server.tool()
    async def generate_feedback(
        student_id: UUID, document_ids: Sequence[UUID] = (), instructions: str | None = None
    ) -> GenerationJob:
        """Generate feedback for a student. The returned job carries the new row's id."""
        return await tools.generate_feedback(resolved, student_id, document_ids, instructions)

    @server.tool()
    async def generate_plan(
        student_id: UUID,
        document_ids: Sequence[UUID] = (),
        instructions: str | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> GenerationJob:
        """Generate a study plan for a student over a period."""
        return await tools.generate_plan(
            resolved, student_id, document_ids, instructions, period_start, period_end
        )

    @server.tool()
    async def list_generation_jobs(
        status: JobStatus | None = None, limit: int = tools.DEFAULT_LIMIT
    ) -> list[GenerationJob]:
        """List generation jobs, most recent first."""
        return await tools.list_generation_jobs(resolved, status, limit)

    @server.tool()
    async def update_generation_job(
        job_id: UUID, status: JobStatus, error: str | None = None
    ) -> GenerationJob:
        """Set a job's status, and its error when it failed."""
        return await tools.update_generation_job(resolved, job_id, status, error)

    @server.tool()
    async def list_tutors() -> list[TutorAccount]:
        """The practice's tutors, each with how many students they hold. Admin only."""
        return await tools.list_tutors(resolved)

    @server.tool()
    async def create_tutor(
        email: str, password: str, first_name: str | None = None, last_name: str | None = None
    ) -> TutorAccount:
        """Add a tutor in the Tutor role. The password is shared out of band. Admin only."""
        return await tools.create_tutor(resolved, email, password, first_name, last_name)

    @server.tool()
    async def reset_tutor_password(user_id: UUID, password: str) -> TutorAccount:
        """Set a new password on a tutor's account. Admin only."""
        return await tools.reset_tutor_password(resolved, user_id, password)

    @server.tool()
    async def set_tutor_status(user_id: UUID, status: TutorStatus) -> TutorAccount:
        """Suspend or reactivate a tutor. Their students and their work are untouched."""
        return await tools.set_tutor_status(resolved, user_id, status)

    @server.tool()
    async def remove_tutor(user_id: UUID) -> None:
        """Delete a tutor's account. A tutor who still has students must be reassigned first."""
        await tools.remove_tutor(resolved, user_id)

    @server.tool()
    async def list_jobs(
        status: JobStatus | None = None, limit: int = tools.DEFAULT_LIMIT
    ) -> list[AdminJob]:
        """Generation jobs across every tutor, with the student and their tutor. Admin only."""
        return await tools.list_jobs(resolved, status, limit)

    @server.tool()
    async def admin_health() -> AdminHealth:
        """Directus, the API, typeset, the generation backend and the practice's counts."""
        return await tools.admin_health(resolved)

    return server


def main() -> None:
    create_server().run()
