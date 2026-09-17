"""The one gate on a student: whether the caller's own token can see them at all."""

from __future__ import annotations

from uuid import UUID

from sidereal_core.directus import DirectusClient, DirectusError
from sidereal_core.files import release_uploads
from sidereal_core.models import Collection, Student, StudentStatus

# What Directus answers for a row the caller may not see, may not have, or that is gone.
HIDDEN = (400, 403, 404)
SUSPENDED = "suspended"
ACTIVE = "active"


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
    if student.user is not None:
        await release_uploads(client, student.user, to=uploads_to)
        await client.delete_user(student.user)
    await client.delete_item(Collection.STUDENTS, student_id)
    return student


async def _set_status(
    client: DirectusClient, student_id: UUID, status: StudentStatus, login: str
) -> Student:
    student = await visible_student(client, student_id)
    if student.user is not None:
        await client.update_user(student.user, {"status": login})
    return await client.update_item(
        Collection.STUDENTS, Student, student_id, {"status": status.value}
    )
