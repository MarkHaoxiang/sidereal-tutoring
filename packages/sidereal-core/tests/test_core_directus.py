from __future__ import annotations

import json
from collections.abc import Callable
from uuid import UUID

import httpx
import pytest
from sidereal_core.directus import (
    DirectusClient,
    DirectusError,
    DirectusUnavailableError,
)
from sidereal_core.models import Collection, Student, StudentDraft, StudentStatus

BASE_URL = "http://directus.test"
STUDENT_ID = UUID("11111111-1111-4111-8111-111111111111")
STUDENT_ROW = {"id": str(STUDENT_ID), "name": "A. Tutee", "status": "active"}

Handler = Callable[[httpx.Request], httpx.Response]


def client_for(handler: Handler) -> DirectusClient:
    return DirectusClient(BASE_URL, "tok", transport=httpx.MockTransport(handler))


async def test_list_items_sends_filter_and_limit_and_validates_rows() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": [STUDENT_ROW]})

    async with client_for(handler) as client:
        students = await client.list_items(
            Collection.STUDENTS,
            Student,
            filter={"status": {"_eq": "active"}},
            limit=10,
            sort=["name"],
        )

    assert [student.name for student in students] == ["A. Tutee"]
    assert students[0].status is StudentStatus.ACTIVE
    request = seen[0]
    assert request.url.path == "/items/students"
    assert json.loads(request.url.params["filter"]) == {"status": {"_eq": "active"}}
    assert request.url.params["limit"] == "10"
    assert request.url.params["sort"] == "name"
    assert request.headers["authorization"] == "Bearer tok"


async def test_get_item_unwraps_the_data_envelope() -> None:
    async with client_for(lambda _: httpx.Response(200, json={"data": STUDENT_ROW})) as client:
        student = await client.get_item(Collection.STUDENTS, Student, STUDENT_ID)

    assert student.id == STUDENT_ID


async def test_create_item_posts_the_draft_payload() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": STUDENT_ROW})

    async with client_for(handler) as client:
        await client.create_item(
            Collection.STUDENTS, Student, StudentDraft(name="A. Tutee", subjects=["maths"])
        )

    assert seen[0].method == "POST"
    assert json.loads(seen[0].content) == {
        "name": "A. Tutee",
        "subjects": ["maths"],
        "status": "active",
    }


async def test_update_item_patches_a_mapping() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": {**STUDENT_ROW, "status": "archived"}})

    async with client_for(handler) as client:
        student = await client.update_item(
            Collection.STUDENTS, Student, STUDENT_ID, {"status": "archived"}
        )

    assert seen[0].method == "PATCH"
    assert student.status is StudentStatus.ARCHIVED


async def test_delete_item_accepts_an_empty_response() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    async with client_for(handler) as client:
        await client.delete_item(Collection.STUDENTS, STUDENT_ID)

    assert seen[0].method == "DELETE"
    assert seen[0].url.path == f"/items/students/{STUDENT_ID}"


async def test_me_returns_the_token_holder() -> None:
    body = {"data": {"id": str(STUDENT_ID), "email": "tutor@example.test", "status": "active"}}

    async with client_for(lambda _: httpx.Response(200, json=body)) as client:
        user = await client.me()

    assert user.email == "tutor@example.test"


async def test_error_response_carries_status_and_directus_errors() -> None:
    body = {
        "errors": [
            {"message": "Invalid user credentials.", "extensions": {"code": "INVALID_CREDENTIALS"}}
        ]
    }

    async with client_for(lambda _: httpx.Response(401, json=body)) as client:
        with pytest.raises(DirectusError) as raised:
            await client.me()

    assert raised.value.status == 401
    assert raised.value.codes == ("INVALID_CREDENTIALS",)
    assert "Invalid user credentials." in str(raised.value)


async def test_error_response_without_a_json_body_still_raises() -> None:
    async with client_for(lambda _: httpx.Response(502, text="bad gateway")) as client:
        with pytest.raises(DirectusError) as raised:
            await client.me()

    assert raised.value.status == 502
    assert raised.value.errors == ()


async def test_missing_envelope_is_an_error_not_a_validation_failure() -> None:
    async with client_for(lambda _: httpx.Response(200, json=STUDENT_ROW)) as client:
        with pytest.raises(DirectusError, match="no data envelope"):
            await client.get_item(Collection.STUDENTS, Student, STUDENT_ID)


async def test_transport_failure_is_unavailable_not_an_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    async with client_for(handler) as client:
        with pytest.raises(DirectusUnavailableError):
            await client.me()


async def test_an_injected_http_client_is_not_closed_by_the_wrapper() -> None:
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(204)))
    client = DirectusClient(BASE_URL, "tok", http_client=http_client)

    await client.aclose()

    assert not http_client.is_closed
    await http_client.aclose()
