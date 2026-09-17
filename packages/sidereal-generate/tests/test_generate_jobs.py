from __future__ import annotations

from datetime import date
from uuid import UUID

import httpx2
import pytest
from anthropic import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    InternalServerError,
    PermissionDeniedError,
    RateLimitError,
)
from openai import APIConnectionError as OpenAIConnectionError
from openai import APIStatusError as OpenAIStatusError
from openai import AuthenticationError as OpenAIAuthenticationError
from openai import InternalServerError as OpenAIInternalServerError
from openai import PermissionDeniedError as OpenAIPermissionDeniedError
from openai import RateLimitError as OpenAIRateLimitError
from sidereal_core.directus import DirectusError, DirectusUnavailableError
from sidereal_core.models import Collection, GenerationKind, JobStatus
from sidereal_core.testing import FakeDirectus, FakeTypeset
from sidereal_generate.base import (
    GenerationError,
    GenerationNotConfiguredError,
    GenerationTruncatedError,
)
from sidereal_generate.fake import FailingGenerator, FakeGenerator, FakePaperExtractor
from sidereal_generate.jobs import Generators, JobInput, retry_job, run_job, start_job
from sidereal_generate.models import (
    FeedbackOutput,
    GeneratedQuestion,
    GenerationRequest,
    HomeworkOutput,
    PlanOutput,
)
from sidereal_generate.usage import UsageTally

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
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _anthropic[E: APIStatusError](error: type[E], status: int) -> E:
    """An SDK error built the way the SDK builds one, without a request going out."""
    request = httpx2.Request("POST", ANTHROPIC_URL)
    return error("refused", response=httpx2.Response(status, request=request), body=None)


def _openrouter[E: OpenAIStatusError](error: type[E], status: int) -> E:
    request = httpx2.Request("POST", OPENROUTER_URL)
    return error("refused", response=httpx2.Response(status, request=request), body=None)


