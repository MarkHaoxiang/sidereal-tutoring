"""The one gate on a student: whether the caller's own token can see them at all."""

from __future__ import annotations

from uuid import UUID

from sidereal_core.directus import DirectusClient, DirectusError
from sidereal_core.models import Collection, Student

# What Directus answers for a row the caller may not see, may not have, or that is gone.
HIDDEN = (400, 403, 404)


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
