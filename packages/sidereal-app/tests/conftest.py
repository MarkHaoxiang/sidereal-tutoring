from __future__ import annotations

from collections.abc import Iterator
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sidereal_app.deps import get_generators, get_http_client
from sidereal_app.main import create_app
from sidereal_core.models import Collection
from sidereal_core.testing import DEFAULT_TOKEN, FakeDirectus
from sidereal_generate.fake import FakeGenerator
from sidereal_generate.jobs import Generators
from sidereal_generate.models import (
    FeedbackOutput,
    GeneratedQuestion,
    HomeworkOutput,
    PlanOutput,
)

HOMEWORK = HomeworkOutput(
    title="Quadratics: week 3",
    content="## Quadratics",
    questions=(
        GeneratedQuestion(
            text="Factorise x^2 - 5x + 6.", answer="(x-2)(x-3)", topic="algebra", difficulty=2
        ),
    ),
)
FEEDBACK = FeedbackOutput(content="Strong on factorising.")
PLAN = PlanOutput(title="Spring term", content="Six weeks of algebra.")


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {DEFAULT_TOKEN}"}


@pytest.fixture
def fake_directus() -> FakeDirectus:
    return FakeDirectus()


@pytest.fixture
def generators() -> Generators:
    return Generators(
        homework=FakeGenerator(HOMEWORK, model="fake-homework"),
        feedback=FakeGenerator(FEEDBACK),
        plan=FakeGenerator(PLAN),
    )


@pytest.fixture
def student_id(fake_directus: FakeDirectus) -> UUID:
    row = fake_directus.seed(Collection.STUDENTS, {"name": "A. Tutee", "subjects": ["maths"]})
    return UUID(row["id"])


@pytest.fixture
def client(fake_directus: FakeDirectus, generators: Generators) -> Iterator[TestClient]:
    """The real auth dependency over a fake Directus: only the transport is substituted."""
    app = create_app()
    pool = httpx.AsyncClient(transport=fake_directus.transport())
    app.dependency_overrides[get_http_client] = lambda: pool
    app.dependency_overrides[get_generators] = lambda: generators
    with TestClient(app) as test_client:
        yield test_client
