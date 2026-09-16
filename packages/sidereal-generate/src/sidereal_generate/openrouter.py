"""The OpenRouter-backed implementation of every generator."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx2
from openai import AsyncOpenAI, BadRequestError, NotFoundError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from pydantic import BaseModel, ValidationError
from sidereal_core.models import Document, HomeworkFormat

from sidereal_generate.base import (
    FeedbackGenerator,
    GenerationError,
    GenerationNotConfiguredError,
    GenerationTruncatedError,
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
from sidereal_generate.settings import ReasoningEffort, generate_settings
from sidereal_generate.usage import UsageTally

logger = logging.getLogger(__name__)

# OpenRouter's app attribution: the URL is the identifier, the title is what it is called.
REFERER = "https://github.com/MarkHaoxiang/sidereal-tutoring"
TITLE = "sidereal-tutoring"
# A whole paper is a long answer, and this is well above the Directus and typeset timeouts.
REQUEST_TIMEOUT = 900.0
NO_KEY = "OPENROUTER_API_KEY is not set, so the OpenRouter backend cannot be called."
# Reasoning tokens are spent from the same budget as the answer, so a budget that is merely
# enough for the answer can be gone before a single character of it is written.
CUT_OFF = "ran out of output budget"
# Ask the gateway to price every call, so a job can file what it cost.
PRICED: dict[str, Any] = {"usage": {"include": True}}


class OpenRouterCall:
    """One structured answer: `response_format` first, a forced tool call when refused.

    A model whose provider has no strict `json_schema` mode answers 400 or 404; the same
    schema then goes out as a forced function call, and this instance stops asking for
    `response_format` again.
    """

    def __init__(
        self,
        *,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        http_client: httpx2.AsyncClient | None = None,
        reasoning: ReasoningEffort | None = None,
    ) -> None:
        settings = generate_settings()
        self._client = client
        self._settings = settings.openrouter
        self._model = model or settings.openrouter.model
        self._max_tokens = max_tokens or settings.max_tokens
        self._http_client = http_client
        self._reasoning = reasoning
        self._structured = True

    @property
    def model(self) -> str:
        return self._model

    def _extra(self) -> dict[str, Any]:
        """Price every call, and say how much thinking it is worth."""
        if self._reasoning is None:
            return PRICED
        return {**PRICED, "reasoning": {"effort": self._reasoning.value}}

    async def payload(
        self,
        *,
        system: str,
        prompt: str,
        name: str,
        description: str,
        schema: dict[str, Any],
        usage: UsageTally | None = None,
    ) -> object:
        if self._structured:
            try:
                return await self._json_schema(system, prompt, name, schema, usage)
            except (BadRequestError, NotFoundError) as exc:
                logger.warning(
                    "%s refused a json_schema response, falling back to a tool call: %s",
                    self._model,
                    exc,
                )
                self._structured = False
        return await self._tool_call(system, prompt, name, description, schema, usage)

    async def _json_schema(
        self,
        system: str,
        prompt: str,
        name: str,
        schema: dict[str, Any],
        usage: UsageTally | None = None,
    ) -> object:
        completion = await self._openai().chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            timeout=REQUEST_TIMEOUT,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": name, "strict": True, "schema": schema},
            },
            extra_body=self._extra(),
        )
        message = self._answer(completion, name, usage)
        if message.content:
            return self._decode(message.content, name)
        # A provider may answer a `json_schema` request with the tool call it translated
        # the schema into.
        return self._decode(self._arguments(message, name), name)

    async def _tool_call(
        self,
        system: str,
        prompt: str,
        name: str,
        description: str,
        schema: dict[str, Any],
        usage: UsageTally | None = None,
    ) -> object:
        completion = await self._openai().chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            timeout=REQUEST_TIMEOUT,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": description,
                        "parameters": schema,
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": name}},
            extra_body=self._extra(),
        )
        message = self._answer(completion, name, usage)
        arguments = self._arguments(message, name)
        if arguments is None:
            raise GenerationError(f"{self._model} did not call {name}")
        return self._decode(arguments, name)

    def _answer(
        self, completion: ChatCompletion, name: str, usage: UsageTally | None = None
    ) -> ChatCompletionMessage:
        """The message, once it is known to be a whole answer rather than a stub."""
        choice = None if not completion.choices else completion.choices[0]
        # A call that failed still spent tokens, so this is recorded before any raise.
        self._record(completion, usage)
        # A paid call leaves one line saying what it cost, at the level a server runs at.
        logger.info(
            "%s answered %s: finish_reason=%s usage=%s",
            self._model,
            name,
            None if choice is None else choice.finish_reason,
            None if completion.usage is None else completion.usage.model_dump(),
        )
        if choice is None:
            raise GenerationError(f"{self._model} answered {name} with no choices")
        logger.debug(
            "%s message: content=%s refusal=%s tool_calls=%s",
            name,
            0 if choice.message.content is None else len(choice.message.content),
            choice.message.refusal,
            [call.type for call in choice.message.tool_calls or ()],
        )
        if choice.finish_reason == "length":
            # Nothing usable survives a cut-off, so this never reaches validation.
            raise GenerationTruncatedError(f"{self._model} {CUT_OFF} before finishing {name}")
        if choice.message.refusal:
            raise GenerationError(f"{self._model} refused {name}: {choice.message.refusal}")
        return choice.message

    def _record(self, completion: ChatCompletion, usage: UsageTally | None) -> None:
        if usage is None or completion.usage is None:
            return
        spent = completion.usage
        details = spent.completion_tokens_details
        # OpenRouter prices the call on the usage object; another gateway may not.
        cost = (spent.model_extra or {}).get("cost")
        usage.record(
            prompt_tokens=spent.prompt_tokens,
            completion_tokens=spent.completion_tokens,
            reasoning_tokens=0 if details is None else (details.reasoning_tokens or 0),
            total_tokens=spent.total_tokens,
            cost_usd=float(cost) if isinstance(cost, int | float) else None,
            effort=None if self._reasoning is None else self._reasoning.value,
        )

    def _arguments(self, message: ChatCompletionMessage, name: str) -> str | None:
        for call in message.tool_calls or ():
            if call.type == "function" and call.function.name == name:
                return call.function.arguments
        return None

    def _decode(self, raw: str | None, name: str) -> object:
        if not raw:
            raise GenerationError(f"{self._model} returned nothing for {name}")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GenerationError(f"{name} returned a payload that is not JSON: {exc}") from exc

    def _openai(self) -> AsyncOpenAI:
        # Built on first use: constructing it demands a key, and importing this module
        # must not.
        if self._client is None:
            if self._settings.api_key is None:
                raise GenerationNotConfiguredError(NO_KEY)
            self._client = AsyncOpenAI(
                api_key=self._settings.api_key,
                base_url=self._settings.base_url,
                default_headers={"HTTP-Referer": REFERER, "X-Title": TITLE},
                http_client=self._http_client,
            )
        return self._client


class OpenRouterGenerator[OutputT: BaseModel]:
    """One artefact, returned against the output model's strict schema."""

    def __init__(
        self,
        output_model: type[OutputT],
        system_prompt: str,
        tool_name: str,
        *,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._output_model = output_model
        self._system_prompt = system_prompt
        self._tool_name = tool_name
        self._call = OpenRouterCall(
            client=client, model=model, max_tokens=max_tokens, http_client=http_client
        )

    @property
    def model(self) -> str:
        return self._call.model

    def system(self, request: GenerationRequest) -> str:
        return self._system_prompt

    async def generate(
        self, request: GenerationRequest, *, usage: UsageTally | None = None
    ) -> OutputT:
        payload = await self._call.payload(
            system=self.system(request),
            prompt=render(request),
            name=self._tool_name,
            description=f"Return the {self._output_model.__name__} for this request.",
            schema=strict_schema(self._output_model),
            usage=usage,
        )
        try:
            return self._output_model.model_validate(payload)
        except ValidationError as exc:
            raise GenerationError(f"{self._tool_name} returned an unusable payload: {exc}") from exc


class OpenRouterHomeworkGenerator(OpenRouterGenerator[HomeworkOutput]):
    """Homework, in the format the request asks for: markdown, or a Typst body."""

    def system(self, request: GenerationRequest) -> str:
        return HOMEWORK_TYPST_PROMPT if request.format is HomeworkFormat.TYPST else HOMEWORK_PROMPT


def homework_generator(
    *,
    client: AsyncOpenAI | None = None,
    model: str | None = None,
    http_client: httpx2.AsyncClient | None = None,
) -> HomeworkGenerator:
    return OpenRouterHomeworkGenerator(
        HomeworkOutput,
        HOMEWORK_PROMPT,
        HOMEWORK_TOOL,
        client=client,
        model=model,
        http_client=http_client,
    )


def feedback_generator(
    *,
    client: AsyncOpenAI | None = None,
    model: str | None = None,
    http_client: httpx2.AsyncClient | None = None,
) -> FeedbackGenerator:
    return OpenRouterGenerator(
        FeedbackOutput,
        FEEDBACK_PROMPT,
        FEEDBACK_TOOL,
        client=client,
        model=model,
        http_client=http_client,
    )


def plan_generator(
    *,
    client: AsyncOpenAI | None = None,
    model: str | None = None,
    http_client: httpx2.AsyncClient | None = None,
) -> PlanGenerator:
    return OpenRouterGenerator(
        PlanOutput, PLAN_PROMPT, PLAN_TOOL, client=client, model=model, http_client=http_client
    )


class OpenRouterPaperExtractor:
    """A paper read out of one document, against the same strict schema.

    A payload the canonical models refuse is asked for once more with the errors appended;
    a second refusal is a `GenerationError`, never a half-read paper.
    """

    def __init__(
        self,
        *,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        http_client: httpx2.AsyncClient | None = None,
        reasoning: ReasoningEffort | None = None,
    ) -> None:
        settings = generate_settings()
        self._call = OpenRouterCall(
            client=client,
            model=model,
            max_tokens=max_tokens or settings.extract_max_tokens,
            http_client=http_client,
            reasoning=reasoning or settings.extract_reasoning,
        )

    @property
    def model(self) -> str:
        return self._call.model

    async def extract(
        self,
        document: Document,
        mark_scheme: Document | None = None,
        *,
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        prompt = render_document(document, mark_scheme)
        payload = await self._paper(PAPER_PROMPT, prompt, usage)
        try:
            return PaperExtraction.model_validate(payload)
        except ValidationError as first:
            payload = await self._paper(PAPER_PROMPT, f"{prompt}\n\n{PAPER_RETRY}\n{first}", usage)
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
        prompt = f"{extraction.model_dump_json()}\n\n{diagnostics}"
        payload = await self._paper(PAPER_REPAIR, prompt, usage)
        try:
            return PaperExtraction.model_validate(payload)
        except ValidationError as exc:
            raise GenerationError(f"{PAPER_TOOL} returned an unusable paper: {exc}") from exc

    async def _paper(self, system: str, prompt: str, usage: UsageTally | None) -> object:
        return await self._call.payload(
            system=system,
            prompt=prompt,
            name=PAPER_TOOL,
            description="Return the paper, and its mark scheme when the source carries one.",
            schema=strict_schema(PaperExtraction),
            usage=usage,
        )


def paper_extractor(
    *,
    client: AsyncOpenAI | None = None,
    model: str | None = None,
    http_client: httpx2.AsyncClient | None = None,
    reasoning: ReasoningEffort | None = None,
) -> PaperExtractor:
    return OpenRouterPaperExtractor(
        client=client, model=model, http_client=http_client, reasoning=reasoning
    )
