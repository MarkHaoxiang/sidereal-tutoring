"""The one place a generated artefact is written back to Directus."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from anthropic import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)
from openai import APIConnectionError as OpenAIConnectionError
from openai import APIError as OpenAIError
from openai import AuthenticationError as OpenAIAuthenticationError
from openai import PermissionDeniedError as OpenAIPermissionDeniedError
from openai import RateLimitError as OpenAIRateLimitError
from pydantic import BaseModel, ConfigDict
from sidereal_core.directus import DirectusClient, DirectusError, DirectusUnavailableError
from sidereal_core.homework import ordered_questions
from sidereal_core.models import (
    Collection,
    Document,
    Feedback,
    FeedbackDraft,
    GenerationJob,
    GenerationKind,
    Homework,
    HomeworkDraft,
    HomeworkFormat,
    HomeworkQuestion,
    HomeworkQuestionDraft,
    JobStatus,
    Plan,
    PlanDraft,
    Question,
    QuestionDraft,
    Session,
    SessionStatus,
    Student,
)
from sidereal_core.students import StudentNotVisibleError, visible_student
from sidereal_core.typeset import TypesetClient, TypesetError, TypesetUnavailableError

from sidereal_generate.base import (
    FeedbackGenerator,
    GenerationError,
    GenerationNotConfiguredError,
    GenerationTruncatedError,
    HomeworkGenerator,
    PaperExtractor,
    PlanGenerator,
)
from sidereal_generate.claude import (
    feedback_generator,
    homework_generator,
    paper_extractor,
    plan_generator,
)
from sidereal_generate.fake import (
    FakeFeedbackGenerator,
    FakeHomeworkGenerator,
    FakePaperExtractor,
    FakePlanGenerator,
)
from sidereal_generate.models import (
    FeedbackOutput,
    GenerationRequest,
    HomeworkOutput,
    MarkedHomework,
    PlanOutput,
)
from sidereal_generate.openrouter import feedback_generator as openrouter_feedback_generator
from sidereal_generate.openrouter import homework_generator as openrouter_homework_generator
from sidereal_generate.openrouter import paper_extractor as openrouter_paper_extractor
from sidereal_generate.openrouter import plan_generator as openrouter_plan_generator
from sidereal_generate.papers import PaperError, extract_paper
from sidereal_generate.settings import GenerateBackend, generate_settings
from sidereal_generate.typst import TYPST_WARNING, Compiled, generate_typst, upload_pdf
from sidereal_generate.usage import UsageTally

logger = logging.getLogger(__name__)
MATERIAL_GONE = (401, 403, 404)
# How much of the generate layer's own sentence a job's `error` carries.
ERROR_DETAIL = 400
# Far enough ahead to find the next lesson without reading a term's worth of them.
SESSION_LOOKAHEAD = 50
STUDENT_GONE = "That job's student no longer exists, so it cannot be run again."


class JobInputError(Exception):
    """A job row whose `input` cannot drive its kind. The message is what a tutor reads."""


class JobStudentGoneError(Exception):
    """A job whose student has been deleted. Its history stays; it cannot be run again."""


class JobInput(BaseModel):
    """The job row's `input` column: everything needed to replay the generation."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    # A paper is library material, so `paper_extract` carries one document and no student.
    student: UUID | None = None
    documents: tuple[UUID, ...] = ()
    # Feedback only: the hand-ins it is about. The first is what the row is filed under.
    homework: tuple[UUID, ...] = ()
    instructions: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    # Homework only. The app refuses `typst` for any other kind before the job is started.
    format: HomeworkFormat = HomeworkFormat.MARKDOWN
    # `paper_extract` only: send the source PDF's pages as images too. None decides from the
    # PDF itself.
    pages: bool | None = None


@dataclass(frozen=True, slots=True)
class Generators:
    homework: HomeworkGenerator
    feedback: FeedbackGenerator
    plan: PlanGenerator

    paper: PaperExtractor

    def for_kind(self, kind: GenerationKind) -> str:
        match kind:
            case GenerationKind.HOMEWORK:
                return self.homework.model
            case GenerationKind.FEEDBACK:
                return self.feedback.model
            case GenerationKind.PLAN:
                return self.plan.model
            case GenerationKind.PAPER_EXTRACT:
                return self.paper.model


