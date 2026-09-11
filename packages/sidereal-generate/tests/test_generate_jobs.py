from __future__ import annotations

from datetime import date
from uuid import UUID

from sidereal_core.models import Collection, GenerationKind, JobStatus
from sidereal_core.testing import FakeDirectus
from sidereal_generate.fake import FailingGenerator, FakeGenerator
from sidereal_generate.jobs import Generators, JobInput, run_job, start_job
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


def generators() -> Generators:
    return Generators(
        homework=FakeGenerator(HOMEWORK, model="fake-homework"),
        feedback=FakeGenerator(FEEDBACK),
        plan=FakeGenerator(PLAN),
    )


def seeded() -> tuple[FakeDirectus, JobInput]:
    fake = FakeDirectus()
    student = fake.seed(Collection.STUDENTS, {"name": "A. Tutee", "subjects": ["maths"]})
    document = fake.seed(
        Collection.DOCUMENTS,
        {"title": "Lesson 3", "kind": "transcript", "text": "We factorised quadratics."},
    )
    return fake, JobInput(
        student=UUID(student["id"]),
        documents=(UUID(document["id"]),),
        instructions="Six questions.",
        period_start=date(2026, 1, 5),
        period_end=date(2026, 2, 16),
    )


async def test_a_homework_job_writes_questions_then_homework_then_succeeds() -> None:
    fake, job_input = seeded()
    all_generators = generators()

    async with fake.client() as client:
        job = await start_job(client, GenerationKind.HOMEWORK, job_input, model="fake-homework")
        assert job.status is JobStatus.QUEUED

        finished = await run_job(client, all_generators, job.id)

    assert finished.status is JobStatus.SUCCEEDED
    assert finished.output_collection == "homework"
    assert finished.error is None

    questions = fake.rows(Collection.QUESTIONS)
    assert [question["text"] for question in questions] == ["Factorise x^2 - 5x + 6."]
    assert questions[0]["subject"] == "maths"

    homework = fake.rows(Collection.HOMEWORK)[0]
    assert homework["id"] == str(finished.output_id)
    assert homework["title"] == "Quadratics: week 3"
    assert homework["generated_from"]["job"] == str(job.id)
    assert homework["generated_from"]["model"] == "fake-homework"
    assert homework["generated_from"]["documents"] == [str(job_input.documents[0])]
    assert homework["generated_from"]["questions"] == [questions[0]["id"]]


async def test_the_generator_sees_the_student_and_the_documents() -> None:
    fake, job_input = seeded()
    all_generators = generators()
    homework = all_generators.homework
    assert isinstance(homework, FakeGenerator)

    async with fake.client() as client:
        job = await start_job(client, GenerationKind.HOMEWORK, job_input, model="fake-homework")
        await run_job(client, all_generators, job.id)

    request = homework.requests[0]
    assert request.student.name == "A. Tutee"
    assert [document.title for document in request.documents] == ["Lesson 3"]
    assert request.instructions == "Six questions."


async def test_a_feedback_job_writes_one_feedback_row() -> None:
    fake, job_input = seeded()

    async with fake.client() as client:
        job = await start_job(client, GenerationKind.FEEDBACK, job_input, model="fake")
        finished = await run_job(client, generators(), job.id)

    assert finished.output_collection == "feedback"
    assert fake.rows(Collection.FEEDBACK)[0]["content"] == "Strong on factorising."


async def test_a_plan_job_carries_the_period_onto_the_row() -> None:
    fake, job_input = seeded()

    async with fake.client() as client:
        job = await start_job(client, GenerationKind.PLAN, job_input, model="fake")
        finished = await run_job(client, generators(), job.id)

    plan = fake.rows(Collection.PLANS)[0]
    assert finished.output_collection == "plans"
    assert plan["period_start"] == "2026-01-05"
    assert plan["period_end"] == "2026-02-16"


async def test_a_failing_generator_marks_the_job_failed_and_writes_nothing() -> None:
    fake, job_input = seeded()
    failing = Generators(
        homework=FailingGenerator(RuntimeError("model refused")),
        feedback=FakeGenerator(FEEDBACK),
        plan=FakeGenerator(PLAN),
    )

    async with fake.client() as client:
        job = await start_job(client, GenerationKind.HOMEWORK, job_input, model="fake")
        finished = await run_job(client, failing, job.id)

    assert finished.status is JobStatus.FAILED
    assert finished.error is not None
    assert "model refused" in finished.error
    assert fake.rows(Collection.HOMEWORK) == []


async def test_a_job_whose_input_is_unusable_fails_rather_than_raising() -> None:
    fake = FakeDirectus()
    row = fake.seed(
        Collection.GENERATION_JOBS,
        {"kind": "homework", "status": "queued", "input": {"documents": []}},
    )

    async with fake.client() as client:
        finished = await run_job(client, generators(), UUID(row["id"]))

    assert finished.status is JobStatus.FAILED
    assert finished.error is not None
    assert "ValidationError" in finished.error


def test_for_kind_reports_each_generators_model() -> None:
    all_generators = generators()

    assert all_generators.for_kind(GenerationKind.HOMEWORK) == "fake-homework"
    assert all_generators.for_kind(GenerationKind.FEEDBACK) == "fake"
    assert all_generators.for_kind(GenerationKind.PLAN) == "fake"
