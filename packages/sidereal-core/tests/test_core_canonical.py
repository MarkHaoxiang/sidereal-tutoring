from __future__ import annotations

import json
import re
from uuid import UUID

import httpx
import pytest
from pydantic import ValidationError
from sidereal_core.canonical import (
    MAX_ANSWER_HEIGHT_MM,
    MAX_ANSWER_LINES,
    MAX_ANSWER_OPTIONS,
    MAX_FIGURE_WIDTH_MM,
    MAX_GRID_COLS,
    MAX_TABLE_COLS,
    MAX_TABLE_ROWS,
    AnswerKind,
    CanonicalAnswer,
    CanonicalAnswerOption,
    CanonicalCodeBlock,
    CanonicalFigureBlock,
    CanonicalMarkScheme,
    CanonicalMarkSchemeQuestion,
    CanonicalMarkup,
    CanonicalPaper,
    CanonicalPart,
    CanonicalPassage,
    CanonicalPassageBlock,
    CanonicalPassageRefBlock,
    CanonicalQuestion,
    CanonicalSection,
    CanonicalSubPart,
    CanonicalTableBlock,
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
                "answer": None,
                "blocks": [],
                "parts": [
                    {
                        "label": "a",
                        "text": "Find $(d y) / (d x)$.",
                        "marks": 2,
                        "answer_lines": 3,
                        "answer": None,
                        "blocks": [],
                        "parts": [
                            {
                                "label": "i",
                                "text": "State the gradient at $x = 1$.",
                                "marks": None,
                                "answer_lines": None,
                                "answer": None,
                                "blocks": [],
                            }
                        ],
                    }
                ],
            }
        ],
        "sections": [],
        "passages": [],
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


async def test_a_fragment_is_a_kind_of_its_own() -> None:
    fake = FakeTypeset()

    async with fake.client() as client:
        pages = await client.render(
            RenderKind.QUESTION,
            PAPER.questions[0],
            RenderOutput.SVG,
            mark_scheme=CanonicalMarkSchemeQuestion(number="1", answer="$3 x^2$"),
        )
        await client.render(
            RenderKind.MARKUP, CanonicalMarkup(text="$x^2 - 5x + 6$"), RenderOutput.SVG
        )

    assert len(pages) == 1
    assert fake.rendered[0]["mark_scheme"] == {
        "number": "1",
        "parts": [],
        "answer": "$3 x^2$",
        "notes": None,
        "blocks": [],
    }
    assert "mark_scheme" not in fake.rendered[1]
    assert fake.rendered[1]["document"] == {"text": "$x^2 - 5x + 6$"}


async def test_a_mark_scheme_entry_the_renderer_refuses_fails_the_fragment() -> None:
    async with FakeTypeset().client() as client:
        with pytest.raises(TypesetError, match="does-not-compile"):
            await client.render(
                RenderKind.QUESTION,
                PAPER.questions[0],
                mark_scheme=CanonicalMarkSchemeQuestion(number="1", answer=FAIL_MARKER),
            )


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


BLOCKS = (
    CanonicalPassageBlock(title="Ozymandias", text="I met a traveller\n  from an antique land"),
    CanonicalPassageRefBlock(id="ozymandias"),
    CanonicalCodeBlock(language="python", text="def total(values):\n    return sum(values)"),
    CanonicalTableBlock(
        caption="Table 1", header=("Gate", "Time / $s$"), rows=(("A", "0.00"), ("B", "0.41"))
    ),
    CanonicalFigureBlock(asset="figure-1.png", caption="Figure 1", width_mm=70),
)


def test_every_block_kind_carries_its_tag_and_reads_back() -> None:
    question = CanonicalQuestion(number="2", blocks=BLOCKS)

    dumped = question.model_dump(mode="json")

    assert [block["type"] for block in dumped["blocks"]] == [
        "passage",
        "passage_ref",
        "code",
        "table",
        "figure",
    ]
    assert CanonicalQuestion.model_validate(dumped) == question


def test_a_block_union_is_any_of_so_a_strict_tool_schema_accepts_it() -> None:
    assert "oneOf" not in json.dumps(CanonicalPaper.model_json_schema())


def test_no_definition_in_a_canonical_schema_refers_to_itself() -> None:
    defs = CanonicalPaper.model_json_schema()["$defs"]
    refs = {
        name: set(re.findall(r'"#/\$defs/([^"]+)"', json.dumps(definition)))
        for name, definition in defs.items()
    }

    reachable = {name: set(targets) for name, targets in refs.items()}
    growing = True
    while growing:
        growing = False
        for name, targets in reachable.items():
            grown = targets | {onwards for target in targets for onwards in refs[target]}
            if grown != targets:
                reachable[name] = grown
                growing = True

    for name, targets in reachable.items():
        assert name not in targets, f"{name} is reachable from itself"


def test_a_sub_part_holds_no_parts_of_its_own() -> None:
    with pytest.raises(ValidationError, match="parts"):
        CanonicalSubPart.model_validate({"label": "i", "text": "State it.", "parts": []})


def test_a_two_level_part_reads_back_unchanged() -> None:
    dumped = PAPER.questions[0].parts[0].model_dump(mode="json")

    assert set(dumped) == {"label", "text", "marks", "answer_lines", "answer", "blocks", "parts"}
    assert set(dumped["parts"][0]) == set(dumped) - {"parts"}
    assert CanonicalPart.model_validate(dumped) == PAPER.questions[0].parts[0]


