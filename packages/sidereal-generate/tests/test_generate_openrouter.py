from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

import httpx2
import pytest
from openai import AsyncOpenAI
from pydantic import ValidationError
from sidereal_core.models import Document, DocumentKind, HomeworkFormat, Student
from sidereal_generate.base import (
    GenerationError,
    GenerationNotConfiguredError,
    GenerationTruncatedError,
    strict_schema,
)
from sidereal_generate.chunks import MarkSchemeBatch, PaperSkeleton, QuestionBatch
from sidereal_generate.models import (
    GenerationRequest,
    HomeworkOutput,
    MarkSchemeExtraction,
    PaperExtraction,
)
from sidereal_generate.openrouter import (
    REFERER,
    TITLE,
    OpenRouterGenerator,
    homework_generator,
    paper_extractor,
)
from sidereal_generate.prompts import (
    HOMEWORK_PROMPT,
    HOMEWORK_TOOL,
    HOMEWORK_TYPST_PROMPT,
    MARK_SCHEME_TOOL,
    QUESTION_BATCH_PAGES_PROMPT,
    QUESTIONS_TOOL,
    SKELETON_PAGES_PROMPT,
    SKELETON_TOOL,
)
from sidereal_generate.settings import DEFAULT_EXTRACT_MAX_TOKENS, generate_settings
from sidereal_generate.usage import UsageTally

STUDENT_ID = UUID("11111111-1111-4111-8111-111111111111")
DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")
BASE_URL = "https://openrouter.test/api/v1"
MODEL = "anthropic/claude-sonnet-5"

HOMEWORK: dict[str, Any] = {
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
PAPER: dict[str, Any] = {
    "paper": {
        "title": "Pure Mathematics 1",
        "source": "Edexcel 2025",
        "board": "Edexcel",
        "year": 2025,
        "time_minutes": 90,
        "total_marks": 75,
        "instructions": None,
        "questions": [
            {
                "number": "1",
                "stem": "Find $(d y) / (d x)$ when $y = x^3$.",
                "marks": 3,
                "answer_lines": 5,
                "parts": [],
            }
        ],
    },
    "figures": [],
}
SHAPE: dict[str, Any] = {
    "title": "Pure Mathematics 1",
    "source": "Edexcel 2025",
    "board": "Edexcel",
    "year": 2025,
    "time_minutes": 90,
    "total_marks": 75,
    "instructions": None,
    "questions": [
        {"number": "1", "stem": "Differentiation", "page": 1, "has_material": False, "marks": 3}
    ],
    "sections": [],
    "passages": [],
}
QUESTIONS: dict[str, Any] = {
    "questions": [
        {
            "number": "1",
            "stem": "Find $(d y) / (d x)$ when $y = x^3$.",
            "marks": 3,
            "answer": {"type": "lines", "lines": 5},
            "parts": [],
        }
    ],
    "figures": [],
}
DRAWN_QUESTIONS: dict[str, Any] = {
    **QUESTIONS,
    "figures": [
        {
            "page": 2,
            "bbox": [0.1, 0.1, 0.8, 0.6],
            "caption": "Figure 1",
            "question_number": "1",
            "part_label": None,
        }
    ],
}
UNUSABLE: dict[str, Any] = {"questions": [{"stem": "no number"}], "figures": []}
MARK_SCHEME: dict[str, Any] = {
    "mark_scheme": {
        "title": "Pure Mathematics 1: mark scheme",
        "questions": [{"number": "1", "answer": "$3 x^2$"}],
    }
}
SCHEME: dict[str, Any] = {"questions": [{"number": "1", "answer": "$3 x^2$"}]}

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


def document() -> Document:
    return Document(
        id=DOCUMENT_ID,
        title="Mock paper 1",
        kind=DocumentKind.UPLOAD,
        text="1. Find $(d y) / (d x)$ when $y = x^3$.",
    )


def completion(message: dict[str, Any], *, finish_reason: str = "stop") -> dict[str, Any]:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": MODEL,
        "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


def answered(payload: dict[str, Any]) -> dict[str, Any]:
    """What a model with a strict `json_schema` mode returns: the object as content."""
    return completion({"role": "assistant", "content": json.dumps(payload)})


def called(payload: dict[str, Any], *, name: str = HOMEWORK_TOOL) -> dict[str, Any]:
    """What the fallback returns: the object as one function call's arguments."""
    return completion(
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(payload)},
                }
            ],
        },
        finish_reason="tool_calls",
    )


