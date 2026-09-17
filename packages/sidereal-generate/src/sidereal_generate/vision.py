"""Reading handwriting: the pages go to the model as images, the transcription comes back typed."""

from __future__ import annotations

import logging
from collections.abc import Sequence

import httpx2
from openai import APIConnectionError, APIError, AsyncOpenAI
from openai import AuthenticationError as OpenAIAuthenticationError
from openai import PermissionDeniedError as OpenAIPermissionDeniedError
from openai import RateLimitError as OpenAIRateLimitError
from pydantic import ValidationError
from sidereal_ingest.base import IngestError
from sidereal_ingest.transcribe import (
    FakeTranscriber,
    Page,
    PaperQuestion,
    Transcriber,
    Transcription,
    TranscriptionResult,
)

from sidereal_generate.base import (
    GenerationError,
    GenerationNotConfiguredError,
    GenerationTruncatedError,
    strict_schema,
)
from sidereal_generate.openrouter import OpenRouterCall
from sidereal_generate.prompts import (
    SCAN_PROMPT,
    SCAN_SOLUTIONS_PROMPT,
    SCAN_TOOL,
    render_questions,
)
from sidereal_generate.settings import GenerateBackend, ReasoningEffort, generate_settings
from sidereal_generate.usage import UsageTally

logger = logging.getLogger(__name__)

NO_VISION = (
    "Handwriting is read by the OpenRouter backend. Ask an administrator to set "
    "SIDEREAL_GENERATE_BACKEND=openrouter."
)
NOT_CONFIGURED = "Handwriting scans are not set up yet. Ask an administrator to configure them."
REFUSED = "The transcription service refused the request."
BUSY = "The transcription service is busy; try again in a minute."
UNREACHABLE = "The transcription service could not be reached. Try again shortly."
CUT_OFF = "The transcription was cut off before it finished. Send fewer pages."
UNUSABLE = "The pages could not be transcribed. Try again."
NO_PAGES = "A scan needs at least one page."


class OpenRouterTranscriber:
    """One call, however many pages: they go up as JPEG parts against a strict schema."""

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

    async def transcribe(
        self, pages: Sequence[Page], *, questions: Sequence[PaperQuestion] = ()
    ) -> TranscriptionResult:
        if not pages:
            raise IngestError(NO_PAGES)
        usage = UsageTally()
        try:
            payload = await self._call.payload(
                system=SCAN_SOLUTIONS_PROMPT if questions else SCAN_PROMPT,
                prompt=_prompt(pages, questions),
                name=SCAN_TOOL,
                description="Return the transcription of these pages.",
                schema=strict_schema(Transcription),
                images=[page.jpeg for page in pages],
                usage=usage,
            )
        except (GenerationError, APIError) as exc:
            logger.warning("%s could not transcribe %d page(s): %s", self.model, len(pages), exc)
            raise IngestError(_message(exc)) from exc
        try:
            transcription = Transcription.model_validate(payload)
        except ValidationError as exc:
            logger.warning("%s returned an unusable transcription: %s", self.model, exc)
            raise IngestError(UNUSABLE) from exc
        return TranscriptionResult(
            transcription=transcription, model=self.model, usage=usage.provenance()
        )


class UnavailableTranscriber:
    """A backend that cannot see an image. Every call is the sentence that says so."""

    model = "none"

    async def transcribe(
        self, pages: Sequence[Page], *, questions: Sequence[PaperQuestion] = ()
    ) -> TranscriptionResult:
        raise IngestError(NO_VISION)


def default_transcriber() -> Transcriber:
    """`SIDEREAL_GENERATE_BACKEND` decides, as it does for every generator."""
    match generate_settings().backend:
        case GenerateBackend.FAKE:
            return FakeTranscriber()
        case GenerateBackend.OPENROUTER:
            return OpenRouterTranscriber()
        case GenerateBackend.CLAUDE:
            return UnavailableTranscriber()


def _prompt(pages: Sequence[Page], questions: Sequence[PaperQuestion]) -> str:
    count = f"{len(pages)} page" if len(pages) == 1 else f"{len(pages)} pages"
    if not questions:
        return f"Transcribe these {count}, in order."
    return (
        f"Transcribe these {count}, in order, and map the working to these questions:\n"
        f"{render_questions(questions)}"
    )


def _message(exc: BaseException) -> str:
    """What the tutor reads. The technical detail is logged, never stored."""
    match exc:
        case GenerationNotConfiguredError():
            return NOT_CONFIGURED
        case GenerationTruncatedError():
            return CUT_OFF
        case GenerationError():
            return UNUSABLE
        case OpenAIAuthenticationError() | OpenAIPermissionDeniedError():
            return REFUSED
        case OpenAIRateLimitError():
            return BUSY
        case APIConnectionError():
            return UNREACHABLE
        case _:
            return UNUSABLE
