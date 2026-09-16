from __future__ import annotations

import json
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError
from sidereal_core.canonical import (
    MAX_ANSWER_LINES,
    CanonicalMarkScheme,
    CanonicalMarkSchemeQuestion,
    CanonicalPaper,
    CanonicalPart,
    CanonicalQuestion,
    CanonicalSubPart,
    CanonicalWorksheet,
    RenderKind,
    RenderOutput,
)
from sidereal_core.models import Paper, PaperDraft, PaperStatus, QuestionDraft
from sidereal_core.testing import FAIL_MARKER, FAKE_PDF, FakeTypeset
from sidereal_core.typeset import TypesetClient, TypesetError

PAPER = CanonicalPaper(
    title="Pure Mathematics 1",
    board="Edexcel",
    year=2025,
    time_minutes=90,
    total_marks=75,
    instructions="Answer *all* questions.",
    questions=(
        CanonicalQuestion(
            number="1",
            stem="The curve $C$ has equation $y = x^3$.",
            parts=(
                CanonicalPart(
                    label="a",
                    text="Find $(d y) / (d x)$.",
                    marks=2,
                    answer_lines=3,
                    parts=(CanonicalSubPart(label="i", text="State the gradient at $x = 1$."),),
                ),
            ),
        ),
    ),
)


def test_a_document_carries_the_field_names_the_renderer_reads() -> None:
    assert json.loads(PAPER.model_dump_json()) == {
        "title": "Pure Mathematics 1",
        "source": None,
        "board": "Edexcel",
        "year": 2025,
        "time_minutes": 90,
        "total_marks": 75,
        "instructions": "Answer *all* questions.",
        "questions": [
            {
                "number": "1",
                "stem": "The curve $C$ has equation $y = x^3$.",
                "marks": None,
                "answer_lines": None,
                "parts": [
                    {
                        "label": "a",
                        "text": "Find $(d y) / (d x)$.",
                        "marks": 2,
                        "answer_lines": 3,
                        "parts": [
                            {
                                "label": "i",
                                "text": "State the gradient at $x = 1$.",
                                "marks": None,
                                "answer_lines": None,
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_a_field_the_structure_does_not_have_is_refused() -> None:
    with pytest.raises(ValidationError, match="marks_available"):
        CanonicalQuestion.model_validate({"number": "1", "marks_available": 4})


def test_answer_lines_are_capped_at_the_renderers_limit() -> None:
    assert CanonicalQuestion(number="1", answer_lines=MAX_ANSWER_LINES).answer_lines == 60
    with pytest.raises(ValidationError, match="answer_lines"):
        CanonicalQuestion(number="1", answer_lines=MAX_ANSWER_LINES + 1)


async def test_rendering_a_paper_sends_the_structure_and_answers_with_a_pdf() -> None:
    fake = FakeTypeset()

    async with fake.client() as client:
        pdf = await client.render(RenderKind.PAPER, PAPER)

    assert pdf == FAKE_PDF
    assert fake.rendered[0]["kind"] == "paper"
    assert fake.rendered[0]["output"] == "pdf"
    assert fake.rendered[0]["document"]["questions"][0]["parts"][0]["label"] == "a"


async def test_a_worksheet_renders_to_source_and_a_mark_scheme_to_pages() -> None:
    worksheet = CanonicalWorksheet(
        title="Week 3", student="A. Tutee", due="2026-09-25", questions=PAPER.questions
    )
    scheme = CanonicalMarkScheme(
        title="Mark scheme", questions=(CanonicalMarkSchemeQuestion(number="1", answer="$3 x^2$"),)
    )
    fake = FakeTypeset(pages=2)

    async with fake.client() as client:
        source = await client.render(RenderKind.WORKSHEET, worksheet, RenderOutput.SOURCE)
        pages = await client.render(RenderKind.MARK_SCHEME, scheme, RenderOutput.SVG)

    assert "A. Tutee" in source
    assert len(pages) == 2
    assert [call["kind"] for call in fake.rendered] == ["worksheet", "mark_scheme"]


async def test_a_document_the_renderer_refuses_carries_what_it_said() -> None:
    async with FakeTypeset().client() as client:
        with pytest.raises(TypesetError, match="does-not-compile") as raised:
            await client.render(RenderKind.PAPER, CanonicalPaper(title=FAIL_MARKER))

    assert raised.value.status == 422


async def test_a_structural_refusal_names_the_path_it_refused() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422, json={"errors": [{"path": "questions[0].parts", "message": "one level only"}]}
        )

    async with TypesetClient("http://typeset.test", transport=httpx.MockTransport(handler)) as c:
        with pytest.raises(TypesetError, match=r"questions\[0\].parts: one level only"):
            await c.render(RenderKind.PAPER, PAPER)


def test_a_paper_draft_writes_only_what_it_was_given() -> None:
    draft = PaperDraft(title="Pure Mathematics 1", structure=PAPER.model_dump(mode="json"))

    payload = draft.payload()

    assert payload["status"] == PaperStatus.DRAFT.value
    assert payload["structure"]["questions"][0]["number"] == "1"
    assert "rendered_pdf" not in payload
    assert "mark_scheme" not in payload


def test_a_question_carries_its_slice_of_a_papers_structure() -> None:
    paper_id = UUID("33333333-3333-4333-8333-333333333333")
    draft = QuestionDraft(
        text="The curve $C$ has equation $y = x^3$.",
        number="1",
        marks=7,
        answer_lines=6,
        parts=[part.model_dump(mode="json") for part in PAPER.questions[0].parts],
        mark_scheme={"number": "1", "answer": "$3 x^2$", "parts": [], "notes": None},
        paper=paper_id,
    )

    payload = draft.payload()

    assert payload["paper"] == str(paper_id)
    assert payload["parts"][0]["label"] == "a"
    assert payload["mark_scheme"]["answer"] == "$3 x^2$"


def test_a_paper_row_ignores_a_column_the_model_does_not_know() -> None:
    row = {
        "id": "44444444-4444-4444-8444-444444444444",
        "title": "Pure Mathematics 1",
        "status": "reviewed",
        "invented_later": True,
    }

    assert Paper.model_validate(row).status is PaperStatus.REVIEWED
