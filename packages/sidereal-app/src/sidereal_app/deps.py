"""Request-scoped dependencies. Tests override these rather than the routes."""

from __future__ import annotations

from typing import Annotated, cast

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sidereal_core.directus import DirectusClient, DirectusError, DirectusUnavailableError
from sidereal_core.models import DirectusUser
from sidereal_core.settings import directus_settings
from sidereal_generate.jobs import Generators, default_generators

from sidereal_app.api.errors import (
    BAD_CREDENTIALS,
    DIRECTUS_UNAVAILABLE,
    NO_CREDENTIALS,
    detail,
)

bearer = HTTPBearer(auto_error=False)


def get_http_client(request: Request) -> httpx.AsyncClient:
    """The app's one connection pool, opened by the lifespan and closed after it."""
    return cast("httpx.AsyncClient", request.app.state.http)


def get_directus_client(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    pool: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> DirectusClient:
    """A client bound to the caller's own Directus token: the app holds no ambient authority."""
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail=detail(NO_CREDENTIALS, "Send a Directus token as `Authorization: Bearer`."),
        )
    return DirectusClient(directus_settings().url, credentials.credentials, http_client=pool)


async def get_current_user(
    client: Annotated[DirectusClient, Depends(get_directus_client)],
) -> DirectusUser:
    try:
        return await client.me()
    except DirectusUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=detail(DIRECTUS_UNAVAILABLE, "Directus is not reachable; try again shortly."),
        ) from exc
    except DirectusError as exc:
        raise HTTPException(
            status_code=401, detail=detail(BAD_CREDENTIALS, "Directus rejected this token.")
        ) from exc


def get_generators() -> Generators:
    return default_generators()


CurrentUser = Annotated[DirectusUser, Depends(get_current_user)]
Directus = Annotated[DirectusClient, Depends(get_directus_client)]
GeneratorSet = Annotated[Generators, Depends(get_generators)]
