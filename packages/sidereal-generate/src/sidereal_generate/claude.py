"""The Anthropic-backed implementation of every generator."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

from anthropic import AsyncAnthropic
from anthropic.types import ToolParam, Usage
from pydantic import BaseModel, ValidationError
from sidereal_core.models import Document, HomeworkFormat

from sidereal_generate.base import (
    FeedbackGenerator,
    GenerationError,
    GenerationTruncatedError,
    HomeworkGenerator,
    PaperExtractor,
    PlanGenerator,
    strict_schema,
    unstringify,
)
from sidereal_generate.chunks import BATCH_QUESTIONS
from sidereal_generate.extraction import Ask, ChunkedPaperExtractor
from sidereal_generate.models import (
    FeedbackOutput,
    GenerationRequest,
    HomeworkOutput,
    PaperExtraction,
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
from sidereal_generate.settings import TRUNCATION_FACTOR, generate_settings
from sidereal_generate.usage import UsageTally

logger = logging.getLogger(__name__)

# Above this the SDK refuses a non-streaming request, and nothing here streams yet.
NON_STREAMING_MAX_TOKENS = 21_333
# Reasoning is spent from the same budget as the answer, so a cut-off answer can be empty.
CUT_OFF = "ran out of output budget"
# How much of a raw answer the DEBUG line carries.
DEBUG_PREFIX = 2000
NO_PAGES = (
    "Page images are read by the OpenRouter backend. Ask an administrator to set "
    "SIDEREAL_GENERATE_BACKEND=openrouter."
)


def _record(spent: Usage, usage: UsageTally | None) -> None:
    """Anthropic prices a call on the invoice, not the response, so no cost is recorded."""
    if usage is None:
        return
    usage.record(
        prompt_tokens=spent.input_tokens,
        completion_tokens=spent.output_tokens,
    )


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

    async def generate(
        self, request: GenerationRequest, *, usage: UsageTally | None = None
    ) -> OutputT:
        return self._validate(await self._asked(request, usage, self._max_tokens, retried=False))

    async def _asked(
        self, request: GenerationRequest, usage: UsageTally | None, budget: int, *, retried: bool
    ) -> object:
        """A cut-off answer buys nothing, so it is asked for once more with twice the budget."""
        response = await self._anthropic().messages.create(
            model=self._model,
            max_tokens=budget,
            system=self.system(request),
            messages=[{"role": "user", "content": render(request)}],
            tools=[self._tool()],
            tool_choice={"type": "tool", "name": self._tool_name},
        )
        _record(response.usage, usage)
        if response.stop_reason == "max_tokens":
            doubled = min(budget * TRUNCATION_FACTOR, NON_STREAMING_MAX_TOKENS)
            if retried or doubled <= budget:
                raise GenerationTruncatedError(
                    f"{self._model} {CUT_OFF} before finishing {self._tool_name}"
                )
            logger.warning(
                "%s was cut off writing %s; asking again with %d tokens",
                self._model,
                self._tool_name,
                doubled,
            )
            return await self._asked(request, usage, doubled, retried=True)
        for block in response.content:
            if block.type == "tool_use" and block.name == self._tool_name:
                return block.input
        raise GenerationError(f"{self._model} did not call {self._tool_name}")

    def _anthropic(self) -> AsyncAnthropic:
        # Built on first use: constructing it demands credentials, and importing this
        # module must not.
        if self._client is None:
            self._client = AsyncAnthropic()
        return self._client

    def _tool(self) -> ToolParam:
        return {
            "name": self._tool_name,
            "description": f"Return the {self._output_model.__name__} for this request.",
            "input_schema": strict_schema(self._output_model),
            "strict": True,
        }

    def _validate(self, payload: object) -> OutputT:
        try:
            return self._output_model.model_validate(unstringify(payload, self._output_model))
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
    return AnthropicGenerator(
        PlanOutput,
        PLAN_PROMPT,
        PLAN_TOOL,
        client=client,
        model=model,
        max_tokens=min(generate_settings().plan_max_tokens, NON_STREAMING_MAX_TOKENS),
    )


class _Caller:
    """The chunked extraction's seam, answered by one forced strict tool call each time."""

    def __init__(self, *, client: AsyncAnthropic | None, model: str, max_tokens: int) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    @property
    def model(self) -> str:
        return self._model

    async def ask(self, ask: Ask, *, usage: UsageTally | None = None) -> object:
        if ask.pages:
            raise GenerationError(NO_PAGES)
        tool: ToolParam = {
            "name": ask.tool,
            "description": ask.description,
            "input_schema": ask.schema,
            "strict": True,
        }
        response = await self._anthropic().messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=ask.system,
            messages=[{"role": "user", "content": ask.prompt}],
            tools=[tool],
            tool_choice={"type": "tool", "name": ask.tool},
        )
        _record(response.usage, usage)
        for block in response.content:
            if block.type == "tool_use" and block.name == ask.tool:
                # What the model actually sent, bounded: a long answer must not flood a log.
                logger.debug("%s answered: %s", ask.tool, json.dumps(block.input)[:DEBUG_PREFIX])
                return block.input
        raise GenerationError(f"{self._model} did not call {ask.tool}")

    def _anthropic(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic()
        return self._client


class AnthropicPaperExtractor(ChunkedPaperExtractor):
    """The paper read in chunks, each through a forced strict tool call of its own."""

    def __init__(
        self,
        *,
        client: AsyncAnthropic | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        size: int = BATCH_QUESTIONS,
    ) -> None:
        settings = generate_settings()
        super().__init__(
            _Caller(
                client=client,
                model=model or settings.model,
                max_tokens=max_tokens or min(settings.extract_max_tokens, NON_STREAMING_MAX_TOKENS),
            ),
            size=size,
        )

    async def extract(
        self,
        document: Document,
        *,
        pages: Sequence[bytes] = (),
        drawn: Sequence[int] = (),
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        if pages:
            raise GenerationError(NO_PAGES)
        return await super().extract(document, drawn=drawn, usage=usage)


def paper_extractor(
    *, client: AsyncAnthropic | None = None, model: str | None = None
) -> PaperExtractor:
    return AnthropicPaperExtractor(client=client, model=model)
