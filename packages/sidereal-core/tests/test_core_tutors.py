from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sidereal_core.directus import DirectusClient
from sidereal_core.logins import InvalidEmailError, WeakPasswordError
from sidereal_core.models import Collection, GenerationKind, JobStatus
from sidereal_core.testing import FAKE_DIRECTUS_VERSION, FakeDirectus, FakeTypeset
from sidereal_core.tutors import (
    TUTOR_ROLE,
    TutorHasStudentsError,
    TutorNotFoundError,
    TutorRefusedError,
    TutorRoleMissingError,
    TutorStatus,
    admin_health,
    create_tutor,
    list_jobs,
    list_tutors,
    remove_tutor,
    reset_tutor_password,
    set_tutor_status,
)

PASSWORD = "correct-horse"
API_VERSION = "9.9.9"


@pytest.fixture
def fake() -> FakeDirectus:
    fake = FakeDirectus(admin=True)
    fake.seed(Collection.DIRECTUS_ROLES, {"name": TUTOR_ROLE})
    return fake


def role_id(fake: FakeDirectus) -> str:
    return str(fake.rows(Collection.DIRECTUS_ROLES)[0]["id"])


def seed_tutor(fake: FakeDirectus, email: str, **extra: Any) -> UUID:
    row = fake.seed(
        Collection.DIRECTUS_USERS,
        {"email": email, "role": role_id(fake), "status": "active", **extra},
    )
    return UUID(str(row["id"]))


async def test_a_tutor_is_created_in_the_tutor_role() -> None:
    fake = FakeDirectus(admin=True)
    fake.seed(Collection.DIRECTUS_ROLES, {"name": TUTOR_ROLE})

    async with fake.client() as client:
        account = await create_tutor(client, "new@sidereal.example.com", PASSWORD, "New", "Tutor")

    stored = fake.items[Collection.DIRECTUS_USERS][str(account.user_id)]
    assert stored["role"] == role_id(fake)
    assert stored["status"] == TutorStatus.ACTIVE.value
    assert account.students == 0
    assert account.first_name == "New"


async def test_a_practice_with_no_tutor_role_cannot_manage_tutors() -> None:
    fake = FakeDirectus(admin=True)

    async with fake.client() as client:
        with pytest.raises(TutorRoleMissingError):
            await create_tutor(client, "new@sidereal.example.com", PASSWORD)


async def test_a_bad_email_or_a_weak_password_never_reaches_directus(fake: FakeDirectus) -> None:
    async with fake.client() as client:
        with pytest.raises(InvalidEmailError):
            await create_tutor(client, "not-an-email", PASSWORD)
        with pytest.raises(WeakPasswordError):
            await create_tutor(client, "new@sidereal.example.com", "short")

    assert fake.rows(Collection.DIRECTUS_USERS) == []