def cut_off() -> dict[str, Any]:
    """What a budget spent entirely on reasoning looks like: no content, and `length`."""
    return completion(
        {"role": "assistant", "content": None, "refusal": None},
        finish_reason="length",
    )


def unsupported() -> httpx2.Response:
    return httpx2.Response(
        400,
        json={
            "error": {
                "code": 400,
                "message": f"{MODEL} does not support the response_format json_schema parameter",
            }
        },
    )


def client_for(handler: Handler) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key="test-key",
        base_url=BASE_URL,
        max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )


def generator_for(handler: Handler) -> OpenRouterGenerator[HomeworkOutput]:
    return OpenRouterGenerator(
        HomeworkOutput, HOMEWORK_PROMPT, HOMEWORK_TOOL, client=client_for(handler), model=MODEL
    )


def replayer(*replies: httpx2.Response) -> tuple[list[httpx2.Request], Handler]:
    """Answers each request in turn, repeating the last reply once they run out."""
    seen: list[httpx2.Request] = []

    def handler(http_request: httpx2.Request) -> httpx2.Response:
        seen.append(http_request)
        return replies[min(len(seen) - 1, len(replies) - 1)]

    return seen, handler


async def test_a_json_schema_answer_becomes_a_validated_output() -> None:
    seen, handler = replayer(httpx2.Response(200, json=answered(HOMEWORK)))

    output = await generator_for(handler).generate(request())

    assert output.title == "Quadratics: week 3"
    assert [question.difficulty for question in output.questions] == [2]

    sent = json.loads(seen[0].content)
    assert seen[0].url.path.endswith("/chat/completions")
    assert sent["model"] == MODEL
    assert sent["response_format"]["type"] == "json_schema"
    assert sent["response_format"]["json_schema"]["name"] == HOMEWORK_TOOL
    assert sent["response_format"]["json_schema"]["strict"] is True
    assert sent["response_format"]["json_schema"]["schema"]["properties"].keys() >= {
        "title",
        "content",
        "questions",
    }
    assert sent["response_format"]["json_schema"]["schema"]["required"] == [
        "title",
        "content",
        "questions",
    ]
    assert "tools" not in sent
    assert sent["messages"][0] == {"role": "system", "content": HOMEWORK_PROMPT}
    assert "We factorised quadratics." in sent["messages"][1]["content"]
    assert "Six questions." in sent["messages"][1]["content"]


async def test_a_model_without_json_schema_falls_back_to_a_forced_tool_call() -> None:
    seen, handler = replayer(unsupported(), httpx2.Response(200, json=called(HOMEWORK)))

    output = await generator_for(handler).generate(request())

    assert output.title == "Quadratics: week 3"
    assert len(seen) == 2

    sent = json.loads(seen[1].content)
    assert "response_format" not in sent
    assert sent["tool_choice"] == {"type": "function", "function": {"name": HOMEWORK_TOOL}}
    assert sent["tools"][0]["function"]["name"] == HOMEWORK_TOOL
    assert sent["tools"][0]["function"]["parameters"]["required"] == [
        "title",
        "content",
        "questions",
    ]


async def test_the_fallback_is_remembered_so_the_refusal_is_asked_for_once() -> None:
    seen, handler = replayer(unsupported(), httpx2.Response(200, json=called(HOMEWORK)))
    generator = generator_for(handler)

    await generator.generate(request())
    await generator.generate(request())

    assert len(seen) == 3
    assert "response_format" not in json.loads(seen[2].content)


async def test_both_backends_are_asked_for_the_same_strict_schema() -> None:
    seen, handler = replayer(unsupported(), httpx2.Response(200, json=called(HOMEWORK)))
    generator = generator_for(handler)

    await generator.generate(request())

    schema = strict_schema(HomeworkOutput)
    assert json.loads(seen[0].content)["response_format"]["json_schema"]["schema"] == schema
    assert json.loads(seen[1].content)["tools"][0]["function"]["parameters"] == schema


