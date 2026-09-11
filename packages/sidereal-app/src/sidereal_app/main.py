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
from sidereal_ingest import HttpxFetcher, default_ingesters

from sidereal_app.api.errors import (
    DIRECTUS_REJECTED,
    DIRECTUS_UNAVAILABLE,
    INVALID_EMAIL,
    LOGIN_EXISTS,
    LOGIN_FAILED,
    LOGIN_MISSING,
    LOGIN_REFUSED,
    STUDENT_ROLE_MISSING,
    WEAK_PASSWORD,
    error_body,
)
from sidereal_app.api.routes import router

TITLE = "Sidereal Tutoring"
VERSION = "0.1.0"
FETCH_TIMEOUT = 20.0
LOGIN_ERRORS: dict[type[Exception], tuple[int, str]] = {
    LoginExistsError: (409, LOGIN_EXISTS),
    LoginMissingError: (404, LOGIN_MISSING),
    InvalidEmailError: (422, INVALID_EMAIL),
    WeakPasswordError: (422, WEAK_PASSWORD),
    StudentRoleMissingError: (500, STUDENT_ROLE_MISSING),
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # One pool for every Directus call, and one for fetching material. Both outlive the
    # request so a background job can still work after the response has been sent.
    async with (
        httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as pool,
        httpx.AsyncClient(timeout=FETCH_TIMEOUT, follow_redirects=True) as web,
    ):
        app.state.http = pool
        app.state.ingesters = default_ingesters(HttpxFetcher(http_client=web))
        yield


def create_app() -> FastAPI:
    app = FastAPI(title=TITLE, version=VERSION, lifespan=lifespan)
    app.include_router(router)
    app.add_exception_handler(DirectusUnavailableError, _unavailable)
    app.add_exception_handler(DirectusError, _rejected)
    app.add_exception_handler(StudentLoginError, _login_refused)
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


def _login_refused(request: Request, exc: Exception) -> JSONResponse:
    """The sentence is the one core wrote; the app only decides the status and the code."""
    if isinstance(exc, LoginRefusedError):
        return JSONResponse(status_code=exc.status, content=error_body(LOGIN_REFUSED, str(exc)))
    status, code = LOGIN_ERRORS.get(type(exc), (500, LOGIN_FAILED))
    return JSONResponse(status_code=status, content=error_body(code, str(exc)))


app = create_app()
