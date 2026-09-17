"""The Anthropic-backed implementation of every generator."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from anthropic import AsyncAnthropic
from anthropic.types import ToolParam, Usage
from pydantic import BaseModel, ValidationError
from sidereal_core.canonical import CanonicalPaper
from sidereal_core.models import Document, HomeworkFormat

from sidereal_generate.base import (
    FeedbackGenerator,
    GenerationError,
    HomeworkGenerator,
    PaperExtractor,
    PlanGenerator,
    strict_schema,
    unstringify,
)
from sidereal_generate.models import (
    FeedbackOutput,
    GenerationRequest,
    HomeworkOutput,
    MarkSchemeExtraction,
    PaperExtraction,
    PlanOutput,
)
from sidereal_generate.prompts import (
    FEEDBACK_PROMPT,
    FEEDBACK_TOOL,
    HOMEWORK_PROMPT,
    HOMEWORK_TOOL,
    HOMEWORK_TYPST_PROMPT,
    MARK_SCHEME_PROMPT,
    MARK_SCHEME_REPAIR,
    MARK_SCHEME_RETRY,
    MARK_SCHEME_TOOL,
    PAPER_PROMPT,
    PAPER_REPAIR,
    PAPER_RETRY,
    PAPER_TOOL,
    PLAN_PROMPT,
    PLAN_TOOL,
    render,
    render_document,
    render_mark_scheme,
)
from sidereal_generate.settings import generate_settings
from sidereal_generate.usage import UsageTally

logger = logging.getLogger(__name__)

# Above this the SDK refuses a non-streaming request, and nothing here streams yet.
NON_STREAMING_MAX_TOKENS = 21_333
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
        response = await self._anthropic().messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=self.system(request),
            messages=[{"role": "user", "content": render(request)}],
            tools=[self._tool()],
            tool_choice={"type": "tool", "name": self._tool_name},
        )
        _record(response.usage, usage)
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
    return AnthropicGenerator(PlanOutput, PLAN_PROMPT, PLAN_TOOL, client=client, model=model)


@dataclass(frozen=True, slots=True)
class _Call:
    """What one extraction call is named, and what an unusable answer to it is called."""

    tool: str
    description: str
    noun: str


_PAPER = _Call(PAPER_TOOL, "Return the paper as structure.", "paper")
_MARK_SCHEME = _Call(MARK_SCHEME_TOOL, "Return the mark scheme as structure.", "mark scheme")


def _validated[M: BaseModel](model: type[M], call: _Call, payload: object) -> M:
    try:
        return model.model_validate(unstringify(payload, model))
    except ValidationError as exc:
        raise GenerationError(f"{call.tool} returned an unusable {call.noun}: {exc}") from exc


class AnthropicPaperExtractor:
    """A paper, then its mark scheme, each through a forced strict tool call of its own.

    A payload the canonical models refuse is asked for once more with the errors appended;
    a second refusal is a `GenerationError`, never a half-read paper.
    """

    def __init__(
        self,
        *,
        client: AsyncAnthropic | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        settings = generate_settings()
        self._client = client
        self._model = model or settings.model
        self._max_tokens = max_tokens or min(settings.extract_max_tokens, NON_STREAMING_MAX_TOKENS)

    @property
    def model(self) -> str:
        return self._model

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
        return await self._extracted(
            PaperExtraction, _PAPER, PAPER_PROMPT, render_document(document), PAPER_RETRY, usage
        )

    async def extract_mark_scheme(
        self,
        document: Document,
        paper: CanonicalPaper,
        *,
        usage: UsageTally | None = None,
    ) -> MarkSchemeExtraction:
        return await self._extracted(
            MarkSchemeExtraction,
            _MARK_SCHEME,
            MARK_SCHEME_PROMPT,
            render_mark_scheme(document, paper),
            MARK_SCHEME_RETRY,
            usage,
        )

    async def repair(
        self,
        extraction: PaperExtraction,
        diagnostics: str,
        *,
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        return await self._repaired(
            PaperExtraction, _PAPER, PAPER_REPAIR, extraction, diagnostics, usage
        )

    async def repair_mark_scheme(
        self,
        extraction: MarkSchemeExtraction,
        diagnostics: str,
        *,
        usage: UsageTally | None = None,
    ) -> MarkSchemeExtraction:
        return await self._repaired(
            MarkSchemeExtraction, _MARK_SCHEME, MARK_SCHEME_REPAIR, extraction, diagnostics, usage
        )

    async def _extracted[M: BaseModel](
        self,
        model: type[M],
        call: _Call,
        system: str,
        prompt: str,
        retry: str,
        usage: UsageTally | None,
    ) -> M:
        payload = await self._ask(model, call, system, prompt, usage)
        try:
            return model.model_validate(unstringify(payload, model))
        except ValidationError as first:
            logger.warning(
                "%s returned an unusable %s, asking once more: %s", call.tool, call.noun, first
            )
            payload = await self._ask(model, call, system, f"{prompt}\n\n{retry}\n{first}", usage)
        return _validated(model, call, payload)

    async def _repaired[M: BaseModel](
        self,
        model: type[M],
        call: _Call,
        system: str,
        extraction: M,
        diagnostics: str,
        usage: UsageTally | None,
    ) -> M:
        prompt = f"{extraction.model_dump_json()}\n\n{diagnostics}"
        return _validated(model, call, await self._ask(model, call, system, prompt, usage))

    async def _ask(
        self,
        model: type[BaseModel],
        call: _Call,
        system: str,
        prompt: str,
        usage: UsageTally | None = None,
    ) -> object:
        tool: ToolParam = {
            "name": call.tool,
            "description": call.description,
            "input_schema": strict_schema(model),
            "strict": True,
        }
        response = await self._anthropic().messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            tools=[tool],
            tool_choice={"type": "tool", "name": call.tool},
        )
        _record(response.usage, usage)
        for block in response.content:
            if block.type == "tool_use" and block.name == call.tool:
                return block.input
        raise GenerationError(f"{self._model} did not call {call.tool}")

    def _anthropic(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic()
        return self._client


def paper_extractor(
    *, client: AsyncAnthropic | None = None, model: str | None = None
) -> PaperExtractor:
    return AnthropicPaperExtractor(client=client, model=model)