async def test_a_typst_request_asks_for_a_typst_body() -> None:
    seen, handler = replayer(httpx2.Response(200, json=answered(HOMEWORK)))
    generator = homework_generator(client=client_for(handler), model=MODEL)

    await generator.generate(request().model_copy(update={"format": HomeworkFormat.TYPST}))
    await generator.generate(request())

    assert json.loads(seen[0].content)["messages"][0]["content"] == HOMEWORK_TYPST_PROMPT
    assert json.loads(seen[1].content)["messages"][0]["content"] == HOMEWORK_PROMPT


async def test_an_answer_that_does_not_validate_is_a_generation_error() -> None:
    _, handler = replayer(httpx2.Response(200, json=answered({"title": "x"})))

    with pytest.raises(GenerationError, match="unusable payload"):
        await generator_for(handler).generate(request())


async def test_an_answer_that_is_not_json_is_a_generation_error() -> None:
    _, handler = replayer(
        httpx2.Response(
            200, json=completion({"role": "assistant", "content": "I would rather not."})
        )
    )

    with pytest.raises(GenerationError, match="not JSON"):
        await generator_for(handler).generate(request())


async def test_an_empty_answer_is_a_generation_error() -> None:
    _, handler = replayer(
        httpx2.Response(200, json=completion({"role": "assistant", "content": None}))
    )

    with pytest.raises(GenerationError, match="returned nothing"):
        await generator_for(handler).generate(request())


async def test_a_fallback_with_no_tool_call_is_a_generation_error() -> None:
    _, handler = replayer(
        unsupported(),
        httpx2.Response(200, json=completion({"role": "assistant", "content": "No."})),
    )

    with pytest.raises(GenerationError, match="did not call"):
        await generator_for(handler).generate(request())


async def test_the_key_base_url_and_attribution_headers_come_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", f"{BASE_URL}/")
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-opus-5")
    seen, handler = replayer(httpx2.Response(200, json=answered(HOMEWORK)))
    generator = homework_generator(
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    )

    assert generator.model == "anthropic/claude-opus-5"
    await generator.generate(request())

    assert str(seen[0].url) == f"{BASE_URL}/chat/completions"
    assert seen[0].headers["authorization"] == "Bearer test-key"
    assert seen[0].headers["HTTP-Referer"] == REFERER
    assert seen[0].headers["X-Title"] == TITLE
    assert json.loads(seen[0].content)["model"] == "anthropic/claude-opus-5"


async def test_a_missing_key_is_a_sentence_not_a_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    generator = homework_generator()

    assert generator.model  # Building it asks for nothing.
    with pytest.raises(GenerationNotConfiguredError, match="OPENROUTER_API_KEY"):
        await generator.generate(request())


async def test_a_budget_spent_before_the_answer_starts_says_it_was_cut_off() -> None:
    """The real first-run failure: reasoning tokens spent the whole budget, content null."""
    _, handler = replayer(httpx2.Response(200, json=cut_off()))

    with pytest.raises(GenerationTruncatedError, match="ran out of output budget"):
        await generator_for(handler).generate(request())


async def test_a_cut_off_tool_call_says_it_was_cut_off_too() -> None:
    _, handler = replayer(unsupported(), httpx2.Response(200, json=cut_off()))

    with pytest.raises(GenerationTruncatedError, match="ran out of output budget"):
        await generator_for(handler).generate(request())


async def test_a_json_schema_answered_as_a_tool_call_is_read_from_the_call() -> None:
    """Some providers translate the schema into a tool call and leave content empty."""
    _, handler = replayer(httpx2.Response(200, json=called(HOMEWORK)))

    output = await generator_for(handler).generate(request())

    assert output.title == "Quadratics: week 3"


async def test_a_refusal_is_a_generation_error_naming_it() -> None:
    _, handler = replayer(
        httpx2.Response(
            200,
            json=completion({"role": "assistant", "content": None, "refusal": "I cannot."}),
        )
    )

    with pytest.raises(GenerationError, match=r"refused emit_homework: I cannot\."):
        await generator_for(handler).generate(request())


async def test_an_answer_with_no_choices_is_a_generation_error() -> None:
    body = completion({"role": "assistant", "content": "{}"})
    body["choices"] = []
    _, handler = replayer(httpx2.Response(200, json=body))

    with pytest.raises(GenerationError, match="no choices"):
        await generator_for(handler).generate(request())


