from __future__ import annotations

import json
import logging
import re
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

# What a backslash may introduce inside a JSON string. Anything else is the model's own.
ESCAPES = frozenset('"\\/bfnrtu')


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


# A JSON escape a model wrote into a text field instead of the character it stands for.
# `12\u00b0` arrives as six characters, and six characters is what the renderer prints.
# A lone surrogate stands for nothing on its own and is left as it was written.
_ESCAPED = re.compile(
    r"\\u(?:(?P<high>[dD][89abAB][0-9a-fA-F]{2})\\u(?P<low>[dD][c-fC-F][0-9a-fA-F]{2})"
    r"|(?P<single>(?![dD][89a-fA-F])[0-9a-fA-F]{4}))"
)


def unescaped(payload: object) -> object:
    """Every string in a model's answer with its JSON escapes turned back into characters."""
    match payload:
        case str():
            return _ESCAPED.sub(_character, payload)
        case dict():
            return {key: unescaped(item) for key, item in payload.items()}
        case list():
            return [unescaped(item) for item in payload]
        case _:
            return payload


def _character(match: re.Match[str]) -> str:
    single = match.group("single")
    if single is not None:
        return chr(int(single, 16))
    high = int(match.group("high"), 16) - 0xD800
    low = int(match.group("low"), 16) - 0xDC00
    return chr(0x10000 + (high << 10) + low)


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
        loaded = _loaded(value, owner, name)
        if loaded is None:
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


def _loaded(text: str, owner: type[BaseModel], name: str) -> dict[str, Any] | list[Any] | None:
    """The object behind a string that was meant to be one, or nothing to leave it alone.

    A string that does not open as JSON is the field's own value. One that does and will not
    parse is said so, and its invalid escapes are doubled once — `\\p` in a maths field is the
    backslash the model meant, and `json.loads` refuses it.
    """
    if not text.strip().startswith(("{", "[")):
        return None
    try:
        return _object(json.loads(text))
    except json.JSONDecodeError as exc:
        logger.warning("%s.%s reads as JSON but would not parse: %s", owner.__name__, name, exc)
    try:
        loaded = _object(json.loads(_escaped(text)))
    except json.JSONDecodeError:
        return None
    logger.warning("%s.%s parsed once its invalid escapes were doubled", owner.__name__, name)
    return loaded


def _object(loaded: object) -> dict[str, Any] | list[Any] | None:
    return loaded if isinstance(loaded, dict | list) else None


def _escaped(text: str) -> str:
    """Every backslash JSON does not know as an escape, doubled into a literal one."""
    out: list[str] = []
    index = 0
    while index < len(text):
        character = text[index]
        out.append(character)
        index += 1
        if character != "\\":
            continue
        following = text[index : index + 1]
        if following and following in ESCAPES:
            out.append(following)
            index += 1
            continue
        out.append("\\")
    return "".join(out)


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
