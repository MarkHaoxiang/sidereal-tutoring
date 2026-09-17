from __future__ import annotations

import base64
import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from openai import AsyncOpenAI
from sidereal_generate.prompts import SCAN_PROMPT, SCAN_SOLUTIONS_PROMPT, SCAN_TOOL
from sidereal_generate.settings import GenerateBackend, ReasoningEffort
from sidereal_generate.vision import (
    BUSY,
    CUT_OFF,
    NO_VISION,
    REFUSED,
    UNUSABLE,
    OpenRouterTranscriber,
    UnavailableTranscriber,
    default_transcriber,
)
from sidereal_ingest.base import IngestError
from sidereal_ingest.transcribe import Confidence, FakeTranscriber, Page, PaperQuestion

BASE_URL = "https://openrouter.test/api/v1"
MODEL = "anthropic/claude-sonnet-5"
JPEG = b"\xff\xd8\xff\xe0 not really a jpeg"
TRANSCRIPTION = {
    "text": "## Page 1\n$2 x = 8$\n$x = 4$",
    "confidence": "high",
    "questions": [
        {"number": "1", "text": "$2 x = 8$, so $x = 4$", "confidence": "high", "note": None}
    ],
}

Handler = Callable[[httpx2.Request], httpx2.Response]


def completion(message: dict[str, Any], *, finish_reason: str = "stop") -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": MODEL,
        "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
        "usage": {
            "prompt_tokens": 1500,
            "completion_tokens": 200,
            "total_tokens": 1700,
            "cost": 0.004,
        },
    }


def answered(payload: dict[str, Any]) -> httpx2.Response:
    return httpx2.Response(
        200, json=completion({"role": "assistant", "content": json.dumps(payload)})
    )


def transcriber_for(handler: Handler) -> OpenRouterTranscriber:
    return OpenRouterTranscriber(
        client=AsyncOpenAI(
            api_key="test-key",
            base_url=BASE_URL,
            max_retries=0,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
        ),
        model=MODEL,
        reasoning=ReasoningEffort.LOW,
    )


def replayer(*replies: httpx2.Response) -> tuple[list[httpx2.Request], Handler]:
    seen: list[httpx2.Request] = []

    def handler(http_request: httpx2.Request) -> httpx2.Response:
        seen.append(http_request)
        return replies[min(len(seen) - 1, len(replies) - 1)]

    return seen, handler


def pages(count: int = 1) -> list[Page]:
    return [Page(index=n, jpeg=JPEG) for n in range(1, count + 1)]


async def test_the_pages_go_up_as_jpeg_parts_before_the_instruction() -> None:
    seen, handler = replayer(answered(TRANSCRIPTION))

    result = await transcriber_for(handler).transcribe(pages(2))

    assert result.transcription.confidence is Confidence.HIGH
    assert result.model == MODEL
    sent = json.loads(seen[0].content)
    content = sent["messages"][1]["content"]
    assert sent["messages"][0]["content"] == SCAN_PROMPT
    assert [part["type"] for part in content] == ["image_url", "image_url", "text"]
    assert content[0]["image_url"]["url"] == (
        f"data:image/jpeg;base64,{base64.b64encode(JPEG).decode()}"
    )
    assert "2 pages" in content[2]["text"]
    assert sent["reasoning"] == {"effort": "low"}
    assert sent["response_format"]["json_schema"]["name"] == SCAN_TOOL
    assert sent["response_format"]["json_schema"]["strict"] is True


async def test_a_paper_sends_its_numbers_and_stems_and_asks_for_the_mapping() -> None:
    seen, handler = replayer(answered(TRANSCRIPTION))

    result = await transcriber_for(handler).transcribe(
        pages(), questions=[PaperQuestion(number="1", stem="Solve $2 x + 3 = 11$.")]
    )

    sent = json.loads(seen[0].content)
    assert sent["messages"][0]["content"] == SCAN_SOLUTIONS_PROMPT
    assert (
        '<question number="1">Solve $2 x + 3 = 11$.</question>'
        in sent["messages"][1]["content"][-1]["text"]
    )
    assert [question.number for question in result.transcription.questions] == ["1"]


async def test_what_the_call_cost_comes_back_with_the_transcription() -> None:
    _, handler = replayer(answered(TRANSCRIPTION))

    result = await transcriber_for(handler).transcribe(pages())

    assert result.usage == {
        "calls": 1,
        "prompt_tokens": 1500,
        "completion_tokens": 200,
        "total_tokens": 1700,
        "cost_usd": 0.004,
        "images": 1,
        "reasoning_effort": "low",
    }


async def test_a_reply_that_is_not_a_transcription_is_one_sentence() -> None:
    _, handler = replayer(answered({"text": "read", "confidence": "certain", "questions": []}))

    with pytest.raises(IngestError, match=UNUSABLE):
        await transcriber_for(handler).transcribe(pages())


async def test_an_answer_cut_off_by_the_budget_says_to_send_fewer_pages() -> None:
    _, handler = replayer(
        httpx2.Response(
            200,
            json=completion({"role": "assistant", "content": None}, finish_reason="length"),
        )
    )

    with pytest.raises(IngestError, match="fewer pages"):
        await transcriber_for(handler).transcribe(pages())
    assert CUT_OFF.endswith("Send fewer pages.")


async def test_a_refused_key_never_reaches_the_tutor_as_the_gateway_worded_it() -> None:
    _, handler = replayer(httpx2.Response(401, json={"error": {"message": "No auth credentials"}}))

    with pytest.raises(IngestError, match=REFUSED):
        await transcriber_for(handler).transcribe(pages())


async def test_a_busy_gateway_asks_the_tutor_to_try_again() -> None:
    _, handler = replayer(httpx2.Response(429, json={"error": {"message": "rate limited"}}))

    with pytest.raises(IngestError, match=BUSY):
        await transcriber_for(handler).transcribe(pages())


async def test_no_pages_is_refused_before_any_request() -> None:
    seen, handler = replayer(answered(TRANSCRIPTION))

    with pytest.raises(IngestError, match="at least one page"):
        await transcriber_for(handler).transcribe([])

    assert seen == []


@pytest.mark.parametrize(
    ("backend", "expected"),
    [
        (GenerateBackend.FAKE, FakeTranscriber),
        (GenerateBackend.OPENROUTER, OpenRouterTranscriber),
        (GenerateBackend.CLAUDE, UnavailableTranscriber),
    ],
)
def test_the_backend_decides_what_reads_handwriting(
    backend: GenerateBackend, expected: type, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIDEREAL_GENERATE_BACKEND", backend.value)

    assert isinstance(default_transcriber(), expected)


async def test_a_backend_that_cannot_see_an_image_says_which_one_can() -> None:
    with pytest.raises(IngestError, match="openrouter"):
        await UnavailableTranscriber().transcribe(pages())
    assert "OpenRouter" in NO_VISION