def test_a_block_field_the_structure_does_not_have_is_refused() -> None:
    with pytest.raises(ValidationError):
        CanonicalQuestion.model_validate(
            {"number": "2", "blocks": [{"type": "code", "text": "x", "caption": "no"}]}
        )


def test_a_table_block_is_rectangular_and_bounded() -> None:
    with pytest.raises(ValidationError, match="header or at least one row"):
        CanonicalTableBlock()
    assert CanonicalTableBlock(rows=(("A", "0.00"),)).header is None
    with pytest.raises(ValidationError, match="cells where the table has 2 columns"):
        CanonicalTableBlock(header=("a", "b"), rows=(("1",),))
    with pytest.raises(ValidationError, match=f"at most {MAX_TABLE_COLS} columns"):
        CanonicalTableBlock(header=tuple(str(n) for n in range(MAX_TABLE_COLS + 1)))
    with pytest.raises(ValidationError, match=f"at most {MAX_TABLE_ROWS} rows"):
        CanonicalTableBlock(header=("a",), rows=(("1",),) * (MAX_TABLE_ROWS + 1))


def test_a_figure_is_no_wider_than_the_text_column() -> None:
    assert CanonicalFigureBlock(asset="f.png", width_mm=MAX_FIGURE_WIDTH_MM).width_mm == 165
    with pytest.raises(ValidationError, match="width_mm"):
        CanonicalFigureBlock(asset="f.png", width_mm=MAX_FIGURE_WIDTH_MM + 1)
    with pytest.raises(ValidationError, match="width_mm"):
        CanonicalFigureBlock(asset="f.png", width_mm=0)


def test_an_answer_reads_only_the_fields_its_kind_needs() -> None:
    choice = CanonicalAnswer(
        type=AnswerKind.MULTIPLE_CHOICE,
        options=(
            CanonicalAnswerOption(text="kinetic energy"),
            CanonicalAnswerOption(label="D", text="power"),
        ),
    )

    assert choice.model_dump(mode="json")["type"] == "multiple_choice"
    assert CanonicalAnswer(type=AnswerKind.NONE).model_dump(mode="json")["lines"] is None


def test_each_answer_kind_is_capped_where_the_renderer_caps_it() -> None:
    with pytest.raises(ValidationError, match=f"at most {MAX_ANSWER_LINES}"):
        CanonicalAnswer(type=AnswerKind.LINES, lines=MAX_ANSWER_LINES + 1)
    with pytest.raises(ValidationError, match=f"at most {MAX_ANSWER_HEIGHT_MM}"):
        CanonicalAnswer(type=AnswerKind.ESSAY, height_mm=MAX_ANSWER_HEIGHT_MM + 1)
    with pytest.raises(ValidationError, match=f"1 to {MAX_ANSWER_OPTIONS} options"):
        CanonicalAnswer(type=AnswerKind.MULTIPLE_CHOICE)
    with pytest.raises(ValidationError, match="needs both rows and cols"):
        CanonicalAnswer(type=AnswerKind.GRID, rows=10)
    with pytest.raises(ValidationError, match=f"1 to {MAX_GRID_COLS}"):
        CanonicalAnswer(type=AnswerKind.GRID, rows=10, cols=MAX_GRID_COLS + 1)
    with pytest.raises(ValidationError, match=f"1 to {MAX_TABLE_COLS}"):
        CanonicalAnswer(type=AnswerKind.TABLE, rows=4, cols=MAX_TABLE_COLS + 1)


def test_a_node_carries_one_answer_spelling_or_the_other() -> None:
    with pytest.raises(ValidationError, match="deprecated spelling"):
        CanonicalQuestion(number="1", answer_lines=3, answer=CanonicalAnswer(type=AnswerKind.LINES))
    with pytest.raises(ValidationError, match="deprecated spelling"):
        CanonicalPart(
            label="a", text="Find it.", answer_lines=3, answer=CanonicalAnswer(type=AnswerKind.BOX)
        )
    with pytest.raises(ValidationError, match="deprecated spelling"):
        CanonicalSubPart(
            label="i", text="State it.", answer_lines=3, answer=CanonicalAnswer(type=AnswerKind.BOX)
        )


def test_a_section_cannot_ask_for_more_questions_than_it_offers() -> None:
    questions = (CanonicalQuestion(number="01"), CanonicalQuestion(number="02"))

    assert CanonicalSection(title="Section A", choose=1, questions=questions).choose == 1
    with pytest.raises(ValidationError, match="cannot be chosen"):
        CanonicalSection(choose=3, questions=questions)
    with pytest.raises(ValidationError, match="cannot be chosen"):
        CanonicalSection(choose=0, questions=questions)


def test_a_paper_carries_its_sections_and_passages() -> None:
    paper = CanonicalPaper(
        title="English Literature",
        sections=(
            CanonicalSection(
                title="Section A: Shakespeare",
                choose=1,
                questions=(CanonicalQuestion(number="01", blocks=BLOCKS[1:2]),),
            ),
        ),
        passages=(CanonicalPassage(id="ozymandias", title="Ozymandias", text="I met a traveller"),),
    )

    dumped = paper.model_dump(mode="json")

    assert dumped["questions"] == []
    assert dumped["sections"][0]["choose"] == 1
    assert dumped["sections"][0]["questions"][0]["blocks"][0] == {
        "type": "passage_ref",
        "id": "ozymandias",
    }
    assert dumped["passages"][0]["id"] == "ozymandias"
