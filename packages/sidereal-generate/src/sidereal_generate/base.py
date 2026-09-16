from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel
from sidereal_core.models import Document

from sidereal_generate.models import (
    FeedbackOutput,
    GenerationRequest,
    HomeworkOutput,
    PaperExtraction,
    PlanOutput,
)
from sidereal_generate.usage import UsageTally


class GenerationError(Exception):
    """The model answered, but not with the artefact we asked for."""


class GenerationNotConfiguredError(GenerationError):
    """The backend has no key, so nothing was asked of it."""


class GenerationTruncatedError(GenerationError):
    """The answer hit the output budget. Reasoning spends it too, so it can buy nothing."""


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """The model's JSON schema with every property required.

    A strict schema has no optional properties, so a field the model may leave unset is
    asked for as null instead. `extra="forbid"` is what puts `additionalProperties: false`
    on each object. Every backend sends this one schema, so two can be compared.
    """
    schema: dict[str, Any] = model.model_json_schema()
    for definition in [schema, *schema.get("$defs", {}).values()]:
        properties = definition.get("properties")
        if isinstance(properties, dict):
            definition["required"] = list(properties)
    return schema


@runtime_checkable
class Generator[OutputT: BaseModel](Protocol):
    """One artefact kind. Swappable so two implementations can be compared."""

    @property
    def model(self) -> str: ...

    async def generate(
        self, request: GenerationRequest, *, usage: UsageTally | None = None
    ) -> OutputT: ...


class HomeworkGenerator(Generator[HomeworkOutput], Protocol): ...


class FeedbackGenerator(Generator[FeedbackOutput], Protocol): ...


class PlanGenerator(Generator[PlanOutput], Protocol): ...


@runtime_checkable
class PaperExtractor(Protocol):
    """A document's text read into a paper. It is transcription, not generation."""

    @property
    def model(self) -> str: ...

    async def extract(
        self,
        document: Document,
        mark_scheme: Document | None = None,
        *,
        usage: UsageTally | None = None,
    ) -> PaperExtraction: ...

    async def repair(
        self,
        extraction: PaperExtraction,
        diagnostics: str,
        *,
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        """The same structure with what the renderer refused corrected, and nothing else."""
        ...
