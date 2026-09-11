"""A generator for tests: no client, no network, and it records what it was asked."""

from __future__ import annotations

from pydantic import BaseModel

from sidereal_generate.models import GenerationRequest

FAKE_MODEL = "fake"


class FakeGenerator[OutputT: BaseModel]:
    def __init__(self, output: OutputT, *, model: str = FAKE_MODEL) -> None:
        self.output = output
        self.requests: list[GenerationRequest] = []
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, request: GenerationRequest) -> OutputT:
        self.requests.append(request)
        return self.output


class FailingGenerator[OutputT: BaseModel]:
    def __init__(self, error: Exception, *, model: str = FAKE_MODEL) -> None:
        self.error = error
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, request: GenerationRequest) -> OutputT:
        raise self.error
