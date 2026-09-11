from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks
from sidereal_core.models import Collection, GenerationJob, GenerationKind
from sidereal_generate.jobs import JobInput, run_job, start_job

from sidereal_app.api.models import Health, JobRequest
from sidereal_app.deps import CurrentUser, Directus, GeneratorSet

router = APIRouter(prefix="/api")


@router.get("/health")
async def health() -> Health:
    """Liveness only. It does not reach Directus, so it stays up while Directus is down."""
    return Health(status="ok")


@router.post("/jobs/{kind}", status_code=202)
async def create_job(
    kind: GenerationKind,
    body: JobRequest,
    user: CurrentUser,
    client: Directus,
    generators: GeneratorSet,
    background: BackgroundTasks,
) -> GenerationJob:
    """Queue a generation and answer immediately; the job row carries the outcome."""
    job = await start_job(
        client,
        kind,
        JobInput(
            student=body.student_id,
            documents=tuple(body.document_ids),
            instructions=body.instructions,
            period_start=body.period_start,
            period_end=body.period_end,
        ),
        model=generators.for_kind(kind),
    )
    background.add_task(run_job, client, generators, job.id)
    return job


@router.get("/jobs/{job_id}")
async def read_job(job_id: UUID, user: CurrentUser, client: Directus) -> GenerationJob:
    return await client.get_item(Collection.GENERATION_JOBS, GenerationJob, job_id)
