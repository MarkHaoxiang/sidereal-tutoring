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
    PAPER_PAGES_PROMPT,
    PAPER_TOOL,
)
from sidereal_generate.settings import DEFAULT_EXTRACT_MAX_TOKENS
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
DRAWN_PAPER: dict[str, Any] = {
    **PAPER,
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
MARK_SCHEME: dict[str, Any] = {
    "mark_scheme": {
        "title": "Pure Mathematics 1: mark scheme",
        "questions": [{"number": "1", "answer": "$3 x^2$"}],
    }
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


async def test_one_answer_becomes_a_paper() -> None:
    seen, handler = replayer(httpx2.Response(200, json=answered(PAPER)))

    extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert extraction.paper.board == "Edexcel"

    sent = json.loads(seen[0].content)
    assert sent["response_format"]["json_schema"]["name"] == PAPER_TOOL
    assert "numbering" in sent["messages"][0]["content"].lower()
    assert "$y = x^3$" in sent["messages"][1]["content"]


async def test_a_paper_that_does_not_validate_is_asked_for_once_more_with_the_errors() -> None:
    seen, handler = replayer(
        httpx2.Response(200, json=answered({"paper": {"title": "x", "questions": [{}]}})),
        httpx2.Response(200, json=answered(PAPER)),
    )

    extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert extraction.paper.title == "Pure Mathematics 1"
    assert len(seen) == 2
    retried = json.loads(seen[1].content)["messages"][1]["content"]
    assert "did not fit the structure" in retried
    assert "number" in retried


async def test_a_second_unusable_paper_is_a_generation_error() -> None:
    _, handler = replayer(
        httpx2.Response(200, json=answered({"paper": {"title": "x", "questions": [{}]}}))
    )

    with pytest.raises(GenerationError, match="unusable paper"):
        await paper_extractor(client=client_for(handler), model=MODEL).extract(document())


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


async def test_a_paper_asks_for_the_larger_output_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """A whole transcribed paper is the longest answer asked for, and is budgeted as one."""
    monkeypatch.delenv("SIDEREAL_GENERATE_EXTRACT_MAX_TOKENS", raising=False)
    monkeypatch.delenv("SIDEREAL_GENERATE_MAX_TOKENS", raising=False)
    seen, handler = replayer(httpx2.Response(200, json=answered(PAPER)))

    await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert json.loads(seen[0].content)["max_tokens"] == DEFAULT_EXTRACT_MAX_TOKENS


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
    """The tokens are spent whether or not an answer comes back."""
    body = cut_off()
    body["usage"] = {"prompt_tokens": 10, "completion_tokens": 20000, "total_tokens": 20010}
    _, handler = replayer(httpx2.Response(200, json=body))
    usage = UsageTally()

    with pytest.raises(GenerationTruncatedError):
        await generator_for(handler).generate(request(), usage=usage)

    assert usage.completion_tokens == 20000


async def test_an_unpriced_call_files_no_price() -> None:
    """A total that silently covered only some calls would be worse than none."""
    body = answered(HOMEWORK)
    body["usage"] = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    _, handler = replayer(httpx2.Response(200, json=body))
    usage = UsageTally()

    await generator_for(handler).generate(request(), usage=usage)

    assert "cost_usd" not in (usage.provenance() or {})


async def test_a_repair_asks_for_the_same_schema_with_the_diagnostics() -> None:
    seen, handler = replayer(httpx2.Response(200, json=answered(PAPER)))
    extraction = PaperExtraction.model_validate(PAPER)

    repaired = await paper_extractor(client=client_for(handler), model=MODEL).repair(
        extraction, "line 219, column 42: unknown variable: PQ"
    )

    assert repaired.paper.title == "Pure Mathematics 1"
    sent = json.loads(seen[0].content)
    assert sent["response_format"]["json_schema"]["name"] == PAPER_TOOL
    assert "does not compile" in sent["messages"][0]["content"]
    assert "unknown variable: PQ" in sent["messages"][1]["content"]
    assert "Pure Mathematics 1" in sent["messages"][1]["content"]


async def test_a_mark_scheme_is_a_call_of_its_own_carrying_the_paper_numbering() -> None:
    seen, handler = replayer(httpx2.Response(200, json=answered(MARK_SCHEME)))
    scheme = Document(
        id=UUID("33333333-3333-4333-8333-333333333333"),
        title="Mark scheme",
        kind=DocumentKind.UPLOAD,
        text="1 (a) $3 x^2$ (2)",
    )
    paper = PaperExtraction.model_validate(PAPER).paper

    extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract_mark_scheme(
        scheme, paper
    )

    assert extraction.mark_scheme.questions[0].answer == "$3 x^2$"
    sent = json.loads(seen[0].content)
    assert sent["response_format"]["json_schema"]["name"] == MARK_SCHEME_TOOL
    assert sent["response_format"]["json_schema"]["schema"] == strict_schema(MarkSchemeExtraction)
    prompt = sent["messages"][1]["content"]
    assert "<mark_scheme" in prompt
    assert "$3 x^2$" in prompt
    assert '<question number="1"' in prompt


def test_the_paper_call_and_the_mark_scheme_call_carry_only_their_own_defs() -> None:
    """Strict mode compiles a grammar per schema, and a whole paper's was too large for one."""
    paper = strict_schema(PaperExtraction)["$defs"]
    scheme = strict_schema(MarkSchemeExtraction)["$defs"]

    assert not [name for name in paper if name.startswith("CanonicalMarkScheme")]
    assert "CanonicalPaper" not in scheme
    assert "CanonicalSection" not in scheme


async def test_a_mark_scheme_that_does_not_validate_is_asked_for_once_more() -> None:
    seen, handler = replayer(
        httpx2.Response(200, json=answered({"mark_scheme": {"questions": [{}]}})),
        httpx2.Response(200, json=answered(MARK_SCHEME)),
    )
    paper = PaperExtraction.model_validate(PAPER).paper

    extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract_mark_scheme(
        document(), paper
    )

    assert extraction.mark_scheme.title == "Pure Mathematics 1: mark scheme"
    assert "mark scheme again" in json.loads(seen[1].content)["messages"][1]["content"]


async def test_a_second_unusable_mark_scheme_is_a_generation_error() -> None:
    _, handler = replayer(httpx2.Response(200, json=answered({"mark_scheme": {"questions": [{}]}})))
    paper = PaperExtraction.model_validate(PAPER).paper

    with pytest.raises(GenerationError, match="unusable mark scheme"):
        await paper_extractor(client=client_for(handler), model=MODEL).extract_mark_scheme(
            document(), paper
        )


async def test_a_mark_scheme_repair_addresses_the_scheme_alone() -> None:
    seen, handler = replayer(httpx2.Response(200, json=answered(MARK_SCHEME)))
    extraction = MarkSchemeExtraction.model_validate(MARK_SCHEME)

    await paper_extractor(client=client_for(handler), model=MODEL).repair_mark_scheme(
        extraction, "line 3, column 1: unknown variable: PQ"
    )

    sent = json.loads(seen[0].content)
    assert sent["response_format"]["json_schema"]["name"] == MARK_SCHEME_TOOL
    assert "mark scheme you returned does not compile" in sent["messages"][0]["content"]
    assert "unknown variable: PQ" in sent["messages"][1]["content"]


async def test_a_field_the_model_sent_as_json_text_is_parsed_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The live failure: the forced tool call is unconstrained, and `paper` arrived as a string."""
    stringified = {"paper": json.dumps(PAPER["paper"]), "figures": []}
    _, handler = replayer(
        unsupported(), httpx2.Response(200, json=called(stringified, name=PAPER_TOOL))
    )

    with caplog.at_level(logging.WARNING):
        extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract(
            document()
        )

    assert extraction.paper.title == "Pure Mathematics 1"
    assert "PaperExtraction stringified paper" in caplog.text


async def test_a_nested_field_sent_as_json_text_is_parsed_too() -> None:
    nested = {**PAPER["paper"], "questions": json.dumps(PAPER["paper"]["questions"])}
    _, handler = replayer(httpx2.Response(200, json=answered({"paper": nested, "figures": []})))

    extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert [question.number for question in extraction.paper.questions] == ["1"]


async def test_a_string_that_is_not_an_object_is_still_refused() -> None:
    """The helper never swallows a real error: only JSON that parses to an object is parsed."""
    _, handler = replayer(
        httpx2.Response(200, json=answered({"paper": "the paper", "figures": []}))
    )

    with pytest.raises(GenerationError, match="unusable paper"):
        await paper_extractor(client=client_for(handler), model=MODEL).extract(document())


async def test_a_field_that_legitimately_holds_a_string_is_left_alone() -> None:
    """A stem that happens to read as JSON is the paper's own text, not a stringified object."""
    quoted = {
        **PAPER["paper"],
        "questions": [{**PAPER["paper"]["questions"][0], "stem": '{"a": 1}'}],
    }
    _, handler = replayer(httpx2.Response(200, json=answered({"paper": quoted, "figures": []})))

    extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert extraction.paper.questions[0].stem == '{"a": 1}'


async def test_a_refused_strict_mode_is_logged_as_such_with_the_providers_own_words(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A shrunk schema that still trips the grammar limit must be visible in the log."""
    seen, handler = replayer(unsupported(), httpx2.Response(200, json=called(HOMEWORK)))

    with caplog.at_level(logging.WARNING):
        await generator_for(handler).generate(request())

    assert len(seen) == 2
    assert "refused strict mode" in caplog.text
    assert "does not support the response_format json_schema parameter" in caplog.text


async def test_an_extraction_asks_for_little_thinking_and_files_which(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Transcription does not need deep reasoning, and reasoning is spent from the answer."""
    monkeypatch.delenv("SIDEREAL_GENERATE_REASONING", raising=False)
    body = answered(PAPER)
    body["usage"] = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    seen, handler = replayer(httpx2.Response(200, json=body))
    usage = UsageTally()

    await paper_extractor(client=client_for(handler), model=MODEL).extract(document(), usage=usage)

    assert json.loads(seen[0].content)["reasoning"] == {"effort": "low"}
    assert (usage.provenance() or {})["reasoning_effort"] == "low"


async def test_the_effort_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIDEREAL_GENERATE_REASONING", "high")
    seen, handler = replayer(httpx2.Response(200, json=answered(PAPER)))

    await paper_extractor(client=client_for(handler), model=MODEL).repair(
        PaperExtraction.model_validate(PAPER), "unknown variable: PQ"
    )

    assert json.loads(seen[0].content)["reasoning"] == {"effort": "high"}


async def test_generating_an_artefact_asks_for_no_particular_effort() -> None:
    """Homework, feedback and plans are writing, not transcription: the model decides."""
    seen, handler = replayer(httpx2.Response(200, json=answered(HOMEWORK)))

    await generator_for(handler).generate(request())

    assert "reasoning" not in json.loads(seen[0].content)


async def test_page_images_go_up_with_the_pages_prompt_and_are_counted() -> None:
    body = answered(PAPER)
    body["usage"] = {
        "prompt_tokens": 4000,
        "completion_tokens": 20,
        "total_tokens": 4020,
        "prompt_tokens_details": {"cached_tokens": 0, "image_tokens": 2600},
    }
    seen, handler = replayer(httpx2.Response(200, json=body))
    usage = UsageTally()

    await paper_extractor(client=client_for(handler), model=MODEL).extract(
        document(), pages=[b"\xff\xd8one", b"\xff\xd8two"], usage=usage
    )

    sent = json.loads(seen[0].content)
    assert sent["messages"][0]["content"] == PAPER_PAGES_PROMPT
    parts = sent["messages"][1]["content"]
    assert [part["type"] for part in parts] == ["image_url", "image_url", "text"]
    assert parts[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert (usage.provenance() or {})["images"] == 2
    assert (usage.provenance() or {})["image_tokens"] == 2600


async def test_a_gateway_that_prices_no_images_still_counts_the_pages() -> None:
    _, handler = replayer(httpx2.Response(200, json=answered(PAPER)))
    usage = UsageTally()

    await paper_extractor(client=client_for(handler), model=MODEL).extract(
        document(), pages=[b"\xff\xd8one"], usage=usage
    )

    provenance = usage.provenance() or {}
    assert provenance["images"] == 1
    assert "image_tokens" not in provenance


async def test_a_retried_extraction_sends_the_same_pages_again() -> None:
    replies = [
        httpx2.Response(200, json=answered({"paper": {"title": "x", "questions": [{}]}})),
        httpx2.Response(200, json=answered(PAPER)),
    ]
    seen, handler = replayer(*replies)

    extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract(
        document(), pages=[b"\xff\xd8one"]
    )

    assert extraction.paper.title == "Pure Mathematics 1"
    retried = json.loads(seen[1].content)["messages"][1]["content"]
    assert [part["type"] for part in retried] == ["image_url", "text"]
    assert "did not fit the structure" in retried[-1]["text"]


def prompt_of(request: httpx2.Request) -> str:
    """The text the model reads, whether it went up alone or behind the page images."""
    content = json.loads(request.content)["messages"][1]["content"]
    return content if isinstance(content, str) else content[-1]["text"]


async def test_a_paper_that_omits_figures_is_refused_rather_than_read_as_none() -> None:
    """An omitted key and a paper with no figures must not look the same."""
    omitted = {"paper": PAPER["paper"]}
    seen, handler = replayer(
        httpx2.Response(200, json=answered(omitted)),
        httpx2.Response(200, json=answered(PAPER)),
    )

    with pytest.raises(ValidationError, match="figures"):
        PaperExtraction.model_validate(omitted)

    extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert extraction.figures == ()
    assert len(seen) == 2
    assert "figures" in prompt_of(seen[1])


async def test_the_drawn_page_numbers_reach_the_extraction_and_its_retry() -> None:
    seen, handler = replayer(
        httpx2.Response(200, json=answered({"paper": {"title": "x", "questions": [{}]}})),
        httpx2.Response(200, json=answered(DRAWN_PAPER)),
    )

    extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract(
        document(), pages=[b"\xff\xd8one", b"\xff\xd8two", b"\xff\xd8three"], drawn=[2, 3]
    )

    assert len(extraction.figures) == 1
    assert len(seen) == 2
    for request in seen:
        assert "2, 3" in prompt_of(request)


async def test_a_drawn_paper_that_came_back_with_no_figures_is_asked_once_more() -> None:
    """A second empty answer is taken: a drawn page can be page furniture."""
    seen, handler = replayer(httpx2.Response(200, json=answered(PAPER)))

    extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract(
        document(), pages=[b"\xff\xd8one"], drawn=[1]
    )

    assert extraction.figures == ()
    assert len(seen) == 2
    assert "returned no figures" in prompt_of(seen[1])


async def test_a_paper_that_answered_with_figures_is_asked_only_once() -> None:
    seen, handler = replayer(httpx2.Response(200, json=answered(DRAWN_PAPER)))

    extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract(
        document(), pages=[b"\xff\xd8one", b"\xff\xd8two"], drawn=[2]
    )

    assert [figure.page for figure in extraction.figures] == [2]
    assert len(seen) == 1


async def test_an_extraction_with_no_page_images_is_never_asked_about_figures() -> None:
    seen, handler = replayer(httpx2.Response(200, json=answered(PAPER)))
    extractor = paper_extractor(client=client_for(handler), model=MODEL)

    await extractor.extract(document())
    # Drawn pages nobody sent the images of say nothing about the figures.
    await extractor.extract(document(), drawn=[1, 2])
    # Page images of a paper with nothing drawn on them do not either.
    await extractor.extract(document(), pages=[b"\xff\xd8one"])

    assert len(seen) == 3
    assert all("returned no figures" not in prompt_of(request) for request in seen)


async def test_a_second_ask_that_is_unusable_keeps_the_paper_that_validated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    seen, handler = replayer(
        httpx2.Response(200, json=answered(PAPER)),
        httpx2.Response(200, json=answered({"paper": {"title": "x", "questions": [{}]}})),
    )

    with caplog.at_level(logging.WARNING):
        extraction = await paper_extractor(client=client_for(handler), model=MODEL).extract(
            document(), pages=[b"\xff\xd8one"], drawn=[1]
        )

    assert extraction.paper.title == "Pure Mathematics 1"
    assert len(seen) == 2
    assert "second ask for figures" in caplog.text


async def test_a_payload_that_fails_validation_logs_the_errors_behind_the_retry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """60,000 prompt tokens went on the refused attempt and left no trace of what was wrong."""
    _, handler = replayer(
        httpx2.Response(200, json=answered({"paper": {"title": "x", "questions": [{}]}})),
        httpx2.Response(200, json=answered(PAPER)),
    )

    with caplog.at_level(logging.WARNING):
        await paper_extractor(client=client_for(handler), model=MODEL).extract(document())

    assert "emit_paper returned an unusable paper" in caplog.text
    assert "number" in caplog.text


async def test_a_mark_scheme_that_fails_validation_logs_the_errors_too(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, handler = replayer(
        httpx2.Response(200, json=answered({"mark_scheme": {"questions": [{}]}})),
        httpx2.Response(200, json=answered(MARK_SCHEME)),
    )
    paper = PaperExtraction.model_validate(PAPER).paper

    with caplog.at_level(logging.WARNING):
        await paper_extractor(client=client_for(handler), model=MODEL).extract_mark_scheme(
            document(), paper
        )

    assert "emit_mark_scheme returned an unusable mark scheme" in caplog.text
    assert "title" in caplog.text
