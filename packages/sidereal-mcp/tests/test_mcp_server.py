from __future__ import annotations

from mcp_doubles import FIXTURES, build_services, seed_student
from mcp_types import CallToolResult
from sidereal_core.models import Collection
from sidereal_core.testing import FakeDirectus
from sidereal_mcp import tools
from sidereal_mcp.server import SERVER_NAME, create_server

EXPECTED = {
    "list_students",
    "get_student",
    "list_documents",
    "ingest_source",
    "generate_homework",
    "generate_feedback",
    "generate_plan",
    "list_generation_jobs",
    "update_generation_job",
}


async def test_the_server_registers_every_tool() -> None:
    server = create_server(build_services(FakeDirectus()))

    listed = await server.list_tools()

    assert server.name == SERVER_NAME
    assert {tool.name for tool in listed} == EXPECTED
    assert all(tool.description for tool in listed)


async def test_every_tool_reaches_its_delegate() -> None:
    fake = FakeDirectus()
    student_id = seed_student(fake)
    services = build_services(fake)
    document = await tools.ingest_source(services, str(FIXTURES / "lesson-4.vtt"))
    server = create_server(services)
    calls: list[tuple[str, dict[str, object]]] = [
        ("list_students", {}),
        ("get_student", {"student_id": str(student_id)}),
        ("list_documents", {}),
        ("ingest_source", {"source": "https://example.test/indices"}),
        ("generate_homework", {"student_id": str(student_id), "document_ids": [str(document.id)]}),
        ("generate_feedback", {"student_id": str(student_id)}),
        ("generate_plan", {"student_id": str(student_id)}),
        ("list_generation_jobs", {}),
    ]

    for name, arguments in calls:
        result = await server.call_tool(name, arguments)
        assert isinstance(result, CallToolResult)
        assert not result.is_error

    job = fake.rows(Collection.GENERATION_JOBS)[0]
    updated = await server.call_tool(
        "update_generation_job", {"job_id": job["id"], "status": "failed", "error": "redo"}
    )
    assert isinstance(updated, CallToolResult)
    assert not updated.is_error
