from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from sidereal_generate.models import (
    FeedbackOutput,
    GenerationRequest,
    HomeworkOutput,
    PlanOutput,
)


class GenerationError(Exception):
    """The model answered, but not with the artefact we asked for."""


@runtime_checkable
class Generator[OutputT: BaseModel](Protocol):
    """One artefact kind. Swappable so two implementations can be compared."""

    @property
    def model(self) -> str: ...

    async def generate(self, request: GenerationRequest) -> OutputT: ...


class HomeworkGenerator(Generator[HomeworkOutput], Protocol): ...


class FeedbackGenerator(Generator[FeedbackOutput], Protocol): ...


class PlanGenerator(Generator[PlanOutput], Protocol): ...
