from __future__ import annotations

from uuid import UUID

import pytest
from sidereal_core.directus import DirectusError, DirectusUnavailableError
from sidereal_core.models import Collection, Student, StudentDraft, StudentStatus
from sidereal_core.testing import FakeDirectus


async def test_crud_round_trip() -> None:
    fake = FakeDirectus()
    async with fake.client() as client:
        created = await client.create_item(
            Collection.STUDENTS, Student, StudentDraft(name="A. Tutee", subjects=["maths"])
        )
        fetched = await client.get_item(Collection.STUDENTS, Student, created.id)
        updated = await client.update_item(
            Collection.STUDENTS, Student, created.id, {"status": "archived"}
        )
        await client.delete_item(Collection.STUDENTS, created.id)

        assert fetched == created
        assert updated.status is StudentStatus.ARCHIVED
        assert await client.list_items(Collection.STUDENTS, Student) == []


async def test_list_applies_eq_filters_and_limit() -> None:
    fake = FakeDirectus()
    fake.seed(Collection.STUDENTS, {"name": "Active", "status": "active"})
    fake.seed(Collection.STUDENTS, {"name": "Paused", "status": "paused"})

    async with fake.client() as client:
        active = await client.list_items(
            Collection.STUDENTS, Student, filter={"status": {"_eq": "active"}}
        )
        capped = await client.list_items(Collection.STUDENTS, Student, limit=1)

    assert [student.name for student in active] == ["Active"]
    assert len(capped) == 1


async def test_the_wrong_token_is_rejected() -> None:
    fake = FakeDirectus()
    async with fake.client(token="wrong") as client:
        with pytest.raises(DirectusError) as raised:
            await client.me()

    assert raised.value.status == 401


async def test_an_unavailable_server_raises_before_any_response() -> None:
    fake = FakeDirectus()
    fake.unavailable = True

    async with fake.client() as client:
        with pytest.raises(DirectusUnavailableError):
            await client.me()


async def test_a_missing_row_is_a_404() -> None:
    fake = FakeDirectus()
    async with fake.client() as client:
        with pytest.raises(DirectusError) as raised:
            await client.get_item(
                Collection.STUDENTS, Student, "11111111-1111-4111-8111-111111111111"
            )

    assert raised.value.status == 404


async def test_the_server_can_fail_partway_through() -> None:
    fake = FakeDirectus()
    fake.unavailable_after = 1

    async with fake.client() as client:
        await client.me()
        with pytest.raises(DirectusUnavailableError):
            await client.me()


async def test_roles_and_users_answer_off_items() -> None:
    fake = FakeDirectus()
    role = fake.seed(Collection.DIRECTUS_ROLES, {"name": "Student"})

    async with fake.client() as client:
        found = await client.find_role("Student")
        missing = await client.find_role("Nobody")
        created = await client.create_user({"email": "tutee@example.test", "role": role["id"]})
        updated = await client.update_user(created.id, {"first_name": "A."})
        await client.delete_user(created.id)

    assert found is not None
    assert found.id == UUID(role["id"])
    assert missing is None
    assert updated.first_name == "A."
    assert fake.rows(Collection.DIRECTUS_USERS) == []
