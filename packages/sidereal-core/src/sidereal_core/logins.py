"""Who the caller is, and the Directus user that lets a student sign in."""

from __future__ import annotations

from contextlib import suppress
from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from sidereal_core.directus import DirectusClient, DirectusClientError, DirectusError
from sidereal_core.models import Collection, DirectusUser, Student

STUDENT_ROLE = "Student"
MIN_PASSWORD_LENGTH = 8
# What Directus answers when a rule refuses the write or its validation fails.
REFUSED = (400, 403)
GONE = (400, 403, 404)


class CallerRole(StrEnum):
    TUTOR = "tutor"
    STUDENT = "student"


class Identity(BaseModel):
    """Who is calling, and the student row they are, when they are one."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    role: CallerRole
    student_id: UUID | None = None


class StudentLogin(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID
    email: str


class StudentLoginError(Exception):
    """A login operation the caller asked for that cannot be carried out."""


class LoginExistsError(StudentLoginError):
    pass


class LoginMissingError(StudentLoginError):
    pass


class InvalidEmailError(StudentLoginError):
    pass


class WeakPasswordError(StudentLoginError):
    pass


class StudentRoleMissingError(StudentLoginError):
    pass


class LoginRefusedError(StudentLoginError):
    """Directus refused the write. Its own wording never reaches a tutor."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


async def student_for_user(client: DirectusClient, user_id: UUID) -> Student | None:
    students = await client.list_items(
        Collection.STUDENTS, Student, filter={"user": {"_eq": str(user_id)}}, limit=1
    )
    return students[0] if students else None


async def identify(client: DirectusClient, user: DirectusUser) -> Identity:
    student = await student_for_user(client, user.id)
    return Identity(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=CallerRole.TUTOR if student is None else CallerRole.STUDENT,
        student_id=None if student is None else student.id,
    )


async def whoami(client: DirectusClient) -> Identity:
    return await identify(client, await client.me())


async def create_login(
    client: DirectusClient, student_id: UUID, email: str, password: str
) -> StudentLogin:
    check_email(email)
    check_password(password)
    student = await _student(client, student_id)
    if student.user is not None:
        raise LoginExistsError("This student already has a login.")
    role = await client.find_role(STUDENT_ROLE)
    if role is None:
        raise StudentRoleMissingError(
            "Directus has no Student role yet, so a student cannot be given a login."
        )
    try:
        user = await client.create_user(
            {
                "email": email,
                "password": password,
                "role": str(role.id),
                "first_name": student.name,
                "status": "active",
            }
        )
    except DirectusClientError as exc:
        _refuse(exc, "That login could not be created. The email may already be in use.")
    try:
        await client.update_item(Collection.STUDENTS, Student, student_id, {"user": str(user.id)})
    except DirectusClientError as exc:
        # An unlinked login would sign in and see nothing, so it does not outlive the failure.
        with suppress(DirectusClientError):
            await client.delete_user(user.id)
        _refuse(exc, "That login could not be given to this student.")
    return _login(user, email)


async def reset_password(client: DirectusClient, student_id: UUID, password: str) -> StudentLogin:
    check_password(password)
    user_id = await _login_of(client, student_id)
    try:
        user = await client.update_user(user_id, {"password": password})
    except DirectusClientError as exc:
        _refuse(exc, "That password could not be set.")
    return _login(user, "")


async def remove_login(client: DirectusClient, student_id: UUID) -> Student:
    """Delete the login. The student's work stays; only the way in goes."""
    user_id = await _login_of(client, student_id)
    try:
        await client.delete_user(user_id)
        return await client.update_item(Collection.STUDENTS, Student, student_id, {"user": None})
    except DirectusClientError as exc:
        _refuse(exc, "That login could not be removed.")


def check_email(email: str) -> None:
    local, _, domain = email.partition("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise InvalidEmailError("That does not look like an email address.")


def check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(f"A password needs at least {MIN_PASSWORD_LENGTH} characters.")


async def _login_of(client: DirectusClient, student_id: UUID) -> UUID:
    student = await _student(client, student_id)
    if student.user is None:
        raise LoginMissingError("This student has no login yet.")
    return student.user


async def _student(client: DirectusClient, student_id: UUID) -> Student:
    try:
        return await client.get_item(Collection.STUDENTS, Student, student_id)
    except DirectusError as exc:
        if exc.status in GONE:
            raise LoginRefusedError(404, "That student could not be found.") from exc
        raise


def _refuse(exc: DirectusClientError, message: str) -> NoReturn:
    """A refusal or a validation failure is the tutor's to read; anything else stays as it is."""
    if isinstance(exc, DirectusError) and exc.status in REFUSED:
        raise LoginRefusedError(exc.status, message) from exc
    raise exc


def _login(user: DirectusUser, fallback: str) -> StudentLogin:
    return StudentLogin(user_id=user.id, email=user.email or fallback)
