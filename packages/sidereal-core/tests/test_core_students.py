from __future__ import annotations

from uuid import UUID, uuid4

import httpx
import pytest
from sidereal_core.directus import DirectusError
from sidereal_core.models import Collection
from sidereal_core.students import StudentNotVisibleError, visible_student
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
