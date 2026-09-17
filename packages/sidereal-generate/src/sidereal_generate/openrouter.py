"""The OpenRouter-backed implementation of every generator."""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Sequence
from typing import Any

import httpx2
from openai import AsyncOpenAI, BadRequestError, NotFoundError
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionContentPartParam,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
)
from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel, ValidationError
from sidereal_core.models import HomeworkFormat

from sidereal_generate.base import (
    FeedbackGenerator,
    GenerationError,
    GenerationNotConfiguredError,
    GenerationTruncatedError,
    HomeworkGenerator,
    PaperExtractor,
    PlanGenerator,
    strict_schema,
    unescaped,
    unstringify,
)
from sidereal_generate.chunks import BATCH_QUESTIONS
from sidereal_generate.extraction import Ask, ChunkedPaperExtractor
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
from sidereal_generate.settings import TRUNCATION_FACTOR, ReasoningEffort, generate_settings
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
# How much of a raw answer the DEBUG line carries.
DEBUG_PREFIX = 2000


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

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

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
        images: Sequence[bytes] = (),
        usage: UsageTally | None = None,
        budget: int | None = None,
    ) -> object:
        messages = _messages(system, prompt, images)
        budget = budget or self._max_tokens
        if self._structured:
            try:
                return await self._json_schema(messages, name, schema, usage, len(images), budget)
            except (BadRequestError, NotFoundError) as exc:
                logger.warning(
                    "%s refused strict mode (response_format json_schema) for %s, "
                    "falling back to an unconstrained tool call. The provider said: %s",
                    self._model,
                    name,
                    exc,
                )
                self._structured = False
        return await self._tool_call(
            messages, name, description, schema, usage, len(images), budget
        )

    async def _json_schema(
        self,
        messages: list[ChatCompletionMessageParam],
        name: str,
        schema: dict[str, Any],
        usage: UsageTally | None = None,
        images: int = 0,
        budget: int | None = None,
    ) -> object:
        completion = await self._openai().chat.completions.create(
            model=self._model,
            max_tokens=budget or self._max_tokens,
            timeout=REQUEST_TIMEOUT,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": name, "strict": True, "schema": schema},
            },
            extra_body=self._extra(),
        )
        message = self._answer(completion, name, usage, images)
        if message.content:
            return self._decode(message.content, name)
        # A provider may answer a `json_schema` request with the tool call it translated
        # the schema into.
        return self._decode(self._arguments(message, name), name)

    async def _tool_call(
        self,
        messages: list[ChatCompletionMessageParam],
        name: str,
        description: str,
        schema: dict[str, Any],
        usage: UsageTally | None = None,
        images: int = 0,
        budget: int | None = None,
    ) -> object:
        completion = await self._openai().chat.completions.create(
            model=self._model,
            max_tokens=budget or self._max_tokens,
            timeout=REQUEST_TIMEOUT,
            messages=messages,
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
        message = self._answer(completion, name, usage, images)
        arguments = self._arguments(message, name)
        if arguments is None:
            raise GenerationError(f"{self._model} did not call {name}")
        return self._decode(arguments, name)

    def _answer(
        self,
        completion: ChatCompletion,
        name: str,
        usage: UsageTally | None = None,
        images: int = 0,
    ) -> ChatCompletionMessage:
        """The message, once it is known to be a whole answer rather than a stub."""
        choice = None if not completion.choices else completion.choices[0]
        # A call that failed still spent tokens, so this is recorded before any raise.
        self._record(completion, usage, images)
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

    def _record(
        self, completion: ChatCompletion, usage: UsageTally | None, images: int = 0
    ) -> None:
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
            images=images,
            image_tokens=_image_tokens(spent),
        )

    def _arguments(self, message: ChatCompletionMessage, name: str) -> str | None:
        for call in message.tool_calls or ():
            if call.type == "function" and call.function.name == name:
                return call.function.arguments
        return None

    def _decode(self, raw: str | None, name: str) -> object:
        if not raw:
            raise GenerationError(f"{self._model} returned nothing for {name}")
        # What the model actually sent, bounded: a 12,000-token answer must not flood a log,
        # and a payload nothing else explains is read here.
        logger.debug("%s answered %d bytes: %s", name, len(raw), raw[:DEBUG_PREFIX])
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