async def test_a_call_records_what_it_spent_including_reasoning_and_price() -> None:
    body = answered(HOMEWORK)
    body["usage"] = {
        "prompt_tokens": 3653,
        "completion_tokens": 1559,
        "total_tokens": 5212,
        "completion_tokens_details": {"reasoning_tokens": 1162},
        "cost": 0.022926,
    }
    _, handler = replayer(httpx2.Response(200, json=body))
    usage = UsageTally()

    await generator_for(handler).generate(request(), usage=usage)

    assert usage.calls == 1
    assert usage.prompt_tokens == 3653
    assert usage.completion_tokens == 1559
    assert usage.reasoning_tokens == 1162
    assert usage.total_tokens == 5212
    assert usage.provenance() == {
        "calls": 1,
        "prompt_tokens": 3653,
        "completion_tokens": 1559,
        "total_tokens": 5212,
        "reasoning_tokens": 1162,
        "cost_usd": 0.022926,
    }


async def test_the_gateway_is_asked_to_price_every_call() -> None:
    seen, handler = replayer(httpx2.Response(200, json=answered(HOMEWORK)))

    await generator_for(handler).generate(request())

    assert json.loads(seen[0].content)["usage"] == {"include": True}


async def test_a_call_that_was_cut_off_still_records_what_it_burned() -> None:
    """The tokens are spent whether or not an answer comes back, and the retry spends more."""
    body = cut_off()
    body["usage"] = {"prompt_tokens": 10, "completion_tokens": 20000, "total_tokens": 20010}
    _, handler = replayer(httpx2.Response(200, json=body))
    usage = UsageTally()

    with pytest.raises(GenerationTruncatedError):
        await generator_for(handler).generate(request(), usage=usage)

    assert usage.calls == 2
    assert usage.completion_tokens == 40000


async def test_a_cut_off_answer_is_asked_for_again_with_twice_the_budget() -> None:
    seen, handler = replayer(
        httpx2.Response(200, json=cut_off()), httpx2.Response(200, json=answered(HOMEWORK))
    )

    output = await generator_for(handler).generate(request())

    assert output.title == "Quadratics: week 3"
    first, second = (json.loads(sent.content)["max_tokens"] for sent in seen)
    assert second == first * 2


async def test_a_second_cut_off_is_the_tutors_failure() -> None:
    """Two rounds and no more: a third would only spend again on the same answer."""
    seen, handler = replayer(httpx2.Response(200, json=cut_off()))

    with pytest.raises(GenerationTruncatedError):
        await generator_for(handler).generate(request())

    assert len(seen) == 2


async def test_a_plan_starts_from_a_bigger_budget_than_the_rest() -> None:
    """A plan covers a whole period in one answer, and week one of six is no plan."""
    settings = generate_settings()

    assert settings.plan_max_tokens > settings.max_tokens


async def test_an_unpriced_call_files_no_price() -> None:
    """A total that silently covered only some calls would be worse than none."""
    body = answered(HOMEWORK)
    body["usage"] = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    _, handler = replayer(httpx2.Response(200, json=body))
    usage = UsageTally()

    await generator_for(handler).generate(request(), usage=usage)

    assert "cost_usd" not in (usage.provenance() or {})


def asked_name(body: dict[str, Any]) -> str:
    """Which schema a request asks for, whether as `response_format` or as a tool."""
    if "response_format" in body:
        return str(body["response_format"]["json_schema"]["name"])
    return str(body["tools"][0]["function"]["name"])


def sent(http_request: httpx2.Request) -> dict[str, Any]:
    body: dict[str, Any] = json.loads(http_request.content)
    return body


def schema_of(http_request: httpx2.Request) -> dict[str, Any]:
    body = sent(http_request)
    if "response_format" in body:
        schema: dict[str, Any] = body["response_format"]["json_schema"]["schema"]
        return schema
    parameters: dict[str, Any] = body["tools"][0]["function"]["parameters"]
    return parameters


def extraction(
    replies: dict[str, list[dict[str, Any]]], usage: dict[str, Any] | None = None
) -> tuple[list[httpx2.Request], Handler]:
    """Answers each call with the next payload queued for the schema it asks for."""
    seen: list[httpx2.Request] = []

    def handler(http_request: httpx2.Request) -> httpx2.Response:
        seen.append(http_request)
        queue = replies[asked_name(sent(http_request))]
        body = answered(queue.pop(0) if len(queue) > 1 else queue[0])
        if usage is not None:
            body["usage"] = usage
        return httpx2.Response(200, json=body)

    return seen, handler


