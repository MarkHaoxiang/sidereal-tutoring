"""The one place a generated artefact is written back to Directus."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from anthropic import (
    APIConnectionError,
    APIError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import BaseModel, ConfigDict
from sidereal_core.directus import DirectusClient, DirectusError, DirectusUnavailableError
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
    Student,
)
from sidereal_core.typeset import TypesetClient, TypesetError, TypesetUnavailableError

from sidereal_generate.base import (
    FeedbackGenerator,
    GenerationError,
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
    PlanOutput,
)
from sidereal_generate.papers import PaperError, extract_paper
from sidereal_generate.settings import GenerateBackend, generate_settings
from sidereal_generate.typst import TYPST_WARNING, Compiled, generate_typst, upload_pdf

logger = logging.getLogger(__name__)
MATERIAL_GONE = (401, 403, 404)


class JobInputError(Exception):
    """A job row whose `input` cannot drive its kind. The message is what a tutor reads."""


class JobInput(BaseModel):
    """The job row's `input` column: everything needed to replay the generation."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    # A paper is library material, so `paper_extract` carries one document and no student.
    student: UUID | None = None
    documents: tuple[UUID, ...] = ()
    instructions: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    # Homework only. The app refuses `typst` for any other kind before the job is started.
    format: HomeworkFormat = HomeworkFormat.MARKDOWN


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
    """`SIDEREAL_GENERATE_BACKEND` decides: `claude` calls Anthropic, `fake` calls nothing."""
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
        case AuthenticationError() | PermissionDeniedError():
            return "The generation service refused the request."
        case RateLimitError():
            return "The generation service is busy; try again in a minute."
        case APIConnectionError():
            return "The generation service could not be reached. Try again shortly."
        case APIError():
            return "The generation service could not finish this request."
        case GenerationError():
            return "The generated result could not be used. Try again."
        case _:
            return "Generation failed unexpectedly."


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
    return GenerationRequest(
        student=student,
        documents=tuple(documents),
        instructions=job_input.instructions,
        period_start=job_input.period_start,
        period_end=job_input.period_end,
        format=job_input.format,
    )


async def _run(
    client: DirectusClient,
    generators: Generators,
    job: GenerationJob,
    job_input: JobInput,
    typeset: TypesetClient,
) -> tuple[Collection, UUID]:
    provenance = {
        "job": str(job.id),
        "model": generators.for_kind(job.kind),
        "documents": [str(document_id) for document_id in job_input.documents],
    }
    if job.kind is GenerationKind.PAPER_EXTRACT:
        return Collection.PAPERS, await extract_paper(
            client, generators.paper, typeset, _one_document(job_input), provenance
        )
    return await _generate(
        client, generators, job.kind, job_input, await _load(client, job_input), provenance, typeset
    )


def _one_document(job_input: JobInput) -> UUID:
    if len(job_input.documents) != 1:
        raise JobInputError("A paper is read from exactly one document.")
    return job_input.documents[0]


async def _generate(
    client: DirectusClient,
    generators: Generators,
    kind: GenerationKind,
    job_input: JobInput,
    request: GenerationRequest,
    provenance: dict[str, Any],
    typeset: TypesetClient,
) -> tuple[Collection, UUID]:
    match kind:
        case GenerationKind.HOMEWORK:
            compiled: Compiled | None = None
            if job_input.format is HomeworkFormat.TYPST:
                output, compiled = await generate_typst(generators.homework, typeset, request)
            else:
                output = await generators.homework.generate(request)
            return Collection.HOMEWORK, await _write_homework(
                client, request, output, compiled, provenance
            )
        case GenerationKind.FEEDBACK:
            feedback = await generators.feedback.generate(request)
            return Collection.FEEDBACK, await _write_feedback(
                client, request.student.id, feedback, provenance
            )
        case GenerationKind.PLAN:
            plan = await generators.plan.generate(request)
            return Collection.PLANS, await _write_plan(
                client, request.student.id, job_input, plan, provenance
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
    output: FeedbackOutput,
    provenance: dict[str, Any],
) -> UUID:
    feedback = await client.create_item(
        Collection.FEEDBACK,
        Feedback,
        FeedbackDraft(student=student_id, content=output.content, generated_from=provenance),
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
