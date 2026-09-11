from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

import httpx2
import pytest
from anthropic import AsyncAnthropic
from sidereal_core.models import Document, DocumentKind, Student
from sidereal_generate.base import GenerationError
from sidereal_generate.claude import AnthropicGenerator, homework_generator
from sidereal_generate.models import GenerationRequest, HomeworkOutput
from sidereal_generate.prompts import HOMEWORK_PROMPT, HOMEWORK_TOOL

STUDENT_ID = UUID("11111111-1111-4111-8111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")

HOMEWORK = {
    "title": "Quadratics: week 3",
    "content": "## Quadratics\nWork through each question.",
    "questions": [
        {
            "text": "Factorise x^2 - 5x + 6.",
            "answer": "(x-2)(x-3)",
            "topic": "factorising",
            "difficulty": 2,
        }
    ],
}

Handler = Callable[[httpx2.Request], httpx2.Response]


def request() -> GenerationRequest:
    return GenerationRequest(
        student=Student(id=STUDENT_ID, name="A. Tutee", level="GCSE", subjects=["maths"]),
        documents=(
            Document(
                id=DOCUMENT_ID,
                title="Lesson 3",
                kind=DocumentKind.TRANSCRIPT,
                text="We factorised quadratics.",
            ),
        ),
        instructions="Six questions.",
    )


def message(content: list[dict[str, Any]], *, stop_reason: str = "tool_use") -> dict[str, Any]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def generator_for(handler: Handler, model: str | None = None) -> AnthropicGenerator[HomeworkOutput]:
    client = AsyncAnthropic(
        api_key="test-key", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    )
    return AnthropicGenerator(
        HomeworkOutput, HOMEWORK_PROMPT, HOMEWORK_TOOL, client=client, model=model
    )


async def test_a_tool_call_becomes_a_validated_output() -> None:
    seen: list[httpx2.Request] = []

    def handler(http_request: httpx2.Request) -> httpx2.Response:
        seen.append(http_request)
        body = message(
            [{"type": "tool_use", "id": "toolu_1", "name": HOMEWORK_TOOL, "input": HOMEWORK}]
        )
        return httpx2.Response(200, json=body)

    output = await generator_for(handler, "claude-sonnet-5").generate(request())

    assert output.title == "Quadratics: week 3"
    assert [question.difficulty for question in output.questions] == [2]

    sent = json.loads(seen[0].content)
    assert sent["model"] == "claude-sonnet-5"
    assert sent["system"] == HOMEWORK_PROMPT
    assert sent["tool_choice"] == {"type": "tool", "name": HOMEWORK_TOOL}
    assert sent["tools"][0]["strict"] is True
    assert sent["tools"][0]["input_schema"]["properties"].keys() >= {
        "title",
        "content",
        "questions",
    }
    assert "We factorised quadratics." in sent["messages"][0]["content"]
    assert "Six questions." in sent["messages"][0]["content"]


async def test_a_reply_with_no_tool_call_is_a_generation_error() -> None:
    body = message([{"type": "text", "text": "I would rather not."}], stop_reason="end_turn")

    with pytest.raises(GenerationError, match="did not call"):
        await generator_for(lambda _: httpx2.Response(200, json=body)).generate(request())


async def test_a_tool_call_that_does_not_validate_is_a_generation_error() -> None:
    body = message(
        [{"type": "tool_use", "id": "toolu_1", "name": HOMEWORK_TOOL, "input": {"title": "x"}}]
    )

    with pytest.raises(GenerationError, match="unusable payload"):
        await generator_for(lambda _: httpx2.Response(200, json=body)).generate(request())


def test_the_model_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIDEREAL_GENERATE_MODEL", "claude-opus-5")

    assert homework_generator().model == "claude-opus-5"


def test_building_a_generator_needs_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert homework_generator().model