def prompt_of(http_request: httpx2.Request) -> str:
    """The text the model reads, whether it went up alone or behind the page images."""
    content = sent(http_request)["messages"][1]["content"]
    return content if isinstance(content, str) else content[-1]["text"]


async def test_a_paper_is_read_as_a_shape_and_then_its_questions() -> None:
    seen, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [QUESTIONS]})

    read = await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert read.paper.board == "Edexcel"
    assert read.paper.questions[0].answer is not None
    assert [asked_name(sent(request)) for request in seen] == [SKELETON_TOOL, QUESTIONS_TOOL]
    assert schema_of(seen[0]) == strict_schema(PaperSkeleton)
    assert schema_of(seen[1]) == strict_schema(QuestionBatch)
    assert "$y = x^3$" in prompt_of(seen[0])
    assert '<question number="1" page="1">' in prompt_of(seen[1])


async def test_every_extraction_call_asks_for_the_larger_output_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transcribed paper is the longest answer asked for, and every run is budgeted as one."""
    monkeypatch.delenv("SIDEREAL_GENERATE_EXTRACT_MAX_TOKENS", raising=False)
    monkeypatch.delenv("SIDEREAL_GENERATE_MAX_TOKENS", raising=False)
    seen, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [QUESTIONS]})

    await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert [sent(request)["max_tokens"] for request in seen] == [DEFAULT_EXTRACT_MAX_TOKENS] * 2


async def test_a_batch_that_does_not_validate_is_asked_for_once_more_with_the_errors() -> None:
    seen, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [UNUSABLE, QUESTIONS]})

    read = await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert read.paper.questions[0].number == "1"
    assert len(seen) == 3
    retried = prompt_of(seen[2])
    assert "did not fit the structure" in retried
    assert "number" in retried


async def test_a_second_unusable_batch_is_a_generation_error() -> None:
    _, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [UNUSABLE]})

    with pytest.raises(GenerationError, match="could not be read after two tries"):
        await paper_extractor(client=client_for(handler), model=MODEL).extract(document())


async def test_a_batch_field_the_model_sent_as_json_text_is_parsed_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The live failure: the forced tool call is unconstrained, and a field arrived as text."""
    stringified = {"questions": json.dumps(QUESTIONS["questions"]), "figures": []}
    _, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [stringified]})

    with caplog.at_level(logging.WARNING):
        read = await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert read.paper.questions[0].stem == "Find $(d y) / (d x)$ when $y = x^3$."
    assert "QuestionBatch stringified questions" in caplog.text


async def test_a_string_that_is_not_an_object_is_still_refused() -> None:
    """The helper never swallows a real error: only JSON that parses to an object is parsed."""
    _, handler = extraction(
        {SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [{"questions": "the questions", "figures": []}]}
    )

    with pytest.raises(GenerationError, match="could not be read"):
        await paper_extractor(client=client_for(handler), model=MODEL).extract(document())


async def test_what_the_model_actually_sent_is_captured_at_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One look at this would have answered both of the live run's failures."""
    _, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [QUESTIONS]})

    with caplog.at_level(logging.DEBUG, logger="sidereal_generate.openrouter"):
        await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert f"{SKELETON_TOOL} answered" in caplog.text
    assert '"board": "Edexcel"' in caplog.text
    assert all(len(record.getMessage()) < 4000 for record in caplog.records)


