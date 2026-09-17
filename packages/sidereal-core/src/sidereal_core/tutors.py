"""The practice's tutors, and whether the system behind them is up. Admin work only."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping
from collections.abc import Set as AbstractSet
from datetime import datetime
from enum import StrEnum
from typing import Any, NoReturn
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError

from sidereal_core.directus import DirectusClient, DirectusClientError, DirectusError
from sidereal_core.files import release_uploads
from sidereal_core.logins import REFUSED, check_email, check_password
from sidereal_core.models import (
    Collection,
    DirectusLicense,
    DirectusRole,
    DirectusUser,
    GenerationJob,
    JobStatus,
    Student,
)
from sidereal_core.typeset import TypesetClient, TypesetClientError

TUTOR_ROLE = "Tutor"
DEFAULT_JOB_LIMIT = 50
# A health answer is worth more late than never, so a probe that stalls is a degraded one.
PROBE_TIMEOUT = 3.0


class TutorStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class TutorAccount(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    status: str | None = None
    students: int = 0
    last_access: datetime | None = None


class AdminJob(BaseModel):
    """A generation job as the whole-practice listing shows it."""

    model_config = ConfigDict(frozen=True)

    job: GenerationJob
    student_name: str | None = None
    tutor_email: str | None = None


class DirectusHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    version: str | None = None
    license: DirectusLicense | None = None


class ApiHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool = True
    version: str


class TypesetHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool
    url: str


class GenerationHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend: str
    model: str


class HealthCounts(BaseModel):
    model_config = ConfigDict(frozen=True)

    tutors: int = 0
    students: int = 0
    documents: int = 0
    jobs_running: int = 0


class AdminHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    directus: DirectusHealth
    api: ApiHealth
    typeset: TypesetHealth
    generation: GenerationHealth
    counts: HealthCounts


class TutorError(Exception):
    """A tutor-account operation that cannot be carried out."""


class TutorRoleMissingError(TutorError):
    pass


class TutorNotFoundError(TutorError):
    pass


class TutorHasStudentsError(TutorError):
    pass


class TutorRefusedError(TutorError):
    """Directus refused the write. Its own wording never reaches an admin."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


async def list_tutors(client: DirectusClient) -> list[TutorAccount]:
    role = await _tutor_role(client)
    users = await client.list_users(filter={"role": {"_eq": str(role.id)}}, sort=["email"])
    counts = await client.count_items_by(Collection.STUDENTS, "tutor")
    return [_account(user, counts.get(str(user.id), 0)) for user in users]


async def create_tutor(
    client: DirectusClient,
    email: str,
    password: str,
    first_name: str | None = None,
    last_name: str | None = None,
) -> TutorAccount:
    check_email(email)
    check_password(password)
    role = await _tutor_role(client)
    body = {
        "email": email,
        "password": password,
        "role": str(role.id),
        "status": TutorStatus.ACTIVE.value,
    }
    if first_name is not None:
        body["first_name"] = first_name
    if last_name is not None:
        body["last_name"] = last_name
    try:
        user = await client.create_user(body)
    except DirectusClientError as exc:
        _refuse(exc, "That tutor could not be created. The email may already be in use.")
    return _account(user, 0)


async def reset_tutor_password(
    client: DirectusClient, user_id: UUID, password: str
) -> TutorAccount:
    check_password(password)
    await _tutor(client, user_id)
    try:
        user = await client.update_user(user_id, {"password": password})
    except DirectusClientError as exc:
        _refuse(exc, "That password could not be set.")
    return _account(user, await _student_count(client, user_id))


async def set_tutor_status(
    client: DirectusClient, user_id: UUID, status: TutorStatus
) -> TutorAccount:
    """A suspended tutor keeps their students and their work; only signing in stops."""
    await _tutor(client, user_id)
    try:
        user = await client.update_user(user_id, {"status": status.value})
    except DirectusClientError as exc:
        _refuse(exc, "That tutor's status could not be changed.")
    return _account(user, await _student_count(client, user_id))


async def remove_tutor(
    client: DirectusClient, user_id: UUID, *, uploads_to: UUID | None = None
) -> None:
    await _tutor(client, user_id)
    students = await _student_count(client, user_id)
    if students:
        held = "1 student" if students == 1 else f"{students} students"
        raise TutorHasStudentsError(
            f"This tutor still has {held}. Reassign them to another tutor first."
        )
    try:
        # Material they uploaded is the caller's to keep: deleting the user would leave it
        # with no `uploaded_by`, and a tutor's file rules are that column.
        await release_uploads(client, user_id, to=uploads_to)
        await client.delete_user(user_id)
    except DirectusClientError as exc:
        _refuse(exc, "That tutor could not be removed.")


async def list_jobs(
    client: DirectusClient,
    status: JobStatus | None = None,
    limit: int = DEFAULT_JOB_LIMIT,
) -> list[AdminJob]:
    """Every tutor's jobs, each carrying the student it is for and that student's tutor."""
    jobs = await client.list_items(
        Collection.GENERATION_JOBS,
        GenerationJob,
        filter=None if status is None else {"status": {"_eq": status.value}},
        limit=limit,
        sort=["-date_created"],
    )
    students = await _students_by_id(client, {job.student for job in jobs if job.student})
    tutors = await _tutors_by_id(
        client, {student.tutor for student in students.values() if student.tutor}
    )
    return [_admin_job(job, students, tutors) for job in jobs]


