"""Test doubles for the MCP tools. A module, not a conftest: module names are unique
across the workspace because mypy maps every test file to one."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from sidereal_core.models import Collection
from sidereal_core.testing import FakeDirectus, FakeTypeset
from sidereal_generate.fake import FakeGenerator
from sidereal_generate.jobs import Generators
from sidereal_generate.models import (
    FeedbackOutput,
    GeneratedQuestion,
    HomeworkOutput,
    PlanOutput,
)
from sidereal_ingest.transcript import TranscriptIngester
from sidereal_ingest.upload import UploadIngester
from sidereal_ingest.web import WebPageIngester
from sidereal_mcp.services import Services

FIXTURES = Path(__file__).parent / "fixtures"

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

PAGE = "<html><head><title>Indices</title></head><body><p>Powers of ten.</p></body></html>"


class StubFetcher:
    async def fetch(self, url: str) -> str:
        return PAGE


def build_services(fake: FakeDirectus, typeset: FakeTypeset | None = None) -> Services:
    return Services(
        typeset=(typeset or FakeTypeset()).client(),
        directus=fake.client(),
        ingesters=[TranscriptIngester(), WebPageIngester(StubFetcher()), UploadIngester()],
        generators=Generators(
            homework=FakeGenerator(HOMEWORK, model="fake-homework"),
            feedback=FakeGenerator(FEEDBACK),
            plan=FakeGenerator(PLAN),
        ),
    )


def seed_student(fake: FakeDirectus) -> UUID:
    row = fake.seed(Collection.STUDENTS, {"name": "A. Tutee", "subjects": ["maths"]})
    return UUID(row["id"])
