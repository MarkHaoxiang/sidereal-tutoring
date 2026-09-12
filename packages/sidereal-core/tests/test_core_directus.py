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
ROLE_ROW = {"id": "22222222-2222-4222-8222-222222222222", "name": "Student"}
USER_ROW = {"id": "33333333-3333-4333-8333-333333333333", "email": "tutee@example.test"}

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


async def test_me_asks_directus_whether_the_caller_is_an_admin() -> None:
    seen: list[str] = []
    me = {"id": str(STUDENT_ID), "email": "tutor@example.test", "role": ROLE_ROW["id"]}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/policies/me/globals":
            return httpx.Response(200, json={"data": {"app_access": True, "admin_access": True}})
        return httpx.Response(200, json={"data": me})

    async with client_for(handler) as client:
        user = await client.me()

    assert sorted(seen) == ["/policies/me/globals", "/users/me"]
    assert user.email == "tutor@example.test"
    assert user.role == UUID(ROLE_ROW["id"])
    assert user.admin_access


async def test_a_directus_that_refuses_the_globals_leaves_the_caller_a_non_admin() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/policies/me/globals":
            return httpx.Response(403, json={"errors": [{"message": "No."}]})
        return httpx.Response(200, json={"data": {"id": str(STUDENT_ID)}})

    async with client_for(handler) as client:
        user = await client.me()

    assert not user.admin_access


async def test_a_related_row_is_created_through_its_owner_and_answers_with_its_id() -> None:
    seen: list[httpx.Request] = []
    new_user = "44444444-4444-4444-8444-444444444444"

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": {"id": str(STUDENT_ID), "user": {"id": new_user}}})

    async with client_for(handler) as client:
        created = await client.create_related(
            Collection.STUDENTS, STUDENT_ID, "user", {"email": "tutee@example.test"}
        )

    assert seen[0].method == "PATCH"
    assert seen[0].url.params.get("fields") == "user.id"
    assert json.loads(seen[0].content) == {"user": {"email": "tutee@example.test"}}
    assert created == UUID(new_user)


async def test_counts_come_back_as_numbers_and_group_by_a_field() -> None:
    seen: list[httpx.Request] = []
    rows = [
        {"tutor": ROLE_ROW["id"], "count": {"id": "2"}},
        {"tutor": None, "count": {"id": "1"}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.params.get("groupBy"):
            return httpx.Response(200, json={"data": rows})
        return httpx.Response(200, json={"data": [{"count": {"id": None}}]})

    async with client_for(handler) as client:
        empty = await client.count_items(Collection.STUDENTS)
        grouped = await client.count_items_by(Collection.STUDENTS, "tutor")

    assert seen[0].url.params.get("aggregate[count]") == "id"
    assert empty == 0
    assert grouped == {ROLE_ROW["id"]: 2}


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


async def test_roles_and_users_are_system_routes_not_items() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/roles":
            return httpx.Response(200, json={"data": [ROLE_ROW]})
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"data": USER_ROW})

    async with client_for(handler) as client:
        role = await client.find_role("Student")
        roles = await client.list_roles()
        created = await client.create_user({"email": "tutee@example.test"})
        updated = await client.update_user(created.id, {"first_name": "A."})
        await client.delete_user(created.id)

    assert role is not None
    assert role.name == "Student"
    assert [each.name for each in roles] == ["Student"]
    assert created.email == "tutee@example.test"
    assert updated.id == created.id
    assert [(request.method, request.url.path) for request in seen] == [
        ("GET", "/roles"),
        ("GET", "/roles"),
        ("POST", "/users"),
        ("PATCH", f"/users/{created.id}"),
        ("DELETE", f"/users/{created.id}"),
    ]
    assert json.loads(seen[0].url.params["filter"]) == {"name": {"_eq": "Student"}}


async def test_find_role_is_none_when_the_name_is_unknown() -> None:
    async with client_for(lambda _: httpx.Response(200, json={"data": []})) as client:
        assert await client.find_role("Student") is None
