from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from sidereal_core.canonical import CanonicalPaper
from sidereal_generate.base import GenerationError, strict_schema
from sidereal_generate.chunks import (
    BatchQuestion,
    BlockBatch,
    BlockPlacement,
    MarkSchemeBatch,
    PaperSkeleton,
    QuestionBatch,
    block_batches,
    images,
    merge,
    question_batches,
    question_runs,
    reconciled,
    wordless,
)

# The provider refused a 6,521-byte grammar and compiled a 4,101-byte one. Every schema an
# extraction sends stays at or under what was proven to compile.
MAX_SCHEMA_BYTES = 4101
MAX_SCHEMA_DEFS = 8
SCHEMAS = (PaperSkeleton, QuestionBatch, BlockBatch, MarkSchemeBatch)
REFUSED_KEYWORDS = {"oneOf", "prefixItems", "minItems", "maxItems"}


def stub(
    number: str, *, page: int = 1, marks: int | None = None, material: bool = False
) -> dict[str, Any]:
    return {
        "number": number,
        "stem": f"About {number}",
        "page": page,
        "has_material": material,
        "marks": marks,
    }


def shape(**overrides: Any) -> PaperSkeleton:
    return PaperSkeleton.model_validate({"title": "Pure Mathematics 1", **overrides})


def keys(schema: Any) -> set[str]:
    match schema:
        case dict():
            return set(schema) | {key for value in schema.values() for key in keys(value)}
        case list():
            return {key for value in schema for key in keys(value)}
        case _:
            return set()


def self_referencing(schema: dict[str, Any]) -> set[str]:
    return {
        name
        for name, definition in schema.get("$defs", {}).items()
        if f'"#/$defs/{name}"' in json.dumps(definition)
    }


@pytest.mark.parametrize("model", SCHEMAS, ids=lambda model: model.__name__)
def test_every_extraction_schema_fits_the_grammar_a_provider_will_compile(
    model: type[Any],
) -> None:
    schema = strict_schema(model)

    assert len(json.dumps(schema)) <= MAX_SCHEMA_BYTES
    assert len(schema.get("$defs", {})) <= MAX_SCHEMA_DEFS
    assert keys(schema).isdisjoint(REFUSED_KEYWORDS)
    assert self_referencing(schema) == set()


def test_the_model_is_never_asked_to_author_a_figure_block() -> None:
    """The app crops figures out of the PDF; a block union with them in does not fit."""
    assert "CanonicalFigureBlock" not in strict_schema(BlockBatch).get("$defs", {})
    assert "CanonicalFigureBlock" not in strict_schema(MarkSchemeBatch).get("$defs", {})


def test_a_run_is_shown_its_own_pages_through_to_where_the_next_one_starts() -> None:
    skeleton = shape(
        questions=[stub("1", page=1), stub("2", page=3), stub("3", page=6), stub("4", page=7)]
    )

    batches = question_batches(skeleton, size=2, page_count=9)

    assert [batch.numbers for batch in batches] == [("1", "2"), ("3", "4")]
    assert batches[0].pages == (1, 2, 3, 4, 5, 6)
    assert batches[1].pages == (6, 7, 8, 9)


def test_a_paper_with_no_page_images_puts_none_in_front_of_a_run() -> None:
    batches = question_batches(shape(questions=[stub("1"), stub("2")]), size=1)

    assert [batch.pages for batch in batches] == [(), ()]


def test_a_page_a_model_invented_is_clamped_to_the_pages_that_went() -> None:
    batches = question_batches(shape(questions=[stub("1", page=99)]), size=6, page_count=3)

    assert batches[0].pages == (3,)


def test_a_block_batch_covers_the_flagged_questions_alone() -> None:
    skeleton = shape(
        questions=[
            stub("1", page=1),
            stub("2", page=2, material=True),
            stub("3", page=4),
            stub("4", page=5, material=True),
        ]
    )

    batches = block_batches(skeleton, size=6, page_count=6)

    assert [batch.numbers for batch in batches] == [("2", "4")]
    # The span still runs from the first flagged question to the end of the last.
    assert batches[0].pages == (2, 3, 4, 5, 6)


def test_a_paper_that_flags_nothing_asks_for_no_block_batch() -> None:
    assert block_batches(shape(questions=[stub("1"), stub("2")]), page_count=4) == ()


def test_the_runs_cover_a_sectioned_papers_questions_too() -> None:
    paper = CanonicalPaper.model_validate(
        {
            "title": "Paper",
            "questions": [{"number": "1"}],
            "sections": [{"questions": [{"number": "2"}, {"number": "3"}]}],
        }
    )

    runs = question_runs(paper, size=2)

    assert [tuple(question.number for question in run) for run in runs] == [("1", "2"), ("3",)]


def test_the_images_of_a_run_are_picked_by_page_number() -> None:
    pages = [b"one", b"two", b"three"]

    assert images(pages, (2, 3)) == (b"two", b"three")
    assert images(pages, (3, 4)) == (b"three",)


def test_a_block_naming_a_node_the_paper_has_not_is_logged_and_dropped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    skeleton = shape(questions=[stub("1", material=True)])
    blocks = [
        BlockPlacement.model_validate(
            {
                "question_number": "9",
                "part_label": "b",
                "block": {"type": "passage", "text": "Orphan."},
            }
        )
    ]

    with caplog.at_level(logging.WARNING):
        paper = merge(skeleton, {"1": BatchQuestion(number="1", stem="A question.")}, blocks)

    assert paper.questions[0].blocks == ()
    assert "a block names question 9 part b" in caplog.text


