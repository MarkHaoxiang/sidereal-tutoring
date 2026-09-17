"""The one gate on a student: whether the caller's own token can see them at all."""

from __future__ import annotations

import logging
from uuid import UUID

from sidereal_core.directus import DirectusClient, DirectusClientError, DirectusError
from sidereal_core.files import release_uploads
from sidereal_core.models import Collection, GenerationJob, Student, StudentStatus

logger = logging.getLogger(__name__)

# What Directus answers for a row the caller may not see, may not have, or that is gone.
HIDDEN = (400, 403, 404)
SUSPENDED = "suspended"
ACTIVE = "active"
# A student's whole history of generation jobs is smaller than this.
MAX_JOBS = 1000


class StudentNotVisibleError(Exception):
    """A student this caller cannot see. To them the student does not exist."""


async def visible_student(client: DirectusClient, student_id: UUID) -> Student:
    """Read the student with the caller's token before writing anything that points at them.

    Directus checks a create rule against the payload alone and cannot reach through a
    relation, so nothing else stops one tutor filing work against another tutor's student.
    """
    try:
        return await client.get_item(Collection.STUDENTS, Student, student_id)
    except DirectusError as exc:
        if exc.status in HIDDEN:
            raise StudentNotVisibleError("That student could not be found.") from exc
        raise


async def archive_student(client: DirectusClient, student_id: UUID) -> Student:
    """Archiving revokes the way in: a student who has left cannot still sign in."""
    return await _set_status(client, student_id, StudentStatus.ARCHIVED, SUSPENDED)


async def unarchive_student(client: DirectusClient, student_id: UUID) -> Student:
    return await _set_status(client, student_id, StudentStatus.ACTIVE, ACTIVE)


async def delete_student(
    client: DirectusClient, student_id: UUID, *, uploads_to: UUID | None = None
) -> Student:
    """The student, their login and everything Directus cascades from the row.

    Sessions, homework, feedback and plans go with them; their material and their generation
    jobs are `SET NULL` and stay, the material as the shared library's.
    """
    student = await visible_student(client, student_id)
    await name_jobs(client, student)
    if student.user is not None:
        await release_uploads(client, student.user, to=uploads_to)
        await client.delete_user(student.user)
    await client.delete_item(Collection.STUDENTS, student_id)
    return student


async def name_jobs(client: DirectusClient, student: Student) -> list[GenerationJob]:
    """Write who each of this student's jobs was for into its own `input`, before the row goes.

    `generation_jobs.student` is `SET NULL`, so afterwards nothing on the row says whose work
    it was; and a retry that sent the deleted id back would answer with a foreign key.
    """
    jobs = await client.list_items(
        Collection.GENERATION_JOBS,
        GenerationJob,
        filter={"student": {"_eq": str(student.id)}},
        limit=MAX_JOBS,
    )
    email = await _tutor_email(client, student)
    for job in jobs:
        named = {key: value for key, value in (job.input or {}).items() if key != "student"}
        named["student_name"] = student.name
        if email is not None:
            named["tutor_email"] = email
        await client.update_item(
            Collection.GENERATION_JOBS, GenerationJob, job.id, {"input": named}
        )
    return jobs


async def _tutor_email(client: DirectusClient, student: Student) -> str | None:
    """Whose practice the job belonged to. A tutor this caller cannot read is left unnamed."""
    if student.tutor is None:
        return None
    try:
        return (await client.get_user(student.tutor)).email
    except DirectusClientError as exc:
        logger.warning("the tutor of student %s could not be read: %s", student.id, exc)
        return None


async def _set_status(
    client: DirectusClient, student_id: UUID, status: StudentStatus, login: str
) -> Student:
    student = await visible_student(client, student_id)
    if student.user is not None:
        await client.update_user(student.user, {"status": login})
    return await client.update_item(
        Collection.STUDENTS, Student, student_id, {"status": status.value}
    )
