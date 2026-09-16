from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from uuid import UUID

import httpx2
import pytest
from anthropic import AsyncAnthropic
from sidereal_core.canonical import CanonicalPaper
from sidereal_core.models import (
    Collection,
    Document,
    DocumentKind,
    GenerationJob,
    GenerationKind,
    JobStatus,
    PaperStatus,
)
from sidereal_core.testing import FAIL_MARKER, FakeDirectus, FakeTypeset
from sidereal_generate.base import GenerationError
from sidereal_generate.claude import AnthropicPaperExtractor, paper_extractor, strict_schema
from sidereal_generate.fake import (
    FakeFeedbackGenerator,
    FakeHomeworkGenerator,
    FakePaperExtractor,
    FakePlanGenerator,
)
from sidereal_generate.jobs import Generators, JobInput, run_job, start_job
from sidereal_generate.models import PaperExtraction
from sidereal_generate.papers import PaperError, paper_worksheet, rerender_paper
from sidereal_generate.prompts import PAPER_TOOL

DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")
Handler = Callable[[httpx2.Request], httpx2.Response]

PAPER_INPUT = {
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
                "stem": "The curve $C$ has equation $y = x^3$.",
                "marks": 5,
                "answer_lines": None,
                "parts": [
                    {
                        "label": "a",
                        "text": "Find $(d y) / (d x)$.",
                        "marks": 2,
                        "answer_lines": 3,
                        "parts": [],
                    }
                ],
            }
        ],
    },
    "mark_scheme": {
        "title": "Pure Mathematics 1: mark scheme",
        "questions": [
            {
                "number": "1",
                "answer": None,
                "notes": None,
                "parts": [{"label": "a", "answer": "$3 x^2$", "marks": 2, "notes": None}],
            }
        ],
    },
}


def generators() -> Generators:
    return Generators(
        homework=FakeHomeworkGenerator(),
        feedback=FakeFeedbackGenerator(),
        plan=FakePlanGenerator(),
        paper=FakePaperExtractor(),
    )


def seeded(text: str = "1. Show that $1 + 1 = 2$.\n2. Differentiate $y = x^2$.") -> FakeDirectus:
    fake = FakeDirectus()
    fake.seed(
        Collection.DOCUMENTS,
        {
            "id": str(DOCUMENT_ID),
            "title": "Mock paper 1",
            "kind": "upload",
            "status": "ready",
            "text": text,
        },
    )
    return fake


async def run(fake: FakeDirectus, typeset: FakeTypeset) -> GenerationJob:
    async with fake.client() as client:
        job = await start_job(
            client, GenerationKind.PAPER_EXTRACT, JobInput(documents=(DOCUMENT_ID,)), model="fake"
        )
        return await run_job(client, generators(), job.id, typeset=typeset.client())


async def extracted(fake: FakeDirectus, typeset: FakeTypeset) -> UUID:
    finished = await run(fake, typeset)
    assert finished.output_id is not None
    return finished.output_id


async def test_a_paper_job_writes_the_paper_its_pdfs_and_its_questions() -> None:
    fake, typeset = seeded(), FakeTypeset()

    finished = await run(fake, typeset)

    assert finished.status is JobStatus.SUCCEEDED
    assert finished.output_collection == "papers"
    assert finished.error is None

    paper = fake.rows(Collection.PAPERS)[0]
    assert paper["id"] == str(finished.output_id)
    assert paper["status"] == PaperStatus.DRAFT.value
    assert paper["document"] == str(DOCUMENT_ID)
    assert paper["structure"]["questions"][0]["number"] == "1"
    assert paper["mark_scheme"]["questions"][0]["number"] == "1"
    assert paper["generated_from"]["job"] == str(finished.id)
    assert paper["generated_from"]["documents"] == [str(DOCUMENT_ID)]
    assert fake.files[paper["rendered_pdf"]][1].startswith(b"%PDF")
    assert fake.files[paper["mark_scheme_pdf"]][1].startswith(b"%PDF")

    questions = fake.rows(Collection.QUESTIONS)
    assert [question["number"] for question in questions] == ["1", "2"]
    assert questions[0]["paper"] == paper["id"]
    assert questions[0]["document"] == str(DOCUMENT_ID)
    assert questions[0]["parts"][0]["label"] == "a"
    assert questions[0]["mark_scheme"]["parts"][0]["answer"] == "$1 + 1 = 2$"
    assert questions[1]["answer_lines"] == 5
    # `Draft.payload()` drops None: a question with no parts writes no `parts`.
    assert "parts" not in questions[1]


