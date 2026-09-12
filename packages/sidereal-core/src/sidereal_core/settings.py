from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_DIRECTUS_URL = "http://localhost:8055"
DEFAULT_TYPESET_URL = "http://127.0.0.1:50052"


@dataclass(frozen=True, slots=True)
class DirectusSettings:
    url: str
    token: str | None


@dataclass(frozen=True, slots=True)
class TypesetSettings:
    url: str


def directus_settings(env: Mapping[str, str] | None = None) -> DirectusSettings:
    source = os.environ if env is None else env
    return DirectusSettings(
        url=source.get("SIDEREAL_DIRECTUS_URL", DEFAULT_DIRECTUS_URL).rstrip("/"),
        token=source.get("SIDEREAL_DIRECTUS_TOKEN") or None,
    )


def typeset_settings(env: Mapping[str, str] | None = None) -> TypesetSettings:
    source = os.environ if env is None else env
    return TypesetSettings(url=source.get("SIDEREAL_TYPESET_URL", DEFAULT_TYPESET_URL).rstrip("/"))
