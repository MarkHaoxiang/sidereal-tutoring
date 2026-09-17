from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from sidereal_core.directus import DirectusClient, DirectusUnavailableError
from sidereal_core.logins import (
    AccountStatus,
    CallerRole,
    InvalidEmailError,
    LoginExistsError,
    LoginMissingError,
    LoginRefusedError,
    LoginUnlinkedError,
    StudentRoleMissingError,
    WeakPasswordError,
    account_status,
    create_login,
    remove_login,
    reset_password,
    whoami,
)
from sidereal_core.models import Collection, Student
from sidereal_core.testing import DEFAULT_USER_ID, FakeDirectus

EMAIL = "tutee@sidereal.example.com"
PASSWORD = "correct-horse"


def seeded() -> tuple[FakeDirectus, UUID]:
    fake = FakeDirectus()
    fake.seed(Collection.DIRECTUS_ROLES, {"name": "Student"})
    row = fake.seed(Collection.STUDENTS, {"name": "A. Tutee", "status": "active"})
    return fake, UUID(row["id"])


def user_rows(fake: FakeDirectus) -> list[dict[str, Any]]:
    return fake.rows(Collection.DIRECTUS_USERS)


async def student_row(client: DirectusClient, student_id: UUID) -> Student:
    return await client.get_item(Collection.STUDENTS, Student, student_id)


async def test_create_login_makes_a_student_role_user_and_links_it_in_one_write() -> None:
    fake, student_id = seeded()
    role = fake.rows(Collection.DIRECTUS_ROLES)[0]

    async with fake.client() as client:
        login = await create_login(client, student_id, EMAIL, PASSWORD)

        assert login.email == EMAIL
        assert (await student_row(client, student_id)).user == login.user_id
    assert [request.url.path for request in fake.requests].count("/users") == 0

    created = user_rows(fake)[0]
    assert created["role"] == role["id"]
    assert created["first_name"] == "A. Tutee"
    assert created["password"] == PASSWORD


async def test_a_second_login_is_refused() -> None:
    fake, student_id = seeded()

    async with fake.client() as client:
        await create_login(client, student_id, EMAIL, PASSWORD)

        with pytest.raises(LoginExistsError):
            await create_login(client, student_id, "other@sidereal.example.com", PASSWORD)

    assert len(user_rows(fake)) == 1


async def test_a_short_password_is_refused_before_anything_is_written() -> None:
    fake, student_id = seeded()

    async with fake.client() as client:
        with pytest.raises(WeakPasswordError):
            await create_login(client, student_id, EMAIL, "short")

    assert user_rows(fake) == []


@pytest.mark.parametrize("email", ["nobody", "@sidereal.example.com", "a@b", "a@.com"])
async def test_a_bad_email_is_refused(email: str) -> None:
    fake, student_id = seeded()

    async with fake.client() as client:
        with pytest.raises(InvalidEmailError):
            await create_login(client, student_id, email, PASSWORD)

    assert user_rows(fake) == []


async def test_without_a_student_role_no_user_is_created() -> None:
    fake = FakeDirectus()
    row = fake.seed(Collection.STUDENTS, {"name": "A. Tutee"})

    async with fake.client() as client:
        with pytest.raises(StudentRoleMissingError):
            await create_login(client, UUID(row["id"]), EMAIL, PASSWORD)

    assert user_rows(fake) == []


async def test_reset_password_writes_the_new_one() -> None:
    fake, student_id = seeded()

    async with fake.client() as client:
        login = await create_login(client, student_id, EMAIL, PASSWORD)
        again = await reset_password(client, student_id, "a-longer-one")

    assert again.user_id == login.user_id
    assert again.email == EMAIL
    assert user_rows(fake)[0]["password"] == "a-longer-one"


async def test_reset_password_needs_a_login_and_a_long_enough_password() -> None:
    fake, student_id = seeded()

    async with fake.client() as client:
        with pytest.raises(LoginMissingError):
            await reset_password(client, student_id, PASSWORD)
        await create_login(client, student_id, EMAIL, PASSWORD)
        with pytest.raises(WeakPasswordError):
            await reset_password(client, student_id, "short")

    assert user_rows(fake)[0]["password"] == PASSWORD


async def test_remove_login_deletes_the_user_and_unlinks_the_student() -> None:
    fake, student_id = seeded()

    async with fake.client() as client:
        await create_login(client, student_id, EMAIL, PASSWORD)

        student = await remove_login(client, student_id)

        assert student.user is None
        assert (await student_row(client, student_id)).user is None
    assert user_rows(fake) == []


async def test_remove_login_needs_a_login() -> None:
    fake, student_id = seeded()

    async with fake.client() as client:
        with pytest.raises(LoginMissingError):
            await remove_login(client, student_id)


async def test_whoami_is_a_student_when_a_student_row_points_at_the_caller() -> None:
    fake, student_id = seeded()
    fake.items[Collection.STUDENTS][str(student_id)]["user"] = str(DEFAULT_USER_ID)

    async with fake.client() as client:
        identity = await whoami(client)

    assert identity.role is CallerRole.STUDENT
    assert identity.student_id == student_id
    assert identity.id == DEFAULT_USER_ID