async def test_a_render_that_fails_still_files_the_paper_and_the_job_succeeds() -> None:
    fake = seeded()
    typeset = FakeTypeset()

    class Failing:
        model = "fake"

        async def extract(self, document: Document) -> PaperExtraction:
            extraction = await FakePaperExtractor().extract(document)
            return extraction.model_copy(
                update={"paper": extraction.paper.model_copy(update={"title": FAIL_MARKER})}
            )

    async with fake.client() as client:
        job = await start_job(
            client, GenerationKind.PAPER_EXTRACT, JobInput(documents=(DOCUMENT_ID,)), model="fake"
        )
        finished = await run_job(
            client,
            Generators(
                homework=FakeHomeworkGenerator(),
                feedback=FakeFeedbackGenerator(),
                plan=FakePlanGenerator(),
                paper=Failing(),
            ),
            job.id,
            typeset=typeset.client(),
        )

    assert finished.status is JobStatus.SUCCEEDED
    paper = fake.rows(Collection.PAPERS)[0]
    assert "rendered_pdf" not in paper
    assert "render it again" in paper["generated_from"]["warning"]
    assert len(fake.rows(Collection.QUESTIONS)) == 2


async def test_a_document_with_no_text_fails_the_job_with_a_sentence_a_tutor_can_act_on() -> None:
    fake = seeded(text="")

    finished = await run(fake, FakeTypeset())

    assert finished.status is JobStatus.FAILED
    assert finished.error == "That document has no text yet, so there is no paper to read."
    assert fake.rows(Collection.PAPERS) == []


async def test_a_job_that_names_no_single_document_fails_before_anything_is_written() -> None:
    fake = seeded()

    async with fake.client() as client:
        job = await start_job(
            client, GenerationKind.PAPER_EXTRACT, JobInput(documents=()), model="fake"
        )
        finished = await run_job(client, generators(), job.id, typeset=FakeTypeset().client())

    assert finished.status is JobStatus.FAILED
    assert finished.error == "A paper is read from exactly one document."


async def test_rendering_again_replaces_both_pdfs_from_the_stored_structure() -> None:
    fake = seeded()
    typeset = FakeTypeset()
    paper_id = await extracted(fake, typeset)
    stored = fake.items[Collection.PAPERS][str(paper_id)]
    before = stored["rendered_pdf"]
    # A tutor reviews the extraction and corrects a question in Directus.
    stored["structure"]["questions"][0]["stem"] = "Corrected stem."

    async with fake.client() as client:
        paper = await rerender_paper(client, typeset.client(), paper_id)

    assert str(paper.rendered_pdf) != before
    assert paper.mark_scheme_pdf is not None
    last = [call for call in typeset.rendered if call["kind"] == "paper"][-1]
    assert last["document"]["questions"][0]["stem"] == "Corrected stem."


async def test_rendering_a_paper_whose_structure_was_broken_says_which_field() -> None:
    fake = seeded()
    paper_id = await extracted(fake, FakeTypeset())
    fake.items[Collection.PAPERS][str(paper_id)]["structure"]["questions"][0] = {
        "stem": "no number"
    }

    async with fake.client() as client:
        with pytest.raises(PaperError, match=r"questions\.0"):
            await rerender_paper(client, FakeTypeset().client(), paper_id)


async def test_a_worksheet_takes_the_questions_asked_for_in_the_order_asked() -> None:
    fake = seeded()
    typeset = FakeTypeset()
    paper_id = await extracted(fake, typeset)
    student = fake.seed(Collection.STUDENTS, {"name": "A. Tutee"})

    async with fake.client() as client:
        result = await paper_worksheet(
            client,
            typeset.client(),
            paper_id,
            ["2", "1"],
            student_id=UUID(student["id"]),
            title="Week 3",
        )

    document = typeset.rendered[-1]["document"]
    assert typeset.rendered[-1]["kind"] == "worksheet"
    assert [question["number"] for question in document["questions"]] == ["2", "1"]
    assert document["student"] == "A. Tutee"
    assert document["title"] == "Week 3"
    assert "Week 3" in result.source
    assert fake.files[str(result.pdf_file_id)][1].startswith(b"%PDF")


