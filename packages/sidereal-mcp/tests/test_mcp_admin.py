from __future__ import annotations

from mcp_doubles import build_services, seed_student
from sidereal_core.models import Collection, GenerationKind, JobStatus
from sidereal_core.testing import FakeDirectus
from sidereal_core.tutors import TUTOR_ROLE
from sidereal_mcp import tools


async def test_jobs_and_health_answer_with_typed_values() -> None:
    fake = FakeDirectus(admin=True)
    fake.seed(Collection.DIRECTUS_ROLES, {"name": TUTOR_ROLE})
    student_id = seed_student(fake)
    fake.seed(
        Collection.GENERATION_JOBS,
        {
            "kind": GenerationKind.FEEDBACK.value,
            "status": JobStatus.SUCCEEDED.value,
            "student": str(student_id),
        },
    )
    services = build_services(fake)

    jobs = await tools.list_jobs(services, JobStatus.SUCCEEDED)
    health = await tools.admin_health(services)

    assert [(row.job.kind, row.student_name, row.tutor_email) for row in jobs] == [
        (GenerationKind.FEEDBACK, "A. Tutee", None)
    ]
    assert health.directus.ok
    assert health.typeset.ok
    assert health.counts.students == 1