async def test_page_images_go_up_with_the_pages_prompt_and_are_counted() -> None:
    spent = {
        "prompt_tokens": 4000,
        "completion_tokens": 20,
        "total_tokens": 4020,
        "prompt_tokens_details": {"cached_tokens": 0, "image_tokens": 2600},
    }
    seen, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [QUESTIONS]}, spent)
    usage = UsageTally()

    await paper_extractor(client=client_for(handler), model=MODEL).extract(
        document(), pages=[b"\xff\xd8one", b"\xff\xd8two"], usage=usage
    )

    assert sent(seen[0])["messages"][0]["content"] == SKELETON_PAGES_PROMPT
    assert sent(seen[1])["messages"][0]["content"] == QUESTION_BATCH_PAGES_PROMPT
    parts = sent(seen[0])["messages"][1]["content"]
    assert [part["type"] for part in parts] == ["image_url", "image_url", "text"]
    assert parts[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    # The shape sees the whole paper and the one run sees the pages it spans.
    assert (usage.provenance() or {})["images"] == 4
    assert (usage.provenance() or {})["image_tokens"] == 5200


async def test_a_retried_batch_sends_the_same_pages_again() -> None:
    seen, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [UNUSABLE, QUESTIONS]})

    read = await paper_extractor(client=client_for(handler), model=MODEL).extract(
        document(), pages=[b"\xff\xd8one"]
    )

    assert read.paper.title == "Pure Mathematics 1"
    retried = sent(seen[2])["messages"][1]["content"]
    assert [part["type"] for part in retried] == ["image_url", "text"]
    assert "did not fit the structure" in retried[-1]["text"]


async def test_a_batch_that_omits_figures_is_refused_rather_than_read_as_none() -> None:
    """An omitted key and a run with no figures must not look the same."""
    omitted = {"questions": QUESTIONS["questions"]}
    seen, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [omitted, QUESTIONS]})

    with pytest.raises(ValidationError, match="figures"):
        QuestionBatch.model_validate(omitted)

    read = await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert read.figures == ()
    assert len(seen) == 3
    assert "figures" in prompt_of(seen[2])


async def test_the_drawn_page_numbers_reach_the_run_that_spans_them() -> None:
    seen, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [DRAWN_QUESTIONS]})

    read = await paper_extractor(client=client_for(handler), model=MODEL).extract(
        document(), pages=[b"\xff\xd8one", b"\xff\xd8two"], drawn=[2]
    )

    assert [figure.page for figure in read.figures] == [2]
    assert "Pages 2 carry drawn content" in prompt_of(seen[1])


async def test_a_text_only_extraction_is_told_there_is_nothing_to_locate() -> None:
    seen, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [QUESTIONS]})

    await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert "`figures` is empty" in sent(seen[1])["messages"][0]["content"]
    assert all("image_url" not in str(sent(request)["messages"]) for request in seen)


async def test_a_mark_scheme_is_a_call_of_its_own_carrying_the_paper_numbering() -> None:
    seen, handler = extraction({MARK_SCHEME_TOOL: [SCHEME]})
    scheme = Document(
        id=UUID("33333333-3333-4333-8333-333333333333"),
        title="Mark scheme",
        kind=DocumentKind.UPLOAD,
        text="1 (a) $3 x^2$ (2)",
    )
    paper = PaperExtraction.model_validate(PAPER).paper

    read = await paper_extractor(client=client_for(handler), model=MODEL).extract_mark_scheme(
        scheme, paper
    )

    assert read.mark_scheme.questions[0].answer == "$3 x^2$"
    assert read.mark_scheme.title == "Pure Mathematics 1: mark scheme"
    assert asked_name(sent(seen[0])) == MARK_SCHEME_TOOL
    assert schema_of(seen[0]) == strict_schema(MarkSchemeBatch)
    prompt = prompt_of(seen[0])
    assert "<mark_scheme" in prompt
    assert "$3 x^2$" in prompt
    assert '<question number="1" marks="3"/>' in prompt


async def test_a_mark_scheme_run_that_does_not_validate_is_asked_for_once_more() -> None:
    seen, handler = extraction({MARK_SCHEME_TOOL: [{"questions": [{}]}, SCHEME]})
    paper = PaperExtraction.model_validate(PAPER).paper

    read = await paper_extractor(client=client_for(handler), model=MODEL).extract_mark_scheme(
        document(), paper
    )

    assert read.mark_scheme.questions[0].number == "1"
    assert "did not fit the structure" in prompt_of(seen[1])


async def test_a_second_unusable_mark_scheme_run_is_a_generation_error() -> None:
    _, handler = extraction({MARK_SCHEME_TOOL: [{"questions": [{}]}]})
    paper = PaperExtraction.model_validate(PAPER).paper

    with pytest.raises(GenerationError, match="mark scheme for questions 1 could not be read"):
        await paper_extractor(client=client_for(handler), model=MODEL).extract_mark_scheme(
            document(), paper
        )