def default_generators() -> Generators:
    """`SIDEREAL_GENERATE_BACKEND` decides: `claude` calls Anthropic, `openrouter` calls
    OpenRouter, `fake` calls nothing. No client is built until the first `generate()`."""
    match generate_settings().backend:
        case GenerateBackend.FAKE:
            return Generators(
                homework=FakeHomeworkGenerator(),
                feedback=FakeFeedbackGenerator(),
                plan=FakePlanGenerator(),
                paper=FakePaperExtractor(),
            )
        case GenerateBackend.CLAUDE:
            return Generators(
                homework=homework_generator(),
                feedback=feedback_generator(),
                plan=plan_generator(),
                paper=paper_extractor(),
            )
        case GenerateBackend.OPENROUTER:
            return Generators(
                homework=openrouter_homework_generator(),
                feedback=openrouter_feedback_generator(),
                plan=openrouter_plan_generator(),
                paper=openrouter_paper_extractor(),
            )


async def start_job(
    client: DirectusClient, kind: GenerationKind, job_input: JobInput, *, model: str
) -> GenerationJob:
    return await client.create_item(
        Collection.GENERATION_JOBS,
        GenerationJob,
        {
            "kind": kind.value,
            "student": None if job_input.student is None else str(job_input.student),
            "status": JobStatus.QUEUED.value,
            "model": model,
            "input": job_input.model_dump(mode="json"),
        },
    )


async def retry_job(client: DirectusClient, generators: Generators, job_id: UUID) -> GenerationJob:
    """A new job carrying the old one's input. The row that failed stays as the history."""
    job = await client.get_item(Collection.GENERATION_JOBS, GenerationJob, job_id)
    job_input = await _replayable(client, job)
    return await start_job(client, job.kind, job_input, model=generators.for_kind(job.kind))


async def _replayable(client: DirectusClient, job: GenerationJob) -> JobInput:
    """The old input, with a student the practice still has.

    Deleting a student nulls the job's own `student` and leaves its `input` naming a row
    Directus will refuse: a retry that sent it back would answer with a foreign key.
    """
    job_input = JobInput.model_validate(job.input)
    if job.kind is GenerationKind.PAPER_EXTRACT:
        return job_input
    student = job_input.student or job.student
    if student is None:
        raise JobStudentGoneError(STUDENT_GONE)
    try:
        await visible_student(client, student)
    except StudentNotVisibleError as exc:
        raise JobStudentGoneError(STUDENT_GONE) from exc
    return job_input.model_copy(update={"student": student})


async def run_job(
    client: DirectusClient, generators: Generators, job_id: UUID, *, typeset: TypesetClient
) -> GenerationJob:
    """Take a queued job to `succeeded` or `failed`. Never raises for a generation failure."""
    job = await client.get_item(Collection.GENERATION_JOBS, GenerationJob, job_id)
    await _patch(client, job_id, {"status": JobStatus.RUNNING.value})
    try:
        job_input = JobInput.model_validate(job.input)
        collection, output_id = await _run(client, generators, job, job_input, typeset)
    except Exception as exc:  # A job records its failure; it does not raise it.
        logger.exception("generation job %s failed", job_id)
        return await _patch(
            client, job_id, {"status": JobStatus.FAILED.value, "error": _message(exc)}
        )
    return await _patch(
        client,
        job_id,
        {
            "status": JobStatus.SUCCEEDED.value,
            "output_collection": collection.value,
            "output_id": str(output_id),
            "error": None,
        },
    )


def _message(exc: BaseException) -> str:
    """What the tutor reads in `error`. The technical detail is logged, never stored."""
    match exc:
        case PaperError() | JobInputError():
            return str(exc)
        case TypesetUnavailableError():
            return "The typeset service could not be reached. Try again shortly."
        case TypesetError():
            return "The homework could not be typeset."
        case DirectusUnavailableError():
            return "The material library could not be reached. Try again shortly."
        case DirectusError() if exc.status in MATERIAL_GONE:
            return "Some of the selected material could no longer be read."
        case DirectusError():
            return "The material library refused this request."
        case (
            AuthenticationError()
            | PermissionDeniedError()
            | OpenAIAuthenticationError()
            | OpenAIPermissionDeniedError()
        ):
            return "The generation service refused the request."
        case RateLimitError() | OpenAIRateLimitError():
            return "The generation service is busy; try again in a minute."
        case APIConnectionError() | OpenAIConnectionError():
            return "The generation service could not be reached. Try again shortly."
        case APIError() | OpenAIError():
            return "The generation service could not finish this request."
        case GenerationNotConfiguredError():
            return "Generation is not set up yet. Ask an administrator to configure it."
        case GenerationTruncatedError():
            return "The answer was cut off before it was finished. Try again with less material."
        case GenerationError():
            return _unusable(str(exc))
        case _:
            return "Generation failed unexpectedly."


