from __future__ import annotations

import json
import logging
from collections.abc import Callable, Sequence
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
from sidereal_generate.base import GenerationError, strict_schema
from sidereal_generate.chunks import MarkSchemeBatch, PaperSkeleton, QuestionBatch
from sidereal_generate.claude import (
    NON_STREAMING_MAX_TOKENS,
    AnthropicPaperExtractor,
    paper_extractor,
)
from sidereal_generate.fake import (
    FakeFeedbackGenerator,
    FakeHomeworkGenerator,
    FakePaperExtractor,
    FakePlanGenerator,
)
from sidereal_generate.jobs import Generators, JobInput, run_job, start_job
from sidereal_generate.models import MarkSchemeExtraction, PaperExtraction
from sidereal_generate.papers import PaperError, paper_worksheet, rerender_paper
from sidereal_generate.prompts import MARK_SCHEME_TOOL, QUESTIONS_TOOL, SKELETON_TOOL
from sidereal_generate.usage import UsageTally

DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")
SCHEME_ID = UUID("33333333-3333-4333-8333-333333333333")
Handler = Callable[[httpx2.Request], httpx2.Response]

PAPER_INPUT: dict[str, Any] = {
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
    "figures": [],
}
SCHEME_INPUT: dict[str, Any] = {
    "questions": [{"number": "1", "parts": [{"label": "a", "answer": "$3 x^2$", "marks": 2}]}]
}
SHAPE_INPUT: dict[str, Any] = {
    "title": "Pure Mathematics 1",
    "source": "Edexcel 2025",
    "board": "Edexcel",
    "year": 2025,
    "time_minutes": 90,
    "total_marks": 75,
    "instructions": None,
    "questions": [
        {"number": "1", "stem": "Differentiation", "page": 1, "has_material": False, "marks": 5}
    ],
    "sections": [],
    "passages": [],
}
QUESTIONS_INPUT: dict[str, Any] = {
    "questions": [
        {
            "number": "1",
            "stem": "The curve $C$ has equation $y = x^3$.",
            "marks": 5,
            "parts": [
                {
                    "label": "a",
                    "text": "Find $(d y) / (d x)$.",
                    "marks": 2,
                    "answer": {"type": "lines", "lines": 3},
                }
            ],
        }
    ],
    "figures": [],
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


def seeded_with_scheme() -> FakeDirectus:
    fake = seeded()
    fake.seed(
        Collection.DOCUMENTS,
        {
            "id": str(SCHEME_ID),
            "title": "Mock paper 1 mark scheme",
            "kind": "upload",
            "status": "ready",
            "text": "1 (a) $3 x^2$ (2)",
        },
    )
    return fake


async def run(
    fake: FakeDirectus,
    typeset: FakeTypeset,
    documents: tuple[UUID, ...] = (DOCUMENT_ID, SCHEME_ID),
) -> GenerationJob:
    async with fake.client() as client:
        job = await start_job(
            client, GenerationKind.PAPER_EXTRACT, JobInput(documents=documents), model="fake"
        )
        return await run_job(client, generators(), job.id, typeset=typeset.client())


async def extracted(
    fake: FakeDirectus,
    typeset: FakeTypeset,
    documents: tuple[UUID, ...] = (DOCUMENT_ID, SCHEME_ID),
) -> UUID:
    finished = await run(fake, typeset, documents)
    assert finished.output_id is not None
    return finished.output_id


async def test_a_paper_job_writes_the_paper_its_pdfs_and_its_questions() -> None:
    fake, typeset = seeded_with_scheme(), FakeTypeset()

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
    assert paper["generated_from"]["documents"] == [str(DOCUMENT_ID), str(SCHEME_ID)]
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

    class Failing(FakePaperExtractor):
        async def extract(
            self,
            document: Document,
            *,
            pages: Sequence[bytes] = (),
            drawn: Sequence[int] = (),
            usage: UsageTally | None = None,
        ) -> PaperExtraction:
            extraction = await super().extract(document, pages=pages, usage=usage)
            return extraction.model_copy(
                update={"paper": extraction.paper.model_copy(update={"title": FAIL_MARKER})}
            )

        async def repair(
            self,
            extraction: PaperExtraction,
            diagnostics: str,
            *,
            usage: UsageTally | None = None,
        ) -> PaperExtraction:
            return extraction

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

    finished = await run(fake, FakeTypeset(), (DOCUMENT_ID,))

    assert finished.status is JobStatus.FAILED
    assert finished.error == "That document has no text yet, so there is no paper to read."
    assert fake.rows(Collection.PAPERS) == []


async def test_a_job_that_names_no_document_fails_before_anything_is_written() -> None:
    fake = seeded()

    async with fake.client() as client:
        job = await start_job(
            client, GenerationKind.PAPER_EXTRACT, JobInput(documents=()), model="fake"
        )
        finished = await run_job(client, generators(), job.id, typeset=FakeTypeset().client())

    assert finished.status is JobStatus.FAILED
    assert finished.error == "A paper is read from one document, or two with its mark scheme."


async def test_rendering_again_replaces_both_pdfs_from_the_stored_structure() -> None:
    fake = seeded_with_scheme()
    typeset = FakeTypeset()
    paper_id = await extracted(fake, typeset)
    stored = fake.items[Collection.PAPERS][str(paper_id)]
    before = stored["rendered_pdf"]
    # A tutor reviews the extraction and corrects a question in Directus.
    stored["structure"]["questions"][0]["stem"] = "Corrected stem."

    async with fake.client() as client:
        paper = await rerender_paper(client, typeset.client(), paper_id, FakePaperExtractor())

    assert str(paper.rendered_pdf) != before
    assert paper.mark_scheme_pdf is not None
    last = [call for call in typeset.rendered if call["kind"] == "paper"][-1]
    assert last["document"]["questions"][0]["stem"] == "Corrected stem."


async def test_rendering_a_paper_whose_structure_was_broken_says_which_field() -> None:
    fake = seeded()
    paper_id = await extracted(fake, FakeTypeset(), (DOCUMENT_ID,))
    fake.items[Collection.PAPERS][str(paper_id)]["structure"]["questions"][0] = {
        "stem": "no number"
    }

    async with fake.client() as client:
        with pytest.raises(PaperError, match=r"questions\.0"):
            await rerender_paper(client, FakeTypeset().client(), paper_id, FakePaperExtractor())


async def test_a_worksheet_takes_the_questions_asked_for_in_the_order_asked() -> None:
    fake = seeded()
    typeset = FakeTypeset()
    paper_id = await extracted(fake, typeset, (DOCUMENT_ID,))
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
    paper_id = await extracted(fake, typeset, (DOCUMENT_ID,))

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
    scheme = await FakePaperExtractor().extract_mark_scheme(document, extraction.paper)

    assert extraction.paper.title.startswith("[fake]")
    assert [question.number for question in extraction.paper.questions] == ["1", "2"]
    assert scheme.mark_scheme.title.startswith("[fake]")
    assert CanonicalPaper.model_validate(extraction.paper.model_dump()) == extraction.paper


def test_the_batch_schema_asks_for_every_field() -> None:
    """A strict schema has no optional properties, whatever default the model carries."""
    schema = strict_schema(QuestionBatch)

    assert schema["required"] == ["figures", "questions"]
    question = schema["$defs"]["BatchQuestion"]
    assert question["required"] == ["number", "stem", "marks", "answer", "parts"]
    assert question["additionalProperties"] is False


def extractor_for(handler: Handler) -> AnthropicPaperExtractor:
    client = AsyncAnthropic(
        api_key="test-key", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    )
    return AnthropicPaperExtractor(client=client, model="claude-sonnet-5")


def message(tool_input: dict[str, Any], *, name: str = QUESTIONS_TOOL) -> dict[str, Any]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-5",
        "content": [{"type": "tool_use", "id": "toolu_1", "name": name, "input": tool_input}],
        "stop_reason": "tool_use",
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def extraction(replies: dict[str, list[dict[str, Any]]]) -> tuple[list[httpx2.Request], Handler]:
    """Answers each forced tool call with the next payload queued for its name."""
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        name = json.loads(request.content)["tools"][0]["name"]
        queue = replies[name]
        payload = queue.pop(0) if len(queue) > 1 else queue[0]
        return httpx2.Response(200, json=message(payload, name=name))

    return seen, handler


def document() -> Document:
    return Document(
        id=DOCUMENT_ID,
        title="Mock paper 1",
        kind=DocumentKind.UPLOAD,
        text="1. The curve $C$ has equation $y = x^3$.",
    )


async def test_each_call_is_a_forced_strict_tool_call_of_its_own() -> None:
    seen, handler = extraction({SKELETON_TOOL: [SHAPE_INPUT], QUESTIONS_TOOL: [QUESTIONS_INPUT]})

    extraction_read = await extractor_for(handler).extract(document())

    assert extraction_read.paper.board == "Edexcel"
    sent = [json.loads(request.content) for request in seen]
    assert [body["tools"][0]["name"] for body in sent] == [SKELETON_TOOL, QUESTIONS_TOOL]
    assert all(body["tools"][0]["strict"] is True for body in sent)
    assert sent[0]["tools"][0]["input_schema"] == strict_schema(PaperSkeleton)
    assert sent[1]["tools"][0]["input_schema"] == strict_schema(QuestionBatch)
    assert sent[0]["tool_choice"] == {"type": "tool", "name": SKELETON_TOOL}
    assert "The curve $C$" in sent[0]["messages"][0]["content"]


async def test_the_mark_scheme_is_a_call_of_its_own_against_its_own_schema() -> None:
    seen, handler = extraction({MARK_SCHEME_TOOL: [SCHEME_INPUT]})
    paper = PaperExtraction.model_validate(PAPER_INPUT).paper

    read = await extractor_for(handler).extract_mark_scheme(document(), paper)

    assert read.mark_scheme.questions[0].parts[0].answer == "$3 x^2$"
    sent = json.loads(seen[0].content)
    assert sent["tools"][0]["input_schema"] == strict_schema(MarkSchemeBatch)
    assert '<part number="1" label="a" marks="2"/>' in sent["messages"][0]["content"]


async def test_a_batch_field_sent_as_json_text_is_parsed_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The live failure: an unconstrained tool call returned a field as a JSON string."""
    stringified = {"questions": json.dumps(QUESTIONS_INPUT["questions"]), "figures": []}
    _, handler = extraction({SKELETON_TOOL: [SHAPE_INPUT], QUESTIONS_TOOL: [stringified]})

    with caplog.at_level(logging.WARNING):
        read = await extractor_for(handler).extract(document())

    assert read.paper.questions[0].parts[0].label == "a"
    assert "QuestionBatch stringified questions" in caplog.text


async def test_a_batch_that_does_not_validate_is_asked_for_once_more_with_the_errors() -> None:
    seen, handler = extraction(
        {
            SKELETON_TOOL: [SHAPE_INPUT],
            QUESTIONS_TOOL: [{"questions": [{}], "figures": []}, QUESTIONS_INPUT],
        }
    )

    read = await extractor_for(handler).extract(document())

    assert read.paper.questions[0].number == "1"
    assert len(seen) == 3
    retried = json.loads(seen[2].content)["messages"][0]["content"]
    assert "did not fit the structure" in retried
    assert "number" in retried


async def test_a_second_unusable_batch_is_a_generation_error() -> None:
    _, handler = extraction(
        {SKELETON_TOOL: [SHAPE_INPUT], QUESTIONS_TOOL: [{"questions": [{}], "figures": []}]}
    )

    with pytest.raises(GenerationError, match="could not be read after two tries"):
        await extractor_for(handler).extract(document())


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


async def test_an_extraction_never_asks_anthropic_for_more_than_it_answers_unstreamed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SDK refuses a non-streaming request above its ceiling, and nothing here streams."""
    monkeypatch.setenv("SIDEREAL_GENERATE_EXTRACT_MAX_TOKENS", "128000")
    seen, handler = extraction({SKELETON_TOOL: [SHAPE_INPUT], QUESTIONS_TOOL: [QUESTIONS_INPUT]})

    await extractor_for(handler).extract(document())

    assert json.loads(seen[0].content)["max_tokens"] == NON_STREAMING_MAX_TOKENS


class Recorder(FakePaperExtractor):
    """An extractor that says what it was handed, and repairs by dropping the fail marker."""

    def __init__(self) -> None:
        self.seen: list[str] = []
        self.schemes: list[tuple[str, str]] = []
        self.repairs: list[str] = []
        self.scheme_repairs: list[str] = []
        self.fail_once = False
        self.fail_scheme = False

    async def extract(
        self,
        document: Document,
        *,
        pages: Sequence[bytes] = (),
        drawn: Sequence[int] = (),
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        self.seen.append(document.title)
        if usage is not None:
            usage.record(prompt_tokens=100, completion_tokens=20, reasoning_tokens=5, cost_usd=0.25)
        extraction = await super().extract(document, pages=pages, usage=None)
        if not self.fail_once:
            return extraction
        return extraction.model_copy(
            update={"paper": extraction.paper.model_copy(update={"title": FAIL_MARKER})}
        )

    async def extract_mark_scheme(
        self,
        document: Document,
        paper: CanonicalPaper,
        *,
        usage: UsageTally | None = None,
    ) -> MarkSchemeExtraction:
        self.schemes.append((document.title, paper.title))
        extraction = await super().extract_mark_scheme(document, paper, usage=usage)
        if not self.fail_scheme:
            return extraction
        return extraction.model_copy(
            update={"mark_scheme": extraction.mark_scheme.model_copy(update={"title": FAIL_MARKER})}
        )

    async def repair(
        self,
        extraction: PaperExtraction,
        diagnostics: str,
        *,
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        self.repairs.append(diagnostics)
        if usage is not None:
            usage.record(prompt_tokens=50, completion_tokens=10, cost_usd=0.25)
        return extraction.model_copy(
            update={
                "paper": extraction.paper.model_copy(
                    update={"title": extraction.paper.title.replace(FAIL_MARKER, "repaired")}
                )
            }
        )

    async def repair_mark_scheme(
        self,
        extraction: MarkSchemeExtraction,
        diagnostics: str,
        *,
        usage: UsageTally | None = None,
    ) -> MarkSchemeExtraction:
        self.scheme_repairs.append(diagnostics)
        return extraction.model_copy(
            update={
                "mark_scheme": extraction.mark_scheme.model_copy(
                    update={"title": extraction.mark_scheme.title.replace(FAIL_MARKER, "repaired")}
                )
            }
        )


def with_extractor(extractor: Recorder) -> Generators:
    return Generators(
        homework=FakeHomeworkGenerator(),
        feedback=FakeFeedbackGenerator(),
        plan=FakePlanGenerator(),
        paper=extractor,
    )


async def run_with(
    fake: FakeDirectus, typeset: FakeTypeset, extractor: Recorder, documents: tuple[UUID, ...]
) -> GenerationJob:
    async with fake.client() as client:
        job = await start_job(
            client, GenerationKind.PAPER_EXTRACT, JobInput(documents=documents), model="fake"
        )
        return await run_job(client, with_extractor(extractor), job.id, typeset=typeset.client())


async def test_a_second_document_reaches_the_extractor_as_the_mark_scheme() -> None:
    fake, extractor = seeded_with_scheme(), Recorder()

    finished = await run_with(fake, FakeTypeset(), extractor, (DOCUMENT_ID, SCHEME_ID))

    assert finished.status is JobStatus.SUCCEEDED
    assert extractor.seen == ["Mock paper 1"]
    # The paper is read first, and is the context the scheme is read under.
    assert extractor.schemes == [("Mock paper 1 mark scheme", "[fake] Mock paper 1")]


async def test_a_paper_alone_makes_no_mark_scheme_call() -> None:
    fake, extractor = seeded(), Recorder()

    await run_with(fake, FakeTypeset(), extractor, (DOCUMENT_ID,))

    assert extractor.seen == ["Mock paper 1"]
    assert extractor.schemes == []


async def test_a_mark_scheme_the_compiler_refuses_is_repaired_on_its_own(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake, extractor = seeded_with_scheme(), Recorder()
    extractor.fail_scheme = True

    with caplog.at_level(logging.WARNING):
        finished = await run_with(fake, FakeTypeset(), extractor, (DOCUMENT_ID, SCHEME_ID))

    assert finished.status is JobStatus.SUCCEEDED
    # The log says which document failed: the paper compiled, and only the scheme did not.
    assert "the mark scheme did not compile" in caplog.text
    assert "the paper did not compile" not in caplog.text
    assert extractor.scheme_repairs  # the scheme's own diagnostics
    assert extractor.repairs == []  # and the paper was never asked for again
    paper = fake.rows(Collection.PAPERS)[0]
    assert paper["structure"]["title"] == "[fake] Mock paper 1"
    assert FAIL_MARKER not in paper["mark_scheme"]["title"]
    assert paper["rendered_pdf"]
    assert paper["mark_scheme_pdf"]


async def test_source_the_compiler_refuses_is_repaired_against_its_diagnostics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake, extractor = seeded(), Recorder()
    extractor.fail_once = True

    with caplog.at_level(logging.WARNING):
        finished = await run_with(fake, FakeTypeset(), extractor, (DOCUMENT_ID,))

    assert finished.status is JobStatus.SUCCEEDED
    assert "the paper did not compile" in caplog.text
    assert len(extractor.repairs) == 1
    assert extractor.repairs[0]  # the compiler's own report, not a summary of it
    paper = fake.rows(Collection.PAPERS)[0]
    # What compiled is what is stored, so the tutor's next render starts from it.
    assert FAIL_MARKER not in paper["structure"]["title"]
    assert paper["rendered_pdf"]
    assert "warning" not in paper["generated_from"]


async def test_a_job_files_what_its_calls_cost() -> None:
    fake, extractor = seeded(), Recorder()
    extractor.fail_once = True

    await run_with(fake, FakeTypeset(), extractor, (DOCUMENT_ID,))

    usage = fake.rows(Collection.PAPERS)[0]["generated_from"]["usage"]
    # The extraction and the repair are both the job's cost.
    assert usage["calls"] == 2
    assert usage["prompt_tokens"] == 150
    assert usage["completion_tokens"] == 30
    assert usage["total_tokens"] == 180
    assert usage["reasoning_tokens"] == 5
    assert usage["cost_usd"] == 0.5


async def test_a_render_that_works_clears_an_earlier_failure_warning() -> None:
    fake, extractor = seeded(), Recorder()
    extractor.fail_once = True
    typeset = FakeTypeset()
    # The extraction's renders all fail, so the row is filed with the warning.
    finished = await run_with(fake, typeset, extractor, (DOCUMENT_ID,))
    paper_id = finished.output_id
    assert paper_id is not None
    stored = fake.items[Collection.PAPERS][str(paper_id)]
    stored["structure"]["title"] = FAIL_MARKER
    stored["generated_from"]["warning"] = "The paper could not be rendered."

    async with fake.client() as client:
        paper = await rerender_paper(client, typeset.client(), paper_id, extractor)

    assert paper.rendered_pdf is not None
    assert "warning" not in (paper.generated_from or {})
