from __future__ import annotations

import pytest
from mcp_doubles import build_services, seed_student
from sidereal_core.logins import CallerRole, LoginExistsError, LoginMissingError
from sidereal_core.models import Collection
from sidereal_core.testing import DEFAULT_USER_ID, FakeDirectus
from sidereal_mcp import tools

EMAIL = "tutee@sidereal.example.com"
PASSWORD = "correct-horse"


def with_role() -> FakeDirectus:
    fake = FakeDirectus()
    fake.seed(Collection.DIRECTUS_ROLES, {"name": "Student"})
    return fake


async def test_whoami_reports_the_tutor_behind_the_token() -> None:
    fake = with_role()
    seed_student(fake)

    identity = await tools.whoami(build_services(fake))

    assert identity.id == DEFAULT_USER_ID
    assert identity.role is CallerRole.TUTOR
    assert identity.student_id is None


async def test_whoami_reports_a_student() -> None:
    fake = with_role()
    student_id = seed_student(fake)
    fake.items[Collection.STUDENTS][str(student_id)]["user"] = str(DEFAULT_USER_ID)

    identity = await tools.whoami(build_services(fake))

    assert identity.role is CallerRole.STUDENT
    assert identity.student_id == student_id


async def test_the_login_tools_create_reset_and_remove_one() -> None:
    fake = with_role()
    student_id = seed_student(fake)
    services = build_services(fake)

    created = await tools.create_student_login(services, student_id, EMAIL, PASSWORD)
    reset = await tools.reset_student_password(services, student_id, "a-longer-one")
    assert fake.rows(Collection.DIRECTUS_USERS)[0]["password"] == "a-longer-one"

    student = await tools.remove_student_login(services, student_id)

    assert created.email == EMAIL
    assert reset.user_id == created.user_id
    assert student.user is None
    assert student.name == "A. Tutee"
    assert fake.rows(Collection.DIRECTUS_USERS) == []


async def test_the_login_tools_refuse_a_second_login_and_a_missing_one() -> None:
    fake = with_role()
    student_id = seed_student(fake)
    services = build_services(fake)

    with pytest.raises(LoginMissingError):
        await tools.remove_student_login(services, student_id)

    await tools.create_student_login(services, student_id, EMAIL, PASSWORD)
    with pytest.raises(LoginExistsError):
        await tools.create_student_login(services, student_id, EMAIL, PASSWORD)