def _unusable(sentence: str) -> str:
    """The generate layer's own words, so a failed extraction says what it could not read."""
    if not sentence.strip():
        return "The generated result could not be used. Try again."
    clipped = sentence if len(sentence) <= ERROR_DETAIL else f"{sentence[:ERROR_DETAIL]}…"
    return f"The generated result could not be used: {clipped}"


def _spent(provenance: dict[str, Any], usage: UsageTally) -> dict[str, Any]:
    """What the job's calls cost, filed beside what they produced. Shown nowhere yet."""
    spent = usage.provenance()
    return provenance if spent is None else {**provenance, "usage": spent}


async def _patch(client: DirectusClient, job_id: UUID, data: dict[str, Any]) -> GenerationJob:
    return await client.update_item(Collection.GENERATION_JOBS, GenerationJob, job_id, data)


async def _load(client: DirectusClient, job_input: JobInput) -> GenerationRequest:
    if job_input.student is None:
        raise JobInputError("That job does not say which student it is for.")
    student = await client.get_item(Collection.STUDENTS, Student, job_input.student)
    documents = [
        await client.get_item(Collection.DOCUMENTS, Document, document_id)
        for document_id in job_input.documents
    ]
    handed_in = [await _handed_in(client, homework_id) for homework_id in job_input.homework]
    today = datetime.now(UTC).date()
    return GenerationRequest(
        student=student,
        documents=tuple(documents),
        homework=tuple(handed_in),
        instructions=job_input.instructions,
        period_start=job_input.period_start,
        period_end=job_input.period_end,
        today=today,
        session_date=await _next_session(client, student.id, today),
        format=job_input.format,
    )


async def _handed_in(client: DirectusClient, homework_id: UUID) -> MarkedHomework:
    """The hand-in as the generator reads it: the questions as set, beside what came back."""
    homework = await client.get_item(Collection.HOMEWORK, Homework, homework_id)
    return MarkedHomework(
        homework=homework, questions=tuple(await ordered_questions(client, homework_id))
    )


async def _next_session(client: DirectusClient, student_id: UUID, today: date) -> date | None:
    """The student's next scheduled lesson, so nothing in the writing has to guess a weekday."""
    sessions = await client.list_items(
        Collection.SESSIONS,
        Session,
        filter={"student": {"_eq": str(student_id)}, "status": {"_eq": SessionStatus.SCHEDULED}},
        sort=["scheduled_at"],
        limit=SESSION_LOOKAHEAD,
    )
    upcoming = [
        session.scheduled_at.date()
        for session in sessions
        if session.scheduled_at is not None and session.scheduled_at.date() >= today
    ]
    return upcoming[0] if upcoming else None


async def _run(
    client: DirectusClient,
    generators: Generators,
    job: GenerationJob,
    job_input: JobInput,
    typeset: TypesetClient,
) -> tuple[Collection, UUID]:
    # One tally for the whole job: a retry and a repair are part of what it cost.
    usage = UsageTally()
    provenance = {
        "job": str(job.id),
        "model": generators.for_kind(job.kind),
        "documents": [str(document_id) for document_id in job_input.documents],
    }
    if job.kind is GenerationKind.PAPER_EXTRACT:
        paper_id, scheme_id = _paper_documents(job_input)
        return Collection.PAPERS, await extract_paper(
            client,
            generators.paper,
            typeset,
            paper_id,
            provenance,
            mark_scheme_id=scheme_id,
            pages=job_input.pages,
            usage=usage,
        )
    return await _generate(
        client,
        generators,
        job.kind,
        job_input,
        await _load(client, job_input),
        provenance,
        typeset,
        usage,
    )


def _paper_documents(job_input: JobInput) -> tuple[UUID, UUID | None]:
    """The paper, and the mark scheme when the tutor filed one beside it."""
    if not 1 <= len(job_input.documents) <= 2:
        raise JobInputError("A paper is read from one document, or two with its mark scheme.")
    paper, *scheme = job_input.documents
    return paper, scheme[0] if scheme else None


