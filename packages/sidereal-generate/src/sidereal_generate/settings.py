from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 8000


class GenerateBackend(StrEnum):
    """Which implementation `default_generators()` builds."""

    CLAUDE = "claude"
    FAKE = "fake"


@dataclass(frozen=True, slots=True)
class GenerateSettings:
    model: str
    max_tokens: int
    backend: GenerateBackend


def generate_settings(env: Mapping[str, str] | None = None) -> GenerateSettings:
    source = os.environ if env is None else env
    raw = source.get("SIDEREAL_GENERATE_MAX_TOKENS")
    return GenerateSettings(
        model=source.get("SIDEREAL_GENERATE_MODEL") or DEFAULT_MODEL,
        max_tokens=int(raw) if raw else DEFAULT_MAX_TOKENS,
        backend=_backend(source.get("SIDEREAL_GENERATE_BACKEND")),
    )


def _backend(raw: str | None) -> GenerateBackend:
    if not raw:
        return GenerateBackend.CLAUDE
    try:
        return GenerateBackend(raw)
    except ValueError as exc:
        choices = ", ".join(backend.value for backend in GenerateBackend)
        raise ValueError(f"SIDEREAL_GENERATE_BACKEND must be one of: {choices}") from exc
