from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp_doubles import build_services
from mcp_types import CallToolResult
from sidereal_core.testing import DEFAULT_TOKEN, FakeDirectus
from sidereal_mcp.server import NO_CREDENTIALS, REJECTED, create_http_server
from sidereal_mcp.services import Services

ENDPOINT = "http://127.0.0.1:50053/mcp"


@asynccontextmanager
async def connect(
    fake: FakeDirectus, token: str | None, seen: list[str] | None = None
) -> AsyncIterator[Client]:
    """The HTTP app over ASGI: no socket, and the request's bearer is the only identity."""

    def services_for(bearer: str) -> Services:
        if seen is not None:
            seen.append(bearer)
        return build_services(fake, token=bearer)

    app = create_http_server(services_for).streamable_http_app()
    headers = {} if token is None else {"Authorization": f"Bearer {token}"}
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app), headers=headers, timeout=10.0
        ) as http,
        Client(streamable_http_client(ENDPOINT, http_client=http)) as client,
    ):
        yield client


async def test_the_bearer_token_is_who_the_caller_is() -> None:
    fake = FakeDirectus()
    seen: list[str] = []

    async with connect(fake, DEFAULT_TOKEN, seen) as client:
        result = await client.call_tool("whoami", {})

    assert isinstance(result, CallToolResult)
    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["role"] == "tutor"
    assert result.structured_content["email"] == fake.user["email"]
    assert seen == [DEFAULT_TOKEN]


async def test_an_administrator_sees_their_own_role() -> None:
    fake = FakeDirectus(admin=True)

    async with connect(fake, DEFAULT_TOKEN) as client:
        result = await client.call_tool("whoami", {})

    assert isinstance(result, CallToolResult)
    assert result.structured_content is not None
    assert result.structured_content["role"] == "admin"


async def test_a_call_with_no_token_is_told_how_to_send_one() -> None:
    async with connect(FakeDirectus(), None) as client:
        result = await client.call_tool("whoami", {})

    assert isinstance(result, CallToolResult)
    assert result.is_error
    assert NO_CREDENTIALS in _text(result)


async def test_a_token_directus_refuses_says_so() -> None:
    async with connect(FakeDirectus(), "stale-credential") as client:
        result = await client.call_tool("whoami", {})

    assert isinstance(result, CallToolResult)
    assert result.is_error
    assert REJECTED in _text(result)


def _text(result: CallToolResult) -> str:
    return "\n".join(block.text for block in result.content if block.type == "text")