async def test_a_directus_refusal_becomes_a_sentence_an_admin_can_read() -> None:
    role = {"id": str(uuid4()), "name": TUTOR_ROLE}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(400, json={"errors": [{"message": "Value has to be unique."}]})
        return httpx.Response(200, json={"data": [role]})

    async with DirectusClient("http://directus.test", transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(TutorRefusedError) as raised:
            await create_tutor(c, "taken@sidereal.example.com", PASSWORD)

    assert raised.value.status == 400
    assert "unique" not in str(raised.value)


async def test_listing_counts_each_tutors_students_in_one_query(fake: FakeDirectus) -> None:
    busy = seed_tutor(fake, "busy@sidereal.example.com")
    idle = seed_tutor(fake, "idle@sidereal.example.com")
    fake.seed(Collection.STUDENTS, {"name": "One", "tutor": str(busy)})
    fake.seed(Collection.STUDENTS, {"name": "Two", "tutor": str(busy)})
    fake.seed(Collection.STUDENTS, {"name": "Unassigned"})

    async with fake.client() as client:
        accounts = await list_tutors(client)

    assert {account.user_id: account.students for account in accounts} == {busy: 2, idle: 0}


async def test_only_a_tutor_role_user_is_a_tutor(fake: FakeDirectus) -> None:
    other = fake.seed(Collection.DIRECTUS_USERS, {"email": "student@sidereal.example.com"})

    async with fake.client() as client:
        with pytest.raises(TutorNotFoundError):
            await reset_tutor_password(client, UUID(str(other["id"])), PASSWORD)
        with pytest.raises(TutorNotFoundError):
            await remove_tutor(client, uuid4())


async def test_a_password_reset_writes_the_new_password(fake: FakeDirectus) -> None:
    tutor = seed_tutor(fake, "tutor@sidereal.example.com")

    async with fake.client() as client:
        account = await reset_tutor_password(client, tutor, "a-longer-secret")

    assert account.user_id == tutor
    assert fake.items[Collection.DIRECTUS_USERS][str(tutor)]["password"] == "a-longer-secret"


async def test_suspending_a_tutor_leaves_their_students_alone(fake: FakeDirectus) -> None:
    tutor = seed_tutor(fake, "tutor@sidereal.example.com")
    fake.seed(Collection.STUDENTS, {"name": "Theirs", "tutor": str(tutor)})

    async with fake.client() as client:
        account = await set_tutor_status(client, tutor, TutorStatus.SUSPENDED)

    assert account.status == TutorStatus.SUSPENDED.value
    assert account.students == 1
    assert fake.rows(Collection.STUDENTS)[0]["tutor"] == str(tutor)


async def test_a_tutor_with_students_cannot_be_removed(fake: FakeDirectus) -> None:
    tutor = seed_tutor(fake, "tutor@sidereal.example.com")
    student = fake.seed(Collection.STUDENTS, {"name": "Theirs", "tutor": str(tutor)})

    async with fake.client() as client:
        with pytest.raises(TutorHasStudentsError, match="Reassign"):
            await remove_tutor(client, tutor)

        student["tutor"] = None
        await remove_tutor(client, tutor)

    assert fake.rows(Collection.DIRECTUS_USERS) == []


async def test_jobs_carry_the_student_and_that_students_tutor(fake: FakeDirectus) -> None:
    tutor = seed_tutor(fake, "tutor@sidereal.example.com")
    theirs = fake.seed(Collection.STUDENTS, {"name": "Theirs", "tutor": str(tutor)})
    nobodys = fake.seed(Collection.STUDENTS, {"name": "Nobody's"})
    for student in (theirs, nobodys, theirs):
        fake.seed(
            Collection.GENERATION_JOBS,
            {
                "kind": GenerationKind.HOMEWORK.value,
                "status": JobStatus.SUCCEEDED.value,
                "student": str(student["id"]),
            },
        )

    async with fake.client() as client:
        before = len(fake.requests)
        rows = await list_jobs(client)

    assert len(rows) == 3
    assert {(row.student_name, row.tutor_email) for row in rows} == {
        ("Theirs", "tutor@sidereal.example.com"),
        ("Nobody's", None),
    }
    # The jobs, then the students, then the tutors: never one lookup per job.
    assert len(fake.requests) - before == 3


async def test_jobs_can_be_filtered_by_status(fake: FakeDirectus) -> None:
    for status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
        fake.seed(
            Collection.GENERATION_JOBS,
            {"kind": GenerationKind.PLAN.value, "status": status.value},
        )

    async with fake.client() as client:
        rows = await list_jobs(client, JobStatus.FAILED)

    assert [row.job.status for row in rows] == [JobStatus.FAILED]


async def test_health_reports_every_service_and_the_practices_counts(fake: FakeDirectus) -> None:
    seed_tutor(fake, "tutor@sidereal.example.com")
    fake.seed(Collection.STUDENTS, {"name": "One"})
    fake.seed(Collection.DOCUMENTS, {"title": "Notes", "kind": "upload"})
    fake.seed(
        Collection.GENERATION_JOBS,
        {"kind": GenerationKind.PLAN.value, "status": JobStatus.RUNNING.value},
    )

    async with fake.client() as client, FakeTypeset().client() as typeset:
        health = await admin_health(
            client, typeset, api_version=API_VERSION, backend="fake", model="fake-model"
        )

    assert health.directus.ok
    assert health.directus.version == FAKE_DIRECTUS_VERSION
    assert health.directus.license is not None
    assert health.directus.license.status == "active"
    assert health.api.version == API_VERSION
    assert health.typeset.ok
    assert health.generation.backend == "fake"
    assert health.counts.model_dump() == {
        "tutors": 1,
        "students": 1,
        "documents": 1,
        "jobs_running": 1,
    }


async def test_an_unreadable_licence_is_not_an_unhealthy_directus(fake: FakeDirectus) -> None:
    fake.licence = None

    async with fake.client() as client, FakeTypeset().client() as typeset:
        health = await admin_health(
            client, typeset, api_version=API_VERSION, backend="fake", model="fake-model"
        )

    assert health.directus.ok
    assert health.directus.license is None


async def test_a_service_that_is_down_is_data_not_an_error(fake: FakeDirectus) -> None:
    fake.unavailable = True
    typeset_service = FakeTypeset()
    typeset_service.unavailable = True

    async with fake.client() as client, typeset_service.client() as typeset:
        health = await admin_health(
            client, typeset, api_version=API_VERSION, backend="fake", model="fake-model"
        )

    assert not health.directus.ok
    assert not health.typeset.ok
    assert health.api.ok
    assert health.counts.students == 0
