from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from types import NoneType
from typing import Any, Protocol, get_args, get_origin, runtime_checkable

from pydantic import BaseModel
from sidereal_core.canonical import CanonicalPaper
from sidereal_core.models import Document

from sidereal_generate.models import (
    FeedbackOutput,
    GenerationRequest,
    HomeworkOutput,
    MarkSchemeExtraction,
    PaperExtraction,
    PlanOutput,
)
from sidereal_generate.usage import UsageTally

logger = logging.getLogger(__name__)


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


def unstringify(payload: object, model: type[BaseModel]) -> object:
    """An object field the model sent as JSON text, parsed back into the object.

    A string that is not JSON, or that is JSON but not an object or an array, is left as it
    stands for validation to refuse. A field that legitimately holds a string is untouched.
    """
    if not isinstance(payload, dict):
        return payload
    fixed = dict(payload)
    for name, field in model.model_fields.items():
        nested = _nested(field.annotation)
        if nested is None or name not in fixed:
            continue
        fixed[name] = _parsed(fixed[name], nested, model, name)
    return fixed


def _parsed(value: object, nested: type[BaseModel], owner: type[BaseModel], name: str) -> object:
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
        except json.JSONDecodeError:
            return value
        if not isinstance(loaded, dict | list):
            return value
        logger.warning(
            "%s stringified %s: the %s arrived as JSON text and was parsed back",
            owner.__name__,
            name,
            nested.__name__,
        )
        value = loaded
    if isinstance(value, list):
        return [unstringify(item, nested) for item in value]
    return unstringify(value, nested)


def _nested(annotation: object) -> type[BaseModel] | None:
    """The one pydantic model behind a field's annotation, through optionals and sequences."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    if get_origin(annotation) is None:
        return None
    found = {
        model
        for argument in get_args(annotation)
        if argument not in (NoneType, Ellipsis)
        for model in (_nested(argument),)
        if model is not None
    }
    return found.pop() if len(found) == 1 else None


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
        *,
        pages: Sequence[bytes] = (),
        drawn: Sequence[int] = (),
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        """`drawn` is the 1-based numbers of the `pages` carrying drawn content."""
        ...

    async def extract_mark_scheme(
        self,
        document: Document,
        paper: CanonicalPaper,
        *,
        usage: UsageTally | None = None,
    ) -> MarkSchemeExtraction:
        """The scheme read under the paper's own numbers and labels, so the two line up."""
        ...

    async def repair(
        self,
        extraction: PaperExtraction,
        diagnostics: str,
        *,
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        """The same structure with what the renderer refused corrected, and nothing else."""
        ...

    async def repair_mark_scheme(
        self,
        extraction: MarkSchemeExtraction,
        diagnostics: str,
        *,
        usage: UsageTally | None = None,
    ) -> MarkSchemeExtraction: ...