def generators() -> Generators:
    return Generators(
        homework=FakeGenerator(HOMEWORK, model="fake-homework"),
        feedback=FakeGenerator(FEEDBACK),
        plan=FakeGenerator(PLAN),
        paper=FakePaperExtractor(),
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

    typeset = FakeTypeset().client()
    async with fake.client() as client:
        job = await start_job(client, GenerationKind.HOMEWORK, job_input, model="fake-homework")
        assert job.status is JobStatus.QUEUED

        finished = await run_job(client, all_generators, job.id, typeset=typeset)

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

    links = fake.rows(Collection.HOMEWORK_QUESTIONS)
    assert [(link["homework"], link["question"], link["sort"]) for link in links] == [
        (homework["id"], questions[0]["id"], 1)
    ]


async def test_every_generated_question_is_linked_to_the_homework_in_order() -> None:
    fake, job_input = seeded()
    three = HomeworkOutput(
        title="Quadratics: week 3",
        content="## Quadratics",
        questions=tuple(
            GeneratedQuestion(text=f"Question {n}.", answer=None, topic=None, difficulty=None)
            for n in (1, 2, 3)
        ),
    )
    all_generators = Generators(
        homework=FakeGenerator(three, model="fake-homework"),
        feedback=FakeGenerator(FEEDBACK),
        plan=FakeGenerator(PLAN),
        paper=FakePaperExtractor(),
    )

    typeset = FakeTypeset().client()
    async with fake.client() as client:
        job = await start_job(client, GenerationKind.HOMEWORK, job_input, model="fake-homework")
        await run_job(client, all_generators, job.id, typeset=typeset)

    homework = fake.rows(Collection.HOMEWORK)[0]
    questions = fake.rows(Collection.QUESTIONS)
    links = fake.rows(Collection.HOMEWORK_QUESTIONS)
    assert [link["sort"] for link in links] == [1, 2, 3]
    assert [link["question"] for link in links] == [question["id"] for question in questions]
    assert {link["homework"] for link in links} == {homework["id"]}


async def test_the_generator_sees_the_student_and_the_documents() -> None:
    fake, job_input = seeded()
    all_generators = generators()
    homework = all_generators.homework
    assert isinstance(homework, FakeGenerator)

    typeset = FakeTypeset().client()
    async with fake.client() as client:
        job = await start_job(client, GenerationKind.HOMEWORK, job_input, model="fake-homework")
        await run_job(client, all_generators, job.id, typeset=typeset)

    request = homework.requests[0]
    assert request.student.name == "A. Tutee"
    assert [document.title for document in request.documents] == ["Lesson 3"]
    assert request.instructions == "Six questions."


async def test_a_feedback_job_writes_one_feedback_row() -> None:
    fake, job_input = seeded()

    typeset = FakeTypeset().client()
    async with fake.client() as client:
        job = await start_job(client, GenerationKind.FEEDBACK, job_input, model="fake")
        finished = await run_job(client, generators(), job.id, typeset=typeset)

    assert finished.output_collection == "feedback"
    assert fake.rows(Collection.FEEDBACK)[0]["content"] == "Strong on factorising."


async def test_a_plan_job_carries_the_period_onto_the_row() -> None:
    fake, job_input = seeded()

    typeset = FakeTypeset().client()
    async with fake.client() as client:
        job = await start_job(client, GenerationKind.PLAN, job_input, model="fake")
        finished = await run_job(client, generators(), job.id, typeset=typeset)

    plan = fake.rows(Collection.PLANS)[0]
    assert finished.output_collection == "plans"
    assert plan["period_start"] == "2026-01-05"
    assert plan["period_end"] == "2026-02-16"


async def test_a_job_whose_input_is_unusable_fails_rather_than_raising() -> None:
    fake = FakeDirectus()
    row = fake.seed(
        Collection.GENERATION_JOBS,
        {"kind": "homework", "status": "queued", "input": {"documents": []}},
    )

    typeset = FakeTypeset().client()
    async with fake.client() as client:
        finished = await run_job(client, generators(), UUID(row["id"]), typeset=typeset)

    assert finished.status is JobStatus.FAILED
    assert finished.error == "That job does not say which student it is for."


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (DirectusUnavailableError("refused"), "The material library could not be reached."),
        (DirectusError(403, message="forbidden"), "Some of the selected material could no"),
        (DirectusError(404, message="gone"), "Some of the selected material could no"),
        (DirectusError(400, message="bad"), "The material library refused this request."),
        (_anthropic(AuthenticationError, 401), "The generation service refused the request."),
        (_anthropic(PermissionDeniedError, 403), "The generation service refused the request."),
        (_anthropic(RateLimitError, 429), "The generation service is busy"),
        (
            APIConnectionError(request=httpx2.Request("POST", ANTHROPIC_URL)),
            "The generation service could not be reached.",
        ),
        (
            _anthropic(InternalServerError, 500),
            "The generation service could not finish this request.",
        ),
        (
            _openrouter(OpenAIAuthenticationError, 401),
            "The generation service refused the request.",
        ),
        (
            _openrouter(OpenAIPermissionDeniedError, 403),
            "The generation service refused the request.",
        ),
        (_openrouter(OpenAIRateLimitError, 429), "The generation service is busy"),
        (
            OpenAIConnectionError(request=httpx2.Request("POST", OPENROUTER_URL)),
            "The generation service could not be reached.",
        ),
        (
            _openrouter(OpenAIInternalServerError, 500),
            "The generation service could not finish this request.",
        ),
        (GenerationNotConfiguredError("OPENROUTER_API_KEY is not set"), "Generation is not set up"),
        (GenerationTruncatedError("ran out of output budget"), "The answer was cut off"),
        (GenerationError("no tool call"), "The generated result could not be used: no tool call"),
        (RuntimeError("model refused"), "Generation failed unexpectedly."),
    ],
)
async def test_a_failure_reaches_the_tutor_as_a_sentence_not_a_traceback(
    error: Exception, message: str
) -> None:
    fake, job_input = seeded()
    failing = Generators(
        homework=FailingGenerator(error),
        feedback=FakeGenerator(FEEDBACK),
        plan=FakeGenerator(PLAN),
        paper=FakePaperExtractor(),
    )

    typeset = FakeTypeset().client()
    async with fake.client() as client:
        job = await start_job(client, GenerationKind.HOMEWORK, job_input, model="fake")
        finished = await run_job(client, failing, job.id, typeset=typeset)

    assert finished.status is JobStatus.FAILED
    assert finished.error is not None
    assert finished.error.startswith(message)
    assert type(error).__name__ not in finished.error
    assert fake.rows(Collection.HOMEWORK) == []


async def test_material_the_job_may_no_longer_read_is_said_plainly() -> None:
    """The generator is never reached: Directus refuses the document the job names."""
    fake, job_input = seeded()
    fake.items[Collection.DOCUMENTS] = {}

    typeset = FakeTypeset().client()
    async with fake.client() as client:
        job = await start_job(client, GenerationKind.HOMEWORK, job_input, model="fake")
        finished = await run_job(client, generators(), job.id, typeset=typeset)

    assert finished.status is JobStatus.FAILED
    assert finished.error == "Some of the selected material could no longer be read."


