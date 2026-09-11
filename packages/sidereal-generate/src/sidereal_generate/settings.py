from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 8000


@dataclass(frozen=True, slots=True)
class GenerateSettings:
    model: str
    max_tokens: int


def generate_settings(env: Mapping[str, str] | None = None) -> GenerateSettings:
    source = os.environ if env is None else env
    raw = source.get("SIDEREAL_GENERATE_MAX_TOKENS")
    return GenerateSettings(
        model=source.get("SIDEREAL_GENERATE_MODEL") or DEFAULT_MODEL,
        max_tokens=int(raw) if raw else DEFAULT_MAX_TOKENS,
    )
