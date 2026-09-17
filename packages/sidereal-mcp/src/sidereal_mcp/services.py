from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import httpx
from sidereal_core.directus import DEFAULT_TIMEOUT, DirectusClient
from sidereal_core.settings import directus_settings, typeset_settings
from sidereal_core.typeset import TypesetClient
from sidereal_generate.jobs import Generators, default_generators
from sidereal_generate.vision import default_transcriber
from sidereal_ingest import Ingester, ScanIngester, default_ingesters


@dataclass(frozen=True, slots=True)
class Services:
    directus: DirectusClient
    ingesters: Sequence[Ingester]
    scanner: ScanIngester
    generators: Generators
    typeset: TypesetClient


ServicesFor = Callable[[str], Services]
"""A caller's Directus token becomes the `Services` that act as them."""


def build_services() -> Services:
    """The stdio server's one `Services`, on the environment's token."""
    settings = directus_settings()
    return Services(
        directus=DirectusClient(settings.url, settings.token),
        ingesters=default_ingesters(),
        scanner=ScanIngester(default_transcriber()),
        generators=default_generators(),
        typeset=TypesetClient(typeset_settings().url),
    )


@dataclass(frozen=True, slots=True)
class ServicePool:
    """The per-process half: one connection pool, one fetch rate limit, one typeset client.

    `for_token` is the per-request half, and holds no ambient authority of its own.
    """

    directus_url: str
    http: httpx.AsyncClient
    ingesters: Sequence[Ingester]
    scanner: ScanIngester
    generators: Generators
    typeset: TypesetClient

    def for_token(self, token: str) -> Services:
        return Services(
            directus=DirectusClient(self.directus_url, token, http_client=self.http),
            ingesters=self.ingesters,
            scanner=self.scanner,
            generators=self.generators,
            typeset=self.typeset,
        )

    async def aclose(self) -> None:
        await self.http.aclose()
        await self.typeset.aclose()


def build_pool() -> ServicePool:
    return ServicePool(
        directus_url=directus_settings().url,
        http=httpx.AsyncClient(timeout=DEFAULT_TIMEOUT),
        ingesters=default_ingesters(),
        scanner=ScanIngester(default_transcriber()),
        generators=default_generators(),
        typeset=TypesetClient(typeset_settings().url),
    )