async def test_a_repair_goes_out_in_the_same_runs_against_the_same_batch_schema() -> None:
    """The whole-paper schema is the grammar the provider refused; a repair may not send it."""
    corrected = {
        "questions": [
            {"number": "1", "stem": "Find $(d y) / (d x)$ when $y = x^3$, where $P Q$ is a chord."}
        ],
        "figures": [],
    }
    seen, handler = extraction({QUESTIONS_TOOL: [corrected]})
    read = PaperExtraction.model_validate(PAPER)

    repaired = await paper_extractor(client=client_for(handler), model=MODEL).repair(
        read, "line 219, column 42: unknown variable: PQ"
    )

    assert "$P Q$" in (repaired.paper.questions[0].stem or "")
    assert repaired.paper.title == "Pure Mathematics 1"
    assert asked_name(sent(seen[0])) == QUESTIONS_TOOL
    assert schema_of(seen[0]) == strict_schema(QuestionBatch)
    assert "does not compile" in sent(seen[0])["messages"][0]["content"]
    assert "unknown variable: PQ" in prompt_of(seen[0])
    assert '"number": "1"' in prompt_of(seen[0])


async def test_a_mark_scheme_repair_addresses_the_scheme_alone() -> None:
    seen, handler = extraction(
        {MARK_SCHEME_TOOL: [{"questions": [{"number": "1", "answer": "$3 x^2$"}]}]}
    )
    read = MarkSchemeExtraction.model_validate(MARK_SCHEME)

    await paper_extractor(client=client_for(handler), model=MODEL).repair_mark_scheme(
        read, "line 3, column 1: unknown variable: PQ"
    )

    assert asked_name(sent(seen[0])) == MARK_SCHEME_TOOL
    assert schema_of(seen[0]) == strict_schema(MarkSchemeBatch)
    assert "does not compile" in sent(seen[0])["messages"][0]["content"]
    assert "unknown variable: PQ" in prompt_of(seen[0])


async def test_an_extraction_asks_for_little_thinking_and_files_which(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transcription does not need deep reasoning, and reasoning is spent from the answer."""
    monkeypatch.delenv("SIDEREAL_GENERATE_REASONING", raising=False)
    seen, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [QUESTIONS]})
    usage = UsageTally()

    await paper_extractor(client=client_for(handler), model=MODEL).extract(document(), usage=usage)

    assert sent(seen[0])["reasoning"] == {"effort": "low"}
    assert (usage.provenance() or {})["reasoning_effort"] == "low"


async def test_the_effort_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIDEREAL_GENERATE_REASONING", "high")
    seen, handler = extraction({QUESTIONS_TOOL: [QUESTIONS]})

    await paper_extractor(client=client_for(handler), model=MODEL).repair(
        PaperExtraction.model_validate(PAPER), "unknown variable: PQ"
    )

    assert sent(seen[0])["reasoning"] == {"effort": "high"}


async def test_generating_an_artefact_asks_for_no_particular_effort() -> None:
    """Homework, feedback and plans are writing, not transcription: the model decides."""
    seen, handler = replayer(httpx2.Response(200, json=answered(HOMEWORK)))

    await generator_for(handler).generate(request())

    assert "reasoning" not in json.loads(seen[0].content)


async def test_a_run_that_fails_validation_logs_the_errors_behind_the_retry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """60,000 prompt tokens went on the refused attempt and left no trace of what was wrong."""
    _, handler = extraction({SKELETON_TOOL: [SHAPE], QUESTIONS_TOOL: [UNUSABLE, QUESTIONS]})

    with caplog.at_level(logging.WARNING):
        await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert "questions 1 did not fit the structure" in caplog.text
    assert "number" in caplog.text


async def test_a_refused_strict_mode_is_logged_as_such_with_the_providers_own_words(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A schema that still trips the grammar limit must be visible in the log."""
    seen, handler = replayer(unsupported(), httpx2.Response(200, json=called(HOMEWORK)))

    with caplog.at_level(logging.WARNING):
        await generator_for(handler).generate(request())

    assert len(seen) == 2
    assert "refused strict mode" in caplog.text
    assert "does not support the response_format json_schema parameter" in caplog.text
