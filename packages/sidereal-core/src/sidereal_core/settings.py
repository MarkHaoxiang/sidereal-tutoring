from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_DIRECTUS_URL = "http://localhost:8055"


@dataclass(frozen=True, slots=True)
class DirectusSettings:
    url: str
    token: str | None


def directus_settings(env: Mapping[str, str] | None = None) -> DirectusSettings:
    source = os.environ if env is None else env
    return DirectusSettings(
        url=source.get("SIDEREAL_DIRECTUS_URL", DEFAULT_DIRECTUS_URL).rstrip("/"),
        token=source.get("SIDEREAL_DIRECTUS_TOKEN") or None,
    )