async def admin_health(
    client: DirectusClient,
    typeset: TypesetClient,
    *,
    api_version: str,
    backend: str,
    model: str,
) -> AdminHealth:
    """Never raises: a service that cannot be reached is `ok: false`, not an error."""
    directus, typeset_ok, counts = await asyncio.gather(
        _directus_health(client), _probe(typeset.healthy()), _counts(client)
    )
    return AdminHealth(
        directus=directus,
        api=ApiHealth(version=api_version),
        typeset=TypesetHealth(ok=bool(typeset_ok), url=typeset.base_url),
        generation=GenerationHealth(backend=backend, model=model),
        counts=counts,
    )


async def _directus_health(client: DirectusClient) -> DirectusHealth:
    info = await _probe(client.server_info())
    if info is None:
        return DirectusHealth(ok=False)
    return DirectusHealth(
        ok=True, version=info.version, license=await _probe(client.license_info())
    )


async def _counts(client: DirectusClient) -> HealthCounts:
    tutors, students, documents, jobs_running = await asyncio.gather(
        _probe(_tutor_count(client)),
        _probe(client.count_items(Collection.STUDENTS)),
        _probe(client.count_items(Collection.DOCUMENTS)),
        _probe(
            client.count_items(
                Collection.GENERATION_JOBS, filter={"status": {"_eq": JobStatus.RUNNING.value}}
            )
        ),
    )
    return HealthCounts(
        tutors=tutors or 0,
        students=students or 0,
        documents=documents or 0,
        jobs_running=jobs_running or 0,
    )


async def _tutor_count(client: DirectusClient) -> int:
    role = await client.find_role(TUTOR_ROLE)
    if role is None:
        return 0
    return await client.count_users(filter={"role": {"_eq": str(role.id)}})


async def _probe[T](awaitable: Awaitable[T]) -> T | None:
    try:
        async with asyncio.timeout(PROBE_TIMEOUT):
            return await awaitable
    except (TimeoutError, DirectusClientError, TypesetClientError, ValidationError):
        return None


async def _students_by_id(client: DirectusClient, ids: AbstractSet[UUID]) -> dict[str, Student]:
    """One query for every student the listing mentions, never one query per job."""
    if not ids:
        return {}
    rows = await client.list_items(Collection.STUDENTS, Student, filter=_in(ids), limit=len(ids))
    return {str(row.id): row for row in rows}


async def _tutors_by_id(client: DirectusClient, ids: AbstractSet[UUID]) -> dict[str, DirectusUser]:
    if not ids:
        return {}
    users = await client.list_users(filter=_in(ids), limit=len(ids))
    return {str(user.id): user for user in users}


def _in(ids: AbstractSet[UUID]) -> dict[str, Any]:
    return {"id": {"_in": [str(identifier) for identifier in ids]}}


def _admin_job(
    job: GenerationJob, students: Mapping[str, Student], tutors: Mapping[str, DirectusUser]
) -> AdminJob:
    """A deleted student's jobs stay: `input` carries who they were for, and it is read here."""
    student = students.get(str(job.student)) if job.student else None
    tutor = tutors.get(str(student.tutor)) if student and student.tutor else None
    return AdminJob(
        job=job,
        student_name=student.name if student is not None else _named(job, "student_name"),
        tutor_email=tutor.email if tutor is not None else _named(job, "tutor_email"),
    )


def _named(job: GenerationJob, field: str) -> str | None:
    value = (job.input or {}).get(field)
    return value if isinstance(value, str) and value else None


async def _tutor_role(client: DirectusClient) -> DirectusRole:
    role = await client.find_role(TUTOR_ROLE)
    if role is None:
        raise TutorRoleMissingError(
            "Directus has no Tutor role yet, so tutor accounts cannot be managed."
        )
    return role


async def _tutor(client: DirectusClient, user_id: UUID) -> DirectusUser:
    """Only a Tutor-role user is one of these; an admin or a student is not found here."""
    role = await _tutor_role(client)
    try:
        user = await client.get_user(user_id)
    except DirectusError as exc:
        raise TutorNotFoundError("That tutor could not be found.") from exc
    if user.role != role.id:
        raise TutorNotFoundError("That tutor could not be found.")
    return user


async def _student_count(client: DirectusClient, user_id: UUID) -> int:
    return await client.count_items(Collection.STUDENTS, filter={"tutor": {"_eq": str(user_id)}})


def _account(user: DirectusUser, students: int) -> TutorAccount:
    return TutorAccount(
        user_id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        status=user.status,
        students=students,
        last_access=user.last_access,
    )


def _refuse(exc: DirectusClientError, message: str) -> NoReturn:
    """A refusal or a validation failure is the admin's to read; anything else stays as it is."""
    if isinstance(exc, DirectusError) and exc.status in REFUSED:
        raise TutorRefusedError(exc.status, message) from exc
    raise exc
