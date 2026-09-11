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
    JobStatus,
    Student,
    StudentStatus,
)

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
        student_id: UUID, document_ids: Sequence[UUID] = (), instructions: str | None = None
    ) -> GenerationJob:
        """Generate homework for a student. The returned job carries the new row's id."""
        return await tools.generate_homework(resolved, student_id, document_ids, instructions)

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

    return server


def main() -> None:
    create_server().run()
