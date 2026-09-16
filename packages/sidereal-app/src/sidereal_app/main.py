"""The FastAPI application, and where a Directus failure becomes an HTTP answer."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sidereal_core.directus import DEFAULT_TIMEOUT, DirectusError, DirectusUnavailableError
from sidereal_core.logins import (
    InvalidEmailError,
    LoginExistsError,
    LoginMissingError,
    LoginRefusedError,
    StudentLoginError,
    StudentRoleMissingError,
    WeakPasswordError,
)
from sidereal_core.settings import typeset_settings
from sidereal_core.students import StudentNotVisibleError
from sidereal_core.tutors import (
    TutorError,
    TutorHasStudentsError,
    TutorNotFoundError,
    TutorRefusedError,
    TutorRoleMissingError,
)
from sidereal_core.typeset import DEFAULT_TIMEOUT as TYPESET_TIMEOUT
from sidereal_core.typeset import (
    TypesetClient,
    TypesetError,
    TypesetUnavailableError,
)
from sidereal_generate.papers import PaperError
from sidereal_generate.typst import NotTypstError
from sidereal_ingest import HttpxFetcher, default_ingesters

from sidereal_app.api.errors import (
    DIRECTUS_REJECTED,
    DIRECTUS_UNAVAILABLE,
    FORMAT_UNSUPPORTED,
    INVALID_EMAIL,
    LOGIN_EXISTS,
    LOGIN_FAILED,
    LOGIN_MISSING,
    LOGIN_REFUSED,
    PAPER_UNUSABLE,
    STUDENT_NOT_FOUND,
    STUDENT_ROLE_MISSING,
    TUTOR_HAS_STUDENTS,
    TUTOR_NOT_FOUND,
    TUTOR_REFUSED,
    TUTOR_ROLE_MISSING,
    TYPESET_FAILED,
    TYPESET_UNAVAILABLE,
    WEAK_PASSWORD,
    error_body,
)
from sidereal_app.api.routes import VERSION, router

TITLE = "Sidereal Tutoring"
FETCH_TIMEOUT = 20.0
LOGIN_ERRORS: dict[type[Exception], tuple[int, str]] = {
    LoginExistsError: (409, LOGIN_EXISTS),
    LoginMissingError: (404, LOGIN_MISSING),
    InvalidEmailError: (422, INVALID_EMAIL),
    WeakPasswordError: (422, WEAK_PASSWORD),
    StudentRoleMissingError: (500, STUDENT_ROLE_MISSING),
}
TUTOR_ERRORS: dict[type[Exception], tuple[int, str]] = {
    TutorHasStudentsError: (409, TUTOR_HAS_STUDENTS),
    TutorNotFoundError: (404, TUTOR_NOT_FOUND),
    TutorRoleMissingError: (500, TUTOR_ROLE_MISSING),
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # One pool for every Directus call, one for fetching material, one for typesetting. All
    # outlive the request so a background job can still work after the response has been sent.
    async with (
        httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as pool,
        httpx.AsyncClient(timeout=FETCH_TIMEOUT, follow_redirects=True) as web,
        httpx.AsyncClient(timeout=TYPESET_TIMEOUT) as typeset,
    ):
        app.state.http = pool
        app.state.ingesters = default_ingesters(HttpxFetcher(http_client=web))
        app.state.typeset = TypesetClient(typeset_settings().url, http_client=typeset)
        yield


def create_app() -> FastAPI:
    app = FastAPI(title=TITLE, version=VERSION, lifespan=lifespan)
    app.include_router(router)
    app.add_exception_handler(DirectusUnavailableError, _unavailable)
    app.add_exception_handler(DirectusError, _rejected)
    app.add_exception_handler(StudentLoginError, _login_refused)
    app.add_exception_handler(TutorError, _tutor_refused)
    app.add_exception_handler(StudentNotVisibleError, _student_not_found)
    app.add_exception_handler(TypesetUnavailableError, _typeset_unavailable)
    app.add_exception_handler(TypesetError, _typeset_failed)
    app.add_exception_handler(NotTypstError, _not_typst)
    app.add_exception_handler(PaperError, _paper_unusable)
    return app


def _unavailable(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=error_body(DIRECTUS_UNAVAILABLE, "Directus is not reachable; try again shortly."),
    )


def _rejected(request: Request, exc: Exception) -> JSONResponse:
    """Directus answered with an error. Its status is the honest one to pass on."""
    status = exc.status if isinstance(exc, DirectusError) else 502
    return JSONResponse(
        status_code=status if 400 <= status < 600 else 502,
        content=error_body(DIRECTUS_REJECTED, str(exc)),
    )


def _typeset_unavailable(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=error_body(
            TYPESET_UNAVAILABLE,
            "The typeset service is not reachable, so nothing can be compiled; try again shortly.",
        ),
    )


def _typeset_failed(request: Request, exc: Exception) -> JSONResponse:
    """The compiler's own diagnostics: the tutor needs the line, not a summary."""
    diagnostics = exc.diagnostics if isinstance(exc, TypesetError) else ()
    return JSONResponse(
        status_code=422,
        content=error_body(
            TYPESET_FAILED,
            "That Typst source did not compile.",
            diagnostics=[diagnostic.model_dump(mode="json") for diagnostic in diagnostics],
        ),
    )


def _not_typst(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=422, content=error_body(FORMAT_UNSUPPORTED, str(exc)))


def _paper_unusable(request: Request, exc: Exception) -> JSONResponse:
    """A paper whose structure cannot be rendered. The sentence is the one generate wrote."""
    return JSONResponse(status_code=422, content=error_body(PAPER_UNUSABLE, str(exc)))


def _login_refused(request: Request, exc: Exception) -> JSONResponse:
    """The sentence is the one core wrote; the app only decides the status and the code."""
    if isinstance(exc, LoginRefusedError):
        return JSONResponse(status_code=exc.status, content=error_body(LOGIN_REFUSED, str(exc)))
    status, code = LOGIN_ERRORS.get(type(exc), (500, LOGIN_FAILED))
    return JSONResponse(status_code=status, content=error_body(code, str(exc)))


def _student_not_found(request: Request, exc: Exception) -> JSONResponse:
    """A student the caller's own token cannot see is one that does not exist."""
    return JSONResponse(status_code=404, content=error_body(STUDENT_NOT_FOUND, str(exc)))


def _tutor_refused(request: Request, exc: Exception) -> JSONResponse:
    """The sentence is the one core wrote; the app only decides the status and the code."""
    if isinstance(exc, TutorRefusedError):
        return JSONResponse(status_code=exc.status, content=error_body(TUTOR_REFUSED, str(exc)))
    status, code = TUTOR_ERRORS.get(type(exc), (500, TUTOR_REFUSED))
    return JSONResponse(status_code=status, content=error_body(code, str(exc)))


app = create_app()
