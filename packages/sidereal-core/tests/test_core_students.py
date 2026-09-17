from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from sidereal_core.directus import DirectusError
from sidereal_core.models import Collection, StudentStatus
from sidereal_core.students import (
    StudentNotVisibleError,
    archive_student,
    delete_student,
    unarchive_student,
    visible_student,
)
from sidereal_core.testing import FakeDirectus


class Scoped(FakeDirectus):
    """A Directus that shows one student and hides every other, the way a tutor's rules do."""

    def __init__(self, mine: str) -> None:
        super().__init__()
        self.mine = mine

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith("/items/students/") and not path.endswith(self.mine):
            return httpx.Response(
                403,
                json={"errors": [{"message": "no", "extensions": {"code": "FORBIDDEN"}}]},
            )
        return super().handle(request)


async def test_a_student_the_caller_can_see_comes_back() -> None:
    fake = FakeDirectus()
    row = fake.seed(Collection.STUDENTS, {"name": "Mine"})

    async with fake.client() as client:
        student = await visible_student(client, UUID(row["id"]))

    assert student.name == "Mine"


async def test_another_tutors_student_does_not_exist_to_this_caller() -> None:
    fake = Scoped(str(uuid4()))

    async with fake.client() as client:
        with pytest.raises(StudentNotVisibleError, match="could not be found"):
            await visible_student(client, uuid4())


async def test_a_directus_failure_that_is_not_a_refusal_stays_one() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"errors": [{"message": "boom"}]})

    fake = FakeDirectus()
    fake.handle = handler  # type: ignore[method-assign]

    async with fake.client() as client:
        with pytest.raises(DirectusError):
            await visible_student(client, uuid4())


async def test_archiving_suspends_the_login_and_unarchiving_brings_it_back() -> None:
    fake = FakeDirectus()
    login = fake.seed(Collection.DIRECTUS_USERS, {"email": "leo@example.test", "status": "active"})
    row = fake.seed(Collection.STUDENTS, {"name": "Leo", "user": login["id"]})

    async with fake.client() as client:
        archived = await archive_student(client, UUID(row["id"]))
        assert archived.status is StudentStatus.ARCHIVED
        assert login["status"] == "suspended"

        active = await unarchive_student(client, UUID(row["id"]))

    assert active.status is StudentStatus.ACTIVE
    assert login["status"] == "active"


async def test_archiving_a_student_with_no_login_touches_no_user() -> None:
    fake = FakeDirectus()
    row = fake.seed(Collection.STUDENTS, {"name": "Leo"})

    async with fake.client() as client:
        await archive_student(client, UUID(row["id"]))

    assert not fake.rows(Collection.DIRECTUS_USERS)


async def test_deleting_a_student_takes_their_login_and_their_row() -> None:
    fake = FakeDirectus()
    login = fake.seed(Collection.DIRECTUS_USERS, {"email": "leo@example.test"})
    row = fake.seed(Collection.STUDENTS, {"name": "Leo", "user": login["id"]})
    fake.register_file("working.jpg", b"jpeg", uploaded_by=login["id"])
    tutor = uuid4()

    async with fake.client() as client:
        deleted = await delete_student(client, UUID(row["id"]), uploads_to=tutor)

    assert deleted.name == "Leo"
    assert not fake.rows(Collection.STUDENTS)
    assert not fake.rows(Collection.DIRECTUS_USERS)
    assert [file["uploaded_by"] for file, _ in fake.files.values()] == [str(tutor)]


async def test_a_student_the_caller_cannot_see_cannot_be_deleted() -> None:
    fake = Scoped(str(uuid4()))

    async with fake.client() as client:
        with pytest.raises(StudentNotVisibleError):
            await delete_student(client, uuid4())


async def test_a_deleted_students_jobs_keep_the_name_they_were_for() -> None:
    """`generation_jobs.student` is SET NULL, so the Jobs history would lose whose work it was."""
    fake = FakeDirectus()
    tutor = fake.seed(Collection.DIRECTUS_USERS, {"email": "priya@example.test"})
    row = fake.seed(Collection.STUDENTS, {"name": "Leo", "tutor": tutor["id"]})
    job = fake.seed(
        Collection.GENERATION_JOBS,
        {
            "kind": "feedback",
            "student": row["id"],
            "status": "succeeded",
            "input": {"student": row["id"], "instructions": "Warm but honest."},
        },
    )

    async with fake.client() as client:
        await delete_student(client, UUID(row["id"]))

    assert job["input"] == {
        "instructions": "Warm but honest.",
        "student_name": "Leo",
        "tutor_email": "priya@example.test",
    }


async def test_a_student_with_no_tutor_still_names_their_jobs() -> None:
    fake = FakeDirectus()
    row = fake.seed(Collection.STUDENTS, {"name": "Leo"})
    job = fake.seed(
        Collection.GENERATION_JOBS,
        {"kind": "plan", "student": row["id"], "status": "failed", "input": {}},
    )

    async with fake.client() as client:
        await delete_student(client, UUID(row["id"]))

    assert job["input"] == {"student_name": "Leo"}
