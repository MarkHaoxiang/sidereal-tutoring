from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sidereal_app.deps import get_generators, get_http_client, get_ingesters, get_typeset
from sidereal_app.main import create_app
from sidereal_core.models import Collection
from sidereal_core.testing import FakeDirectus, FakeTypeset
from sidereal_generate.jobs import Generators

TEXT = {"type": "text", "text": "Factorise x^2 - 5x + 6."}


class Scoped(FakeDirectus):
    """A Directus that hides every `students` row but one, the way a tutor's rules do."""

    def __init__(self) -> None:
        super().__init__()
        self.mine = str(self.seed(Collection.STUDENTS, {"name": "Mine"})["id"])
        self.theirs = str(self.seed(Collection.STUDENTS, {"name": "Another tutor's"})["id"])

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith("/items/students/") and not path.endswith(self.mine):
            return httpx.Response(
                403, json={"errors": [{"message": "no", "extensions": {"code": "FORBIDDEN"}}]}
            )
        return super().handle(request)


@pytest.fixture
def scoped() -> Scoped:
    return Scoped()


@pytest.fixture
def scoped_client(
    scoped: Scoped,
    fake_typeset: FakeTypeset,
    generators: Generators,
    ingesters: list[object],
) -> Iterator[TestClient]:
    app = create_app()
    pool = httpx.AsyncClient(transport=scoped.transport())
    app.dependency_overrides[get_http_client] = lambda: pool
    app.dependency_overrides[get_generators] = lambda: generators
    app.dependency_overrides[get_ingesters] = lambda: ingesters
    app.dependency_overrides[get_typeset] = lambda: fake_typeset.client()
    with TestClient(app) as test_client:
        yield test_client


def test_material_cannot_be_filed_against_another_tutors_student(
    scoped_client: TestClient, scoped: Scoped, auth: dict[str, str]
) -> None:
    response = scoped_client.post(
        "/api/documents", headers=auth, json={"student_id": scoped.theirs, "source": TEXT}
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "student_not_found"
    assert scoped.rows(Collection.DOCUMENTS) == []


def test_a_job_cannot_be_queued_for_another_tutors_student(
    scoped_client: TestClient, scoped: Scoped, auth: dict[str, str]
) -> None:
    response = scoped_client.post(
        "/api/jobs/homework", headers=auth, json={"student_id": scoped.theirs}
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "student_not_found"
    assert scoped.rows(Collection.GENERATION_JOBS) == []


def test_the_tutors_own_student_is_still_reachable(
    scoped_client: TestClient, scoped: Scoped, auth: dict[str, str]
) -> None:
    filed = scoped_client.post(
        "/api/documents", headers=auth, json={"student_id": scoped.mine, "source": TEXT}
    )
    queued = scoped_client.post(
        "/api/jobs/homework", headers=auth, json={"student_id": scoped.mine}
    )

    assert filed.status_code == 202
    assert queued.status_code == 202
    assert UUID(filed.json()["student"]) == UUID(scoped.mine)