async def test_a_worksheet_asking_for_a_question_the_paper_has_not_got_is_refused() -> None:
    fake = seeded()
    typeset = FakeTypeset()
    paper_id = await extracted(fake, typeset)

    async with fake.client() as client:
        with pytest.raises(PaperError, match="no question 9"):
            await paper_worksheet(client, typeset.client(), paper_id, ["9"])
        with pytest.raises(PaperError, match="at least one"):
            await paper_worksheet(client, typeset.client(), paper_id, [])


async def test_the_fake_extractor_produces_a_paper_the_renderer_accepts() -> None:
    document = Document(
        id=DOCUMENT_ID, title="Mock paper 1", kind=DocumentKind.UPLOAD, text="1. A question."
    )

    extraction = await FakePaperExtractor().extract(document)

    assert extraction.paper.title.startswith("[fake]")
    assert [question.number for question in extraction.paper.questions] == ["1", "2"]
    assert extraction.mark_scheme is not None
    assert CanonicalPaper.model_validate(extraction.paper.model_dump()) == extraction.paper


def test_the_tool_schema_asks_for_every_field() -> None:
    schema = strict_schema(PaperExtraction)

    assert schema["required"] == ["paper", "mark_scheme"]
    question = schema["$defs"]["CanonicalQuestion"]
    assert question["required"] == ["number", "stem", "marks", "parts", "answer_lines"]
    assert question["additionalProperties"] is False


def extractor_for(handler: Handler) -> AnthropicPaperExtractor:
    client = AsyncAnthropic(
        api_key="test-key", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    )
    return AnthropicPaperExtractor(client=client, model="claude-sonnet-5")


def message(tool_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "content": [{"type": "tool_use", "id": "toolu_1", "name": PAPER_TOOL, "input": tool_input}],
        "stop_reason": "tool_use",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def document() -> Document:
    return Document(
        id=DOCUMENT_ID,
        title="Mock paper 1",
        kind=DocumentKind.UPLOAD,
        text="1. The curve $C$ has equation $y = x^3$.",
    )


async def test_one_tool_call_becomes_a_paper_and_its_mark_scheme() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=message(PAPER_INPUT))

    extraction = await extractor_for(handler).extract(document())

    assert extraction.paper.board == "Edexcel"
    assert extraction.mark_scheme is not None
    assert extraction.mark_scheme.questions[0].parts[0].answer == "$3 x^2$"

    sent = json.loads(seen[0].content)
    assert sent["tool_choice"] == {"type": "tool", "name": PAPER_TOOL}
    assert sent["tools"][0]["strict"] is True
    assert "numbering" in sent["system"].lower()
    assert "Typst" in sent["system"]
    assert "The curve $C$" in sent["messages"][0]["content"]


async def test_a_payload_that_does_not_validate_is_asked_for_once_more_with_the_errors() -> None:
    seen: list[httpx2.Request] = []
    replies = [
        message({"paper": {"title": "x", "questions": [{}]}, "mark_scheme": None}),
        message(PAPER_INPUT),
    ]

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json=replies[min(len(seen) - 1, len(replies) - 1)])

    extraction = await extractor_for(handler).extract(document())

    assert extraction.paper.title == "Pure Mathematics 1"
    assert len(seen) == 2
    retried = json.loads(seen[1].content)["messages"][0]["content"]
    assert "did not fit the structure" in retried
    assert "number" in retried


async def test_a_second_unusable_payload_is_a_generation_error() -> None:
    body = message({"paper": {"title": "x", "questions": [{}]}, "mark_scheme": None})

    with pytest.raises(GenerationError, match="unusable paper"):
        await extractor_for(lambda _: httpx2.Response(200, json=body)).extract(document())


async def test_a_reply_with_no_tool_call_is_a_generation_error() -> None:
    body = {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "content": [{"type": "text", "text": "I would rather not."}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }

    with pytest.raises(GenerationError, match="did not call"):
        await extractor_for(lambda _: httpx2.Response(200, json=body)).extract(document())


def test_building_an_extractor_needs_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert paper_extractor().model


def test_generators_report_the_extractors_model() -> None:
    assert generators().for_kind(GenerationKind.PAPER_EXTRACT) == "fake"
