"""The one place a generated artefact is written back to Directus."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from sidereal_core.directus import DirectusClient
from sidereal_core.models import (
    Collection,
    Document,
    Feedback,
    FeedbackDraft,
    GenerationJob,
    GenerationKind,
    Homework,
    HomeworkDraft,
    JobStatus,
    Plan,
    PlanDraft,
    Question,
    QuestionDraft,
    Student,
)

from sidereal_generate.base import FeedbackGenerator, HomeworkGenerator, PlanGenerator
from sidereal_generate.claude import feedback_generator, homework_generator, plan_generator
from sidereal_generate.models import (
    FeedbackOutput,
    GenerationRequest,
    HomeworkOutput,
    PlanOutput,
)


class JobInput(BaseModel):
    """The job row's `input` column: everything needed to replay the generation."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    student: UUID
    documents: tuple[UUID, ...] = ()
    instructions: str | None = None
    period_start: date | None = None
    period_end: date | None = None


@dataclass(frozen=True, slots=True)
class Generators:
    homework: HomeworkGenerator
    feedback: FeedbackGenerator
    plan: PlanGenerator

    def for_kind(self, kind: GenerationKind) -> str:
        match kind:
            case GenerationKind.HOMEWORK:
                return self.homework.model
            case GenerationKind.FEEDBACK:
                return self.feedback.model
            case GenerationKind.PLAN:
                return self.plan.model


def default_generators() -> Generators:
    return Generators(
        homework=homework_generator(), feedback=feedback_generator(), plan=plan_generator()
    )


async def start_job(
    client: DirectusClient, kind: GenerationKind, job_input: JobInput, *, model: str
) -> GenerationJob:
    return await client.create_item(
        Collection.GENERATION_JOBS,
        GenerationJob,
        {
            "kind": kind.value,
            "student": str(job_input.student),
            "status": JobStatus.QUEUED.value,
            "model": model,
            "input": job_input.model_dump(mode="json"),
        },
    )


async def run_job(client: DirectusClient, generators: Generators, job_id: UUID) -> GenerationJob:
    """Take a queued job to `succeeded` or `failed`. Never raises for a generation failure."""
    job = await client.get_item(Collection.GENERATION_JOBS, GenerationJob, job_id)
    await _patch(client, job_id, {"status": JobStatus.RUNNING.value})
    try:
        job_input = JobInput.model_validate(job.input)
        request = await _load(client, job_input)
        collection, output_id = await _generate(client, generators, job, job_input, request)
    except Exception as exc:  # noqa: BLE001 - a job records its failure, it does not raise it.
        return await _patch(
            client,
            job_id,
            {"status": JobStatus.FAILED.value, "error": f"{type(exc).__name__}: {exc}"},
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


async def _patch(client: DirectusClient, job_id: UUID, data: dict[str, Any]) -> GenerationJob:
    return await client.update_item(Collection.GENERATION_JOBS, GenerationJob, job_id, data)


async def _load(client: DirectusClient, job_input: JobInput) -> GenerationRequest:
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
    )


async def _generate(
    client: DirectusClient,
    generators: Generators,
    job: GenerationJob,
    job_input: JobInput,
    request: GenerationRequest,
) -> tuple[Collection, UUID]:
    provenance = {
        "job": str(job.id),
        "model": generators.for_kind(job.kind),
        "documents": [str(document_id) for document_id in job_input.documents],
    }
    match job.kind:
        case GenerationKind.HOMEWORK:
            output = await generators.homework.generate(request)
            return Collection.HOMEWORK, await _write_homework(
                client, job_input, request, output, provenance
            )
        case GenerationKind.FEEDBACK:
            feedback = await generators.feedback.generate(request)
            return Collection.FEEDBACK, await _write_feedback(
                client, job_input, feedback, provenance
            )
        case GenerationKind.PLAN:
            plan = await generators.plan.generate(request)
            return Collection.PLANS, await _write_plan(client, job_input, plan, provenance)


async def _write_homework(
    client: DirectusClient,
    job_input: JobInput,
    request: GenerationRequest,
    output: HomeworkOutput,
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
    homework = await client.create_item(
        Collection.HOMEWORK,
        Homework,
        HomeworkDraft(
            student=job_input.student,
            title=output.title,
            content=output.content,
            generated_from={**provenance, "questions": [str(qid) for qid in question_ids]},
        ),
    )
    return homework.id


async def _write_feedback(
    client: DirectusClient,
    job_input: JobInput,
    output: FeedbackOutput,
    provenance: dict[str, Any],
) -> UUID:
    feedback = await client.create_item(
        Collection.FEEDBACK,
        Feedback,
        FeedbackDraft(student=job_input.student, content=output.content, generated_from=provenance),
    )
    return feedback.id


async def _write_plan(
    client: DirectusClient,
    job_input: JobInput,
    output: PlanOutput,
    provenance: dict[str, Any],
) -> UUID:
    plan = await client.create_item(
        Collection.PLANS,
        Plan,
        PlanDraft(
            student=job_input.student,
            title=output.title,
            content=output.content,
            period_start=job_input.period_start,
            period_end=job_input.period_end,
            generated_from=provenance,
        ),
    )
    return plan.id