async def _generate(
    client: DirectusClient,
    generators: Generators,
    kind: GenerationKind,
    job_input: JobInput,
    request: GenerationRequest,
    provenance: dict[str, Any],
    typeset: TypesetClient,
    usage: UsageTally,
) -> tuple[Collection, UUID]:
    match kind:
        case GenerationKind.HOMEWORK:
            compiled: Compiled | None = None
            if job_input.format is HomeworkFormat.TYPST:
                output, compiled = await generate_typst(
                    generators.homework, typeset, request, usage=usage
                )
            else:
                output = await generators.homework.generate(request, usage=usage)
            return Collection.HOMEWORK, await _write_homework(
                client, request, output, compiled, _spent(provenance, usage)
            )
        case GenerationKind.FEEDBACK:
            feedback = await generators.feedback.generate(request, usage=usage)
            return Collection.FEEDBACK, await _write_feedback(
                client, request.student.id, job_input, feedback, _spent(provenance, usage)
            )
        case GenerationKind.PLAN:
            plan = await generators.plan.generate(request, usage=usage)
            return Collection.PLANS, await _write_plan(
                client, request.student.id, job_input, plan, _spent(provenance, usage)
            )
        case GenerationKind.PAPER_EXTRACT:  # handled before a request is built.
            raise JobInputError("A paper is read from a document, not generated for a student.")


async def _write_homework(
    client: DirectusClient,
    request: GenerationRequest,
    output: HomeworkOutput,
    compiled: Compiled | None,
    provenance: dict[str, Any],
) -> UUID:
    subject = request.student.subjects[0] if request.student.subjects else None
    question_ids = [
        (
            await client.create_item(
                Collection.QUESTIONS,
                Question,
                QuestionDraft(
                    text=question.text,
                    answer=question.answer,
                    topic=question.topic,
                    difficulty=question.difficulty,
                    subject=subject,
                ),
            )
        ).id
        for question in output.questions
    ]
    generated_from: dict[str, Any] = {
        **provenance,
        "questions": [str(qid) for qid in question_ids],
    }
    pdf: UUID | None = None
    if compiled is not None and compiled.pdf is not None:
        pdf = await upload_pdf(client, output.title, compiled.pdf)
    elif compiled is not None:
        # A source that will not compile is still the tutor's work: it is written, with the
        # compiler's report beside it, and the job succeeds carrying the warning.
        generated_from["warning"] = TYPST_WARNING
    homework = await client.create_item(
        Collection.HOMEWORK,
        Homework,
        HomeworkDraft(
            student=request.student.id,
            title=output.title,
            content=output.content if compiled is None else compiled.source,
            format=HomeworkFormat.MARKDOWN if compiled is None else HomeworkFormat.TYPST,
            pdf=pdf,
            compile_error=None if compiled is None else compiled.error,
            generated_from=generated_from,
        ),
    )
    await _link_questions(client, homework.id, question_ids)
    return homework.id


async def _link_questions(
    client: DirectusClient, homework_id: UUID, question_ids: Sequence[UUID]
) -> None:
    """The m2m rows the `questions` alias reads, in the order the model produced them."""
    for position, question_id in enumerate(question_ids, start=1):
        await client.create_item(
            Collection.HOMEWORK_QUESTIONS,
            HomeworkQuestion,
            HomeworkQuestionDraft(homework=homework_id, question=question_id, sort=position),
        )


async def _write_feedback(
    client: DirectusClient,
    student_id: UUID,
    job_input: JobInput,
    output: FeedbackOutput,
    provenance: dict[str, Any],
) -> UUID:
    """Feedback about a hand-in is filed against it, so both views name the other."""
    homework = job_input.homework[0] if job_input.homework else None
    feedback = await client.create_item(
        Collection.FEEDBACK,
        Feedback,
        FeedbackDraft(
            student=student_id,
            homework=homework,
            content=output.content,
            generated_from={**provenance, "homework": [str(h) for h in job_input.homework]}
            if job_input.homework
            else provenance,
        ),
    )
    return feedback.id


async def _write_plan(
    client: DirectusClient,
    student_id: UUID,
    job_input: JobInput,
    output: PlanOutput,
    provenance: dict[str, Any],
) -> UUID:
    plan = await client.create_item(
        Collection.PLANS,
        Plan,
        PlanDraft(
            student=student_id,
            title=output.title,
            content=output.content,
            period_start=job_input.period_start,
            period_end=job_input.period_end,
            generated_from=provenance,
        ),
    )
    return plan.id