async def test_whoami_is_a_tutor_otherwise() -> None:
    fake, _ = seeded()

    async with fake.client() as client:
        identity = await whoami(client)

    assert identity.role is CallerRole.TUTOR
    assert identity.student_id is None


async def test_an_admin_is_never_read_as_a_student() -> None:
    """Admin wins, so the students table is not even asked about."""
    fake, student_id = seeded()
    fake.items[Collection.STUDENTS][str(student_id)]["user"] = str(DEFAULT_USER_ID)
    fake.admin = True

    async with fake.client() as client:
        identity = await whoami(client)

    assert identity.role is CallerRole.ADMIN
    assert identity.student_id is None
    assert "/items/students" not in [request.url.path for request in fake.requests]


async def test_a_student_role_login_no_student_points_at_is_refused() -> None:
    """The live failure: a removed student kept a session and was served the tutor's shell."""
    fake, _ = seeded()
    role = fake.rows(Collection.DIRECTUS_ROLES)[0]
    fake.user["role"] = role["id"]

    async with fake.client() as client:
        with pytest.raises(LoginUnlinkedError, match="no longer linked to a student"):
            await whoami(client)


async def test_a_tutors_own_role_leaves_them_a_tutor() -> None:
    fake, _ = seeded()
    tutor_role = fake.seed(Collection.DIRECTUS_ROLES, {"name": "Tutor"})
    fake.user["role"] = tutor_role["id"]

    async with fake.client() as client:
        identity = await whoami(client)

    assert identity.role is CallerRole.TUTOR


class Refuses(FakeDirectus):
    """A Directus that answers one method and path prefix with a refusal."""

    def __init__(self, method: str, prefix: str, status: int) -> None:
        super().__init__()
        self.refused = (method, prefix, status)

    def handle(self, request: httpx.Request) -> httpx.Response:
        method, prefix, status = self.refused
        if request.method == method and request.url.path.startswith(prefix):
            return httpx.Response(
                status, json={"errors": [{"message": "no", "extensions": {"code": "FORBIDDEN"}}]}
            )
        return super().handle(request)


def refusing(method: str, prefix: str, status: int) -> tuple[Refuses, UUID]:
    fake = Refuses(method, prefix, status)
    fake.seed(Collection.DIRECTUS_ROLES, {"name": "Student"})
    return fake, UUID(fake.seed(Collection.STUDENTS, {"name": "A. Tutee"})["id"])


async def test_a_refused_login_leaves_nothing_behind() -> None:
    """The login is created on the student's own field, so a refusal writes nothing at all."""
    fake, student_id = refusing("PATCH", "/items/students/", 400)

    async with fake.client() as client:
        with pytest.raises(LoginRefusedError, match="already be in use") as raised:
            await create_login(client, student_id, EMAIL, PASSWORD)

    assert raised.value.status == 400
    assert user_rows(fake) == []


async def test_a_student_directus_will_not_show_is_not_found() -> None:
    fake, student_id = refusing("GET", "/items/students/", 403)

    async with fake.client() as client:
        with pytest.raises(LoginRefusedError, match="could not be found") as raised:
            await create_login(client, student_id, EMAIL, PASSWORD)

    assert raised.value.status == 404


async def test_directus_being_unreachable_stays_a_directus_failure() -> None:
    fake, student_id = seeded()
    fake.unavailable_after = 2

    async with fake.client() as client:
        with pytest.raises(DirectusUnavailableError):
            await create_login(client, student_id, EMAIL, PASSWORD)


async def test_removing_a_login_releases_the_uploads_that_would_pin_it() -> None:
    fake = FakeDirectus()
    login = fake.seed(Collection.DIRECTUS_USERS, {"email": "leo@example.test"})
    row = fake.seed(Collection.STUDENTS, {"name": "Leo", "user": login["id"]})
    fake.register_file("working.jpg", b"jpeg", uploaded_by=login["id"])
    tutor = uuid4()

    async with fake.client() as client:
        student = await remove_login(client, UUID(row["id"]), uploads_to=tutor)

    assert student.user is None
    assert not fake.rows(Collection.DIRECTUS_USERS)
    assert [file["uploaded_by"] for file, _ in fake.files.values()] == [str(tutor)]


async def test_an_account_that_may_not_sign_in_says_so_without_saying_more() -> None:
    fake = FakeDirectus()
    fake.seed(Collection.DIRECTUS_USERS, {"email": "priya@example.test", "status": "suspended"})
    fake.seed(Collection.DIRECTUS_USERS, {"email": "amara@example.test", "status": "active"})

    async with fake.client() as client:
        assert await account_status(client, "priya@example.test") is AccountStatus.SUSPENDED
        assert await account_status(client, "amara@example.test") is AccountStatus.ACTIVE
        assert await account_status(client, "nobody@example.test") is AccountStatus.UNKNOWN
