from __future__ import annotations

from uuid import UUID

import pytest
from sidereal_core.models import Student
from sidereal_generate.base import FeedbackGenerator, HomeworkGenerator, PlanGenerator
from sidereal_generate.fake import FailingGenerator, FakeGenerator
from sidereal_generate.models import (
    FeedbackOutput,
    GeneratedQuestion,
    GenerationRequest,
    HomeworkOutput,
    PlanOutput,
)

STUDENT_ID = UUID("11111111-1111-4111-8111-111111111111")


def a_request() -> GenerationRequest:
    return GenerationRequest(student=Student(id=STUDENT_ID, name="A. Tutee"))


async def test_the_fake_returns_its_output_and_records_the_request() -> None:
    output = HomeworkOutput(
        title="Week 1",
        content="Do these.",
        questions=(GeneratedQuestion(text="2 + 2?", answer="4", topic="arithmetic", difficulty=1),),
    )
    generator: HomeworkGenerator = FakeGenerator(output)

    assert await generator.generate(a_request()) is output
    assert isinstance(generator, FakeGenerator)
    assert len(generator.requests) == 1


async def test_the_fakes_satisfy_every_generator_protocol() -> None:
    feedback: FeedbackGenerator = FakeGenerator(FeedbackOutput(content="Good progress."))
    plan: PlanGenerator = FakeGenerator(PlanOutput(title="Spring", content="Six weeks."))

    assert (await feedback.generate(a_request())).content == "Good progress."
    assert (await plan.generate(a_request())).title == "Spring"
    assert feedback.model == "fake"


async def test_the_failing_generator_raises_what_it_was_given() -> None:
    generator: HomeworkGenerator = FailingGenerator(RuntimeError("upstream down"))

    with pytest.raises(RuntimeError, match="upstream down"):
        await generator.generate(a_request())