def test_a_question_no_batch_was_asked_for_is_logged_and_dropped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The shape is the paper's order of record, so an unasked-for number has no place."""
    with caplog.at_level(logging.WARNING):
        paper = merge(
            shape(questions=[stub("1")]),
            {"1": BatchQuestion(number="1"), "9": BatchQuestion(number="9")},
        )

    assert [question.number for question in paper.questions] == ["1"]
    assert "a batch returned question 9" in caplog.text


def part(label: str, text: str) -> dict[str, Any]:
    return {"label": label, "text": text}


def test_a_batch_question_takes_the_place_of_the_stubs_the_shape_split_it_into(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """AQA prints `01.1`; a shape that read those as questions is corrected by what was read."""
    skeleton = shape(
        sections=[
            {"title": "Section A", "questions": [stub("01.1"), stub("01.2"), stub("01.3")]},
            {"title": "Section B", "questions": [stub("02")]},
        ]
    )
    answered = {
        "01": BatchQuestion.model_validate(
            {
                "number": "01",
                "stem": "A trolley on a ramp.",
                "parts": [part("1", "State the force."), part("2", "Find it."), part("3", "Why?")],
            }
        ),
        "02": BatchQuestion(number="02", stem="A second question."),
    }

    with caplog.at_level(logging.WARNING):
        paper = merge(skeleton, answered)

    assert paper.questions == ()
    assert [question.number for question in paper.sections[0].questions] == ["01"]
    assert paper.sections[0].title == "Section A"
    assert paper.sections[0].questions[0].stem == "A trolley on a ramp."
    assert [p.label for p in paper.sections[0].questions[0].parts] == ["1", "2", "3"]
    assert [question.number for question in paper.sections[1].questions] == ["02"]
    assert "the shape split question 01 into 01.1, 01.2, 01.3" in caplog.text
    # No stub's one-line summary survives as a question's wording.
    assert "About 01" not in paper.model_dump_json()


def test_a_paper_really_numbered_one_point_one_at_the_top_level_is_left_alone() -> None:
    """Nothing is renumbered without a batch question to key the reconciliation on."""
    skeleton = shape(questions=[stub("1.1"), stub("1.2")])
    answered = {
        "1.1": BatchQuestion(number="1.1", stem="The first."),
        "1.2": BatchQuestion(number="1.2", stem="The second."),
    }

    paper = merge(skeleton, answered)

    assert [question.number for question in paper.questions] == ["1.1", "1.2"]
    assert [question.stem for question in paper.questions] == ["The first.", "The second."]


def test_a_question_ten_is_no_part_of_a_question_one() -> None:
    """A suffix that is not a separator is another question's number, not a part label."""
    skeleton = shape(questions=[stub("10"), stub("11")])
    answered = {
        "1": BatchQuestion(number="1"),
        "10": BatchQuestion(number="10", stem="Ten."),
        "11": BatchQuestion(number="11", stem="Eleven."),
    }

    paper = merge(skeleton, answered)

    assert [question.number for question in paper.questions] == ["10", "11"]


def test_a_question_left_untranscribed_fails_rather_than_keeping_its_summary() -> None:
    skeleton = shape(questions=[stub("1"), stub("2"), stub("3")])

    with pytest.raises(GenerationError) as raised:
        merge(skeleton, {"1": BatchQuestion(number="1", stem="The first.")})

    assert str(raised.value) == (
        "No call transcribed question 2, 3, so the paper would carry a one-line summary where "
        "its wording belongs. Try the extraction again."
    )


def test_a_folded_question_keeps_the_earliest_page_and_the_material_of_its_stubs() -> None:
    skeleton = shape(
        questions=[stub("05.1", page=7), stub("05.2", page=8, material=True)],
    )
    answered = {"05": BatchQuestion(number="05", stem="Read the extract.")}

    folded = question_batches(reconciled(skeleton, answered), page_count=9)

    assert folded[0].numbers == ("05",)
    assert folded[0].pages == (7, 8, 9)
    assert block_batches(reconciled(skeleton, answered), page_count=9)[0].numbers == ("05",)


def figure_request(**overrides: Any) -> dict[str, Any]:
    return {
        "page": 1,
        "bbox": [0.1, 0.1, 0.8, 0.6],
        "caption": None,
        "question_number": "1",
        "part_label": None,
        **overrides,
    }


def test_a_node_a_figure_was_asked_for_and_given_no_wording_is_named() -> None:
    batch = QuestionBatch.model_validate(
        {
            "figures": [figure_request(), figure_request(question_number="2", part_label="b")],
            "questions": [
                {"number": "1", "stem": "  "},
                {"number": "2", "parts": [part("a", "Say why."), part("b", "")]},
            ],
        }
    )

    assert wordless(batch) == ("question 1", "question 2 part b")


def test_a_node_that_carries_its_wording_is_not_named() -> None:
    """A question whose parts speak for it has its wording, and a figure is not its only text."""
    batch = QuestionBatch.model_validate(
        {
            "figures": [figure_request(), figure_request(question_number="2")],
            "questions": [
                {"number": "1", "stem": "The circuit shown."},
                {"number": "2", "stem": None, "parts": [part("a", "Find the current.")]},
            ],
        }
    )

    assert wordless(batch) == ()
