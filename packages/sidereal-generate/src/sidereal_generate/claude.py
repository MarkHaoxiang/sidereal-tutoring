"""The Anthropic-backed implementation of every generator."""

from __future__ import annotations

from anthropic import AsyncAnthropic
from anthropic.types import ToolParam, Usage
from pydantic import BaseModel, ValidationError
from sidereal_core.models import Document, HomeworkFormat

from sidereal_generate.base import (
    FeedbackGenerator,
    GenerationError,
    HomeworkGenerator,
    PaperExtractor,
    PlanGenerator,
    strict_schema,
)
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
    PAPER_PROMPT,
    PAPER_REPAIR,
    PAPER_RETRY,
    PAPER_TOOL,
    PLAN_PROMPT,
    PLAN_TOOL,
    render,
    render_document,
)
from sidereal_generate.settings import generate_settings
from sidereal_generate.usage import UsageTally

# Above this the SDK refuses a non-streaming request, and nothing here streams yet.
NON_STREAMING_MAX_TOKENS = 21_333


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


class AnthropicPaperExtractor:
    """A paper read out of one document, through the same forced strict tool call.

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
        mark_scheme: Document | None = None,
        *,
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        prompt = render_document(document, mark_scheme)
        payload = await self._call(PAPER_PROMPT, prompt, usage)
        try:
            return PaperExtraction.model_validate(payload)
        except ValidationError as first:
            payload = await self._call(PAPER_PROMPT, f"{prompt}\n\n{PAPER_RETRY}\n{first}", usage)
        try:
            return PaperExtraction.model_validate(payload)
        except ValidationError as exc:
            raise GenerationError(f"{PAPER_TOOL} returned an unusable paper: {exc}") from exc

    async def repair(
        self,
        extraction: PaperExtraction,
        diagnostics: str,
        *,
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        payload = await self._call(
            PAPER_REPAIR, f"{extraction.model_dump_json()}\n\n{diagnostics}", usage
        )
        try:
            return PaperExtraction.model_validate(payload)
        except ValidationError as exc:
            raise GenerationError(f"{PAPER_TOOL} returned an unusable paper: {exc}") from exc

    async def _call(self, system: str, prompt: str, usage: UsageTally | None = None) -> object:
        response = await self._anthropic().messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            tools=[self._tool()],
            tool_choice={"type": "tool", "name": PAPER_TOOL},
        )
        _record(response.usage, usage)
        for block in response.content:
            if block.type == "tool_use" and block.name == PAPER_TOOL:
                return block.input
        raise GenerationError(f"{self._model} did not call {PAPER_TOOL}")

    def _anthropic(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic()
        return self._client

    def _tool(self) -> ToolParam:
        return {
            "name": PAPER_TOOL,
            "description": "Return the paper, and its mark scheme when the source carries one.",
            "input_schema": strict_schema(PaperExtraction),
            "strict": True,
        }


def paper_extractor(
    *, client: AsyncAnthropic | None = None, model: str | None = None
) -> PaperExtractor:
    return AnthropicPaperExtractor(client=client, model=model)
