"""The Anthropic-backed implementation of every generator."""

from __future__ import annotations

from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import ToolParam
from pydantic import BaseModel, ValidationError
from sidereal_core.models import HomeworkFormat

from sidereal_generate.base import (
    FeedbackGenerator,
    GenerationError,
    HomeworkGenerator,
    PlanGenerator,
)
from sidereal_generate.models import (
    FeedbackOutput,
    GenerationRequest,
    HomeworkOutput,
    PlanOutput,
)
from sidereal_generate.prompts import (
    FEEDBACK_PROMPT,
    FEEDBACK_TOOL,
    HOMEWORK_PROMPT,
    HOMEWORK_TOOL,
    HOMEWORK_TYPST_PROMPT,
    PLAN_PROMPT,
    PLAN_TOOL,
    render,
)
from sidereal_generate.settings import generate_settings


class AnthropicGenerator[OutputT: BaseModel]:
    """One artefact, returned through a strict tool call whose schema is the output model."""

    def __init__(
        self,
        output_model: type[OutputT],
        system_prompt: str,
        tool_name: str,
        *,
        client: AsyncAnthropic | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        settings = generate_settings()
        self._output_model = output_model
        self._system_prompt = system_prompt
        self._tool_name = tool_name
        self._client = client
        self._model = model or settings.model
        self._max_tokens = max_tokens or settings.max_tokens

    @property
    def model(self) -> str:
        return self._model

    def system(self, request: GenerationRequest) -> str:
        return self._system_prompt

    async def generate(self, request: GenerationRequest) -> OutputT:
        response = await self._anthropic().messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=self.system(request),
            messages=[{"role": "user", "content": render(request)}],
            tools=[self._tool()],
            tool_choice={"type": "tool", "name": self._tool_name},
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == self._tool_name:
                return self._validate(block.input)
        raise GenerationError(f"{self._model} did not call {self._tool_name}")

    def _anthropic(self) -> AsyncAnthropic:
        # Built on first use: constructing it demands credentials, and importing this
        # module must not.
        if self._client is None:
            self._client = AsyncAnthropic()
        return self._client

    def _tool(self) -> ToolParam:
        schema: dict[str, Any] = self._output_model.model_json_schema()
        return {
            "name": self._tool_name,
            "description": f"Return the {self._output_model.__name__} for this request.",
            "input_schema": schema,
            "strict": True,
        }

    def _validate(self, payload: object) -> OutputT:
        try:
            return self._output_model.model_validate(payload)
        except ValidationError as exc:
            raise GenerationError(f"{self._tool_name} returned an unusable payload: {exc}") from exc


class AnthropicHomeworkGenerator(AnthropicGenerator[HomeworkOutput]):
    """Homework, in the format the request asks for: markdown, or a Typst body."""

    def system(self, request: GenerationRequest) -> str:
        return HOMEWORK_TYPST_PROMPT if request.format is HomeworkFormat.TYPST else HOMEWORK_PROMPT


def homework_generator(
    *, client: AsyncAnthropic | None = None, model: str | None = None
) -> HomeworkGenerator:
    return AnthropicHomeworkGenerator(
        HomeworkOutput, HOMEWORK_PROMPT, HOMEWORK_TOOL, client=client, model=model
    )


def feedback_generator(
    *, client: AsyncAnthropic | None = None, model: str | None = None
) -> FeedbackGenerator:
    return AnthropicGenerator(
        FeedbackOutput, FEEDBACK_PROMPT, FEEDBACK_TOOL, client=client, model=model
    )


def plan_generator(
    *, client: AsyncAnthropic | None = None, model: str | None = None
) -> PlanGenerator:
    return AnthropicGenerator(PlanOutput, PLAN_PROMPT, PLAN_TOOL, client=client, model=model)
