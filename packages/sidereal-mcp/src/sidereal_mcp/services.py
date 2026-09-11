from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sidereal_core.directus import DirectusClient
from sidereal_core.settings import directus_settings
from sidereal_generate.jobs import Generators, default_generators
from sidereal_ingest import Ingester, default_ingesters


@dataclass(frozen=True, slots=True)
class Services:
    directus: DirectusClient
    ingesters: Sequence[Ingester]
    generators: Generators


def build_services() -> Services:
    settings = directus_settings()
    return Services(
        directus=DirectusClient(settings.url, settings.token),
        ingesters=default_ingesters(),
        generators=default_generators(),
    )