class Recording(FakeGenerator[FeedbackOutput]):
    """A generator that keeps the request it was given, so the prompt can be read back."""

    def __init__(self) -> None:
        super().__init__(FEEDBACK)
        self.requests: list[GenerationRequest] = []

    async def generate(
        self, request: GenerationRequest, *, usage: UsageTally | None = None
    ) -> FeedbackOutput:
        self.requests.append(request)
        return await super().generate(request, usage=usage)


def handed_in(fake: FakeDirectus, student_id: str) -> str:
    homework = fake.seed(
        Collection.HOMEWORK,
        {
            "student": student_id,
            "title": "Moments",
            "content": "",
            "status": "marked",
            "submission": "Q1 R_D = 90 N",
            "submission_transcription": {"text": "4.8 + 2.4", "confidence": "high"},
            "marking": {"total_awarded": 4, "total_available": 6, "questions": []},
        },
    )
    question = fake.seed(Collection.QUESTIONS, {"text": "A plank $A B$.", "number": "1"})
    fake.seed(
        Collection.HOMEWORK_QUESTIONS,
        {"homework": homework["id"], "question": question["id"], "sort": 1},
    )
    return str(homework["id"])


async def test_feedback_reads_the_hand_in_and_is_filed_against_it() -> None:
    fake, job_input = seeded()
    student_id = str(job_input.student)
    homework_id = handed_in(fake, student_id)
    fake.seed(
        Collection.SESSIONS,
        {"student": student_id, "scheduled_at": "2099-09-18T17:00:00+00:00", "status": "scheduled"},
    )
    feedback = Recording()
    all_generators = generators()
    all_generators = Generators(
        homework=all_generators.homework,
        feedback=feedback,
        plan=all_generators.plan,
        paper=all_generators.paper,
    )

    typeset = FakeTypeset().client()
    async with fake.client() as client:
        job = await start_job(
            client,
            GenerationKind.FEEDBACK,
            job_input.model_copy(update={"homework": (UUID(homework_id),)}),
            model="fake",
        )
        finished = await run_job(client, all_generators, job.id, typeset=typeset)

    assert finished.status is JobStatus.SUCCEEDED
    row = fake.rows(Collection.FEEDBACK)[0]
    assert row["homework"] == homework_id
    assert row["generated_from"]["homework"] == [homework_id]
    asked = feedback.requests[0]
    assert asked.homework[0].homework.submission == "Q1 R_D = 90 N"
    assert [question.number for question in asked.homework[0].questions] == ["1"]
    assert asked.today is not None
    assert asked.session_date == date(2099, 9, 18)


async def test_feedback_about_nothing_in_particular_is_filed_against_nothing() -> None:
    fake, job_input = seeded()

    typeset = FakeTypeset().client()
    async with fake.client() as client:
        job = await start_job(client, GenerationKind.FEEDBACK, job_input, model="fake")
        await run_job(client, generators(), job.id, typeset=typeset)

    assert fake.rows(Collection.FEEDBACK)[0].get("homework") is None


async def test_a_lesson_already_past_is_not_the_next_one() -> None:
    fake, job_input = seeded()
    feedback = Recording()
    fake.seed(
        Collection.SESSIONS,
        {
            "student": str(job_input.student),
            "scheduled_at": "2020-01-01T17:00:00+00:00",
            "status": "scheduled",
        },
    )
    built = generators()
    built = Generators(
        homework=built.homework, feedback=feedback, plan=built.plan, paper=built.paper
    )

    typeset = FakeTypeset().client()
    async with fake.client() as client:
        job = await start_job(client, GenerationKind.FEEDBACK, job_input, model="fake")
        await run_job(client, built, job.id, typeset=typeset)

    assert feedback.requests[0].session_date is None


async def test_a_retry_queues_the_same_input_and_leaves_the_failed_row_alone() -> None:
    fake, job_input = seeded()
    built = generators()

    typeset = FakeTypeset().client()
    async with fake.client() as client:
        failed = await start_job(client, GenerationKind.FEEDBACK, job_input, model="fake")
        again = await retry_job(client, built, failed.id)
        finished = await run_job(client, built, again.id, typeset=typeset)

    assert again.id != failed.id
    assert again.kind is GenerationKind.FEEDBACK
    assert again.input == failed.input
    assert finished.status is JobStatus.SUCCEEDED
    assert len(fake.rows(Collection.GENERATION_JOBS)) == 2
