from __future__ import annotations

import pytest
from sidereal_core.directus import DirectusError, DirectusUnavailableError
from sidereal_core.models import Collection, Student, StudentDraft, StudentStatus
from sidereal_core.testing import FakeDirectus

MISSING_ID = "11111111-1111-4111-8111-111111111111"


async def test_the_fake_serves_crud_filters_and_a_missing_row() -> None:
    fake = FakeDirectus()
    fake.seed(Collection.STUDENTS, {"name": "Paused", "status": "paused"})

    async with fake.client() as client:
        created = await client.create_item(
            Collection.STUDENTS, Student, StudentDraft(name="A. Tutee", subjects=["maths"])
        )
        fetched = await client.get_item(Collection.STUDENTS, Student, created.id)
        updated = await client.update_item(
            Collection.STUDENTS, Student, created.id, {"status": "archived"}
        )
        paused = await client.list_items(
            Collection.STUDENTS, Student, filter={"status": {"_eq": "paused"}}
        )
        capped = await client.list_items(Collection.STUDENTS, Student, limit=1)
        await client.delete_item(Collection.STUDENTS, created.id)
        remaining = await client.list_items(Collection.STUDENTS, Student)

        with pytest.raises(DirectusError) as raised:
            await client.get_item(Collection.STUDENTS, Student, MISSING_ID)

    assert fetched == created
    assert updated.status is StudentStatus.ARCHIVED
    assert [student.name for student in paused] == ["Paused"]
    assert len(capped) == 1
    assert [student.name for student in remaining] == ["Paused"]
    assert raised.value.status == 404


async def test_the_fake_refuses_a_wrong_token_and_can_go_unavailable() -> None:
    fake = FakeDirectus()

    async with fake.client(token="wrong") as client:
        with pytest.raises(DirectusError) as raised:
            await client.me()

    partway = FakeDirectus()
    partway.unavailable_after = 1
    async with partway.client() as client:
        await client.me()
        with pytest.raises(DirectusUnavailableError):
            await client.me()

    down = FakeDirectus()
    down.unavailable = True
    async with down.client() as client:
        with pytest.raises(DirectusUnavailableError):
            await client.me()

    assert raised.value.status == 401
