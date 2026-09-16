"""Request-scoped dependencies. Tests override these rather than the routes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, cast

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sidereal_core.directus import DirectusClient, DirectusError, DirectusUnavailableError
from sidereal_core.logins import CallerRole, Identity, identify
from sidereal_core.models import DirectusUser
from sidereal_core.settings import directus_settings
from sidereal_core.typeset import TypesetClient
from sidereal_generate.jobs import Generators
from sidereal_ingest.base import Ingester

from sidereal_app.api.errors import (
    ADMIN_ONLY,
    BAD_CREDENTIALS,
    DIRECTUS_UNAVAILABLE,
    NO_CREDENTIALS,
    TUTOR_ONLY,
    detail,
)

bearer = HTTPBearer(auto_error=False)


def get_http_client(request: Request) -> httpx.AsyncClient:
    """The app's one connection pool, opened by the lifespan and closed after it."""
    return cast("httpx.AsyncClient", request.app.state.http)


def get_ingesters(request: Request) -> Sequence[Ingester]:
    """Built once by the lifespan: the web fetcher's rate limit is per process, not per request."""
    return cast("Sequence[Ingester]", request.app.state.ingesters)


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


def get_generators(request: Request) -> Generators:
    """Built once by the lifespan: the backend's client and its pool outlive the request."""
    return cast("Generators", request.app.state.generators)


def get_typeset(request: Request) -> TypesetClient:
    """One client for the process, opened by the lifespan: it outlives the request."""
    return cast("TypesetClient", request.app.state.typeset)


async def require_tutor(
    user: Annotated[DirectusUser, Depends(get_current_user)],
    client: Annotated[DirectusClient, Depends(get_directus_client)],
) -> Identity:
    """Authoring is the tutor's, and an admin counts as one. A student is refused."""
    identity = await identify(client, user)
    if identity.role is CallerRole.STUDENT:
        raise HTTPException(
            status_code=403,
            detail=detail(TUTOR_ONLY, "Only a tutor can do this."),
        )
    return identity


async def require_admin(
    user: Annotated[DirectusUser, Depends(get_current_user)],
    client: Annotated[DirectusClient, Depends(get_directus_client)],
) -> Identity:
    """Running the practice is the admin's. A tutor and a student are both refused."""
    identity = await identify(client, user)
    if identity.role is not CallerRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail=detail(ADMIN_ONLY, "Only an administrator can do this."),
        )
    return identity


CurrentUser = Annotated[DirectusUser, Depends(get_current_user)]
Tutor = Annotated[Identity, Depends(require_tutor)]
Admin = Annotated[Identity, Depends(require_admin)]
IngesterSet = Annotated[Sequence[Ingester], Depends(get_ingesters)]
Directus = Annotated[DirectusClient, Depends(get_directus_client)]
GeneratorSet = Annotated[Generators, Depends(get_generators)]
Typeset = Annotated[TypesetClient, Depends(get_typeset)]
