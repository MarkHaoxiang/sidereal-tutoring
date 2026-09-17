from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

DEFAULT_MODEL = "claude-sonnet-5"
# Reasoning is spent from the same budget as the answer, so neither is sized to the
# answer alone: a 36-page paper spent 20,000 without finishing. A cap bills nothing
# until it is used.
DEFAULT_MAX_TOKENS = 16000
# A term's plan is six weeks of sessions, and a plan that stops in week one is no plan.
DEFAULT_PLAN_MAX_TOKENS = 32000
DEFAULT_EXTRACT_MAX_TOKENS = 48000
# A cut-off answer is asked for once more with this much of the budget again.
TRUNCATION_FACTOR = 2
DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "anthropic/claude-sonnet-5"


class ReasoningEffort(StrEnum):
    """How much thinking a call is asked for. Transcription needs little of it."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GenerateBackend(StrEnum):
    """Which implementation `default_generators()` builds."""

    CLAUDE = "claude"
    OPENROUTER = "openrouter"
    FAKE = "fake"


@dataclass(frozen=True, slots=True)
class OpenRouterSettings:
    """`api_key` is kept out of the repr: a value object ends up in tracebacks and logs."""

    api_key: str | None = field(repr=False)
    base_url: str
    model: str


@dataclass(frozen=True, slots=True)
class GenerateSettings:
    model: str
    max_tokens: int
    # A plan covers a whole period in one answer, so it starts from more than the rest.
    plan_max_tokens: int
    # A whole exam paper, transcribed, is the longest answer anything here asks for.
    extract_max_tokens: int
    backend: GenerateBackend
    # Reading a paper is transcription, and thinking is spent from the answer's budget.
    extract_reasoning: ReasoningEffort
    openrouter: OpenRouterSettings

    @property
    def active_model(self) -> str:
        """The model the chosen backend will call. What `admin_health` reports."""
        if self.backend is GenerateBackend.OPENROUTER:
            return self.openrouter.model
        return self.model


def generate_settings(env: Mapping[str, str] | None = None) -> GenerateSettings:
    source = os.environ if env is None else env
    raw = source.get("SIDEREAL_GENERATE_MAX_TOKENS")
    plan = source.get("SIDEREAL_GENERATE_PLAN_MAX_TOKENS")
    extract = source.get("SIDEREAL_GENERATE_EXTRACT_MAX_TOKENS")
    return GenerateSettings(
        model=source.get("SIDEREAL_GENERATE_MODEL") or DEFAULT_MODEL,
        max_tokens=int(raw) if raw else DEFAULT_MAX_TOKENS,
        plan_max_tokens=int(plan) if plan else DEFAULT_PLAN_MAX_TOKENS,
        extract_max_tokens=int(extract) if extract else DEFAULT_EXTRACT_MAX_TOKENS,
        backend=_backend(source.get("SIDEREAL_GENERATE_BACKEND")),
        extract_reasoning=_effort(source.get("SIDEREAL_GENERATE_REASONING")),
        openrouter=OpenRouterSettings(
            api_key=source.get("OPENROUTER_API_KEY", "").strip() or None,
            base_url=_setting(source, "OPENROUTER_BASE_URL", DEFAULT_OPENROUTER_BASE_URL).rstrip(
                "/"
            ),
            model=_setting(source, "OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
        ),
    )


def _backend(raw: str | None) -> GenerateBackend:
    if not raw:
        return GenerateBackend.CLAUDE
    try:
        return GenerateBackend(raw)
    except ValueError as exc:
        choices = ", ".join(backend.value for backend in GenerateBackend)
        raise ValueError(f"SIDEREAL_GENERATE_BACKEND must be one of: {choices}") from exc


def _effort(raw: str | None) -> ReasoningEffort:
    if not raw:
        return ReasoningEffort.LOW
    try:
        return ReasoningEffort(raw)
    except ValueError as exc:
        choices = ", ".join(effort.value for effort in ReasoningEffort)
        raise ValueError(f"SIDEREAL_GENERATE_REASONING must be one of: {choices}") from exc


def _setting(env: Mapping[str, str], name: str, default: str) -> str:
    """An exported-but-empty variable is someone's unset value, not a setting."""
    return env.get(name, "").strip() or default
