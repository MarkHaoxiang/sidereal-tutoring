"""Who the caller is, and the Directus user that lets a student sign in."""

from __future__ import annotations

from enum import StrEnum
from typing import NoReturn
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from sidereal_core.directus import DirectusClient, DirectusClientError, DirectusError
from sidereal_core.files import release_uploads
from sidereal_core.models import Collection, DirectusUser, Student
from sidereal_core.students import StudentNotVisibleError, visible_student

STUDENT_ROLE = "Student"
UNLINKED = "This login is no longer linked to a student. Ask your tutor."
ACTIVE_STATUS = "active"
MIN_PASSWORD_LENGTH = 8
# What Directus answers when a rule refuses the write or its validation fails.
REFUSED = (400, 403)


class CallerRole(StrEnum):
    ADMIN = "admin"
    TUTOR = "tutor"
    STUDENT = "student"


class AccountStatus(StrEnum):
    """As much as anyone refused at sign-in is told about why."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


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


class LoginUnlinkedError(StudentLoginError):
    """A Student-role login no `students` row points at. It is nobody, not a tutor."""


class LoginRefusedError(StudentLoginError):
    """Directus refused the write. Its own wording never reaches a tutor."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


async def account_status(client: DirectusClient, email: str) -> AccountStatus:
    """Whether an account may sign in at all.

    Directus answers `INVALID_CREDENTIALS` for a suspended account and for a wrong password
    alike, so nothing else can tell someone which of the two they are looking at.
    """
    users = await client.list_users(filter={"email": {"_eq": email}}, limit=1)
    if not users:
        return AccountStatus.UNKNOWN
    if users[0].status == ACTIVE_STATUS:
        return AccountStatus.ACTIVE
    return AccountStatus.SUSPENDED


async def student_for_user(client: DirectusClient, user_id: UUID) -> Student | None:
    students = await client.list_items(
        Collection.STUDENTS, Student, filter={"user": {"_eq": str(user_id)}}, limit=1
    )
    return students[0] if students else None


async def identify(client: DirectusClient, user: DirectusUser) -> Identity:
    """Admin wins over every other reading, so an admin is never looked up as a student.

    A login in the Student role that no `students` row points at is refused rather than read
    as a tutor: a student whose login was removed kept a session, and the app served it the
    tutor's own shell.
    """
    if user.admin_access:
        return _identity(user, CallerRole.ADMIN, None)
    student = await student_for_user(client, user.id)
    if student is not None:
        return _identity(user, CallerRole.STUDENT, student.id)
    if await _in_student_role(client, user):
        raise LoginUnlinkedError(UNLINKED)
    return _identity(user, CallerRole.TUTOR, None)


async def _in_student_role(client: DirectusClient, user: DirectusUser) -> bool:
    """Whether the caller's own role is the Student one, by the name the bootstrap gave it."""
    if user.role is None:
        return False
    try:
        role = await client.get_role(user.role)
    except DirectusClientError:
        # A caller who may not read their own role is not one this can refuse.
        return False
    return role.name == STUDENT_ROLE


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
        # One write on the student: a tutor cannot read back a `directus_users` row they
        # created on its own, and an unlinked login would sign in and see nothing anyway.
        user_id = await client.create_related(
            Collection.STUDENTS,
            student_id,
            "user",
            {
                "email": email,
                "password": password,
                "role": str(role.id),
                "first_name": student.name,
                "status": "active",
                "provider": "default",
            },
        )
    except DirectusClientError as exc:
        _refuse(exc, "That login could not be created. The email may already be in use.")
    return StudentLogin(user_id=user_id, email=email)


async def reset_password(client: DirectusClient, student_id: UUID, password: str) -> StudentLogin:
    check_password(password)
    user_id = await _login_of(client, student_id)
    try:
        user = await client.update_user(user_id, {"password": password})
    except DirectusClientError as exc:
        _refuse(exc, "That password could not be set.")
    return _login(user, "")


async def remove_login(
    client: DirectusClient, student_id: UUID, *, uploads_to: UUID | None = None
) -> Student:
    """Delete the login. The student's work stays; only the way in goes."""
    user_id = await _login_of(client, student_id)
    try:
        # Their hand-in photos are the caller's to keep: deleting the user would leave them
        # with no `uploaded_by`, and a tutor's file rules are that column.
        await release_uploads(client, user_id, to=uploads_to)
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
        return await visible_student(client, student_id)
    except StudentNotVisibleError as exc:
        raise LoginRefusedError(404, str(exc)) from exc


def _refuse(exc: DirectusClientError, message: str) -> NoReturn:
    """A refusal or a validation failure is the tutor's to read; anything else stays as it is."""
    if isinstance(exc, DirectusError) and exc.status in REFUSED:
        raise LoginRefusedError(exc.status, message) from exc
    raise exc


def _login(user: DirectusUser, fallback: str) -> StudentLogin:
    return StudentLogin(user_id=user.id, email=user.email or fallback)


def _identity(user: DirectusUser, role: CallerRole, student_id: UUID | None) -> Identity:
    return Identity(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=role,
        student_id=student_id,
    )