def _image_tokens(spent: CompletionUsage) -> int:
    """What the images cost. A gateway that says nothing about them must still tally."""
    details: Any = spent.prompt_tokens_details
    raw = getattr(details, "image_tokens", None)
    extra = details.model_extra if isinstance(details, BaseModel) else details
    if raw is None and isinstance(extra, dict):
        raw = extra.get("image_tokens")
    return int(raw) if isinstance(raw, int | float) else 0


def _messages(
    system: str, prompt: str, images: Sequence[bytes] = ()
) -> list[ChatCompletionMessageParam]:
    """The pages first, then what to do with them: a model reads the instruction last."""
    if not images:
        return [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    content: list[ChatCompletionContentPartParam] = [
        {"type": "image_url", "image_url": {"url": _data_url(image)}} for image in images
    ]
    content.append({"type": "text", "text": prompt})
    return [{"role": "system", "content": system}, {"role": "user", "content": content}]


def _data_url(jpeg: bytes) -> str:
    return f"data:image/jpeg;base64,{base64.b64encode(jpeg).decode()}"


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
        payload = await self._asked(request, usage, None)
        try:
            answer = unescaped(unstringify(payload, self._output_model))
            return self._output_model.model_validate(answer)
        except ValidationError as exc:
            raise GenerationError(f"{self._tool_name} returned an unusable payload: {exc}") from exc

    async def _asked(
        self, request: GenerationRequest, usage: UsageTally | None, budget: int | None
    ) -> object:
        """A cut-off answer buys nothing, so it is asked for once more with twice the budget."""
        try:
            return await self._call.payload(
                system=self.system(request),
                prompt=render(request),
                name=self._tool_name,
                description=f"Return the {self._output_model.__name__} for this request.",
                schema=strict_schema(self._output_model),
                usage=usage,
                budget=budget,
            )
        except GenerationTruncatedError:
            if budget is not None:
                raise
            doubled = self._call.max_tokens * TRUNCATION_FACTOR
            logger.warning(
                "%s was cut off writing %s; asking again with %d tokens",
                self._call.model,
                self._tool_name,
                doubled,
            )
            return await self._asked(request, usage, doubled)


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
        PlanOutput,
        PLAN_PROMPT,
        PLAN_TOOL,
        client=client,
        model=model,
        max_tokens=generate_settings().plan_max_tokens,
        http_client=http_client,
    )


class _Caller:
    """The chunked extraction's seam, answered by one OpenRouter call each time."""

    def __init__(self, call: OpenRouterCall) -> None:
        self._call = call

    @property
    def model(self) -> str:
        return self._call.model

    async def ask(self, ask: Ask, *, usage: UsageTally | None = None) -> object:
        return await self._call.payload(
            system=ask.system,
            prompt=ask.prompt,
            name=ask.tool,
            description=ask.description,
            schema=ask.schema,
            images=ask.pages,
            usage=usage,
        )


class OpenRouterPaperExtractor(ChunkedPaperExtractor):
    """The paper read in chunks, each against a schema small enough to compile."""

    def __init__(
        self,
        *,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        http_client: httpx2.AsyncClient | None = None,
        reasoning: ReasoningEffort | None = None,
        size: int = BATCH_QUESTIONS,
    ) -> None:
        settings = generate_settings()
        super().__init__(
            _Caller(
                OpenRouterCall(
                    client=client,
                    model=model,
                    max_tokens=max_tokens or settings.extract_max_tokens,
                    http_client=http_client,
                    reasoning=reasoning or settings.extract_reasoning,
                )
            ),
            size=size,
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
