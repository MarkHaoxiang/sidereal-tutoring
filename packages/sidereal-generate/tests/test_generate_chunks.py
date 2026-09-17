from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from sidereal_core.canonical import (
    CanonicalMarkSchemeQuestion,
    CanonicalPaper,
    CanonicalPassageBlock,
)
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
    merge_scheme,
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


def test_a_lone_unlabelled_part_is_the_questions_stem() -> None:
    """The live paper's questions 16 and 25: no stem, and one part carrying the whole thing."""
    answered = {
        "16": BatchQuestion.model_validate(
            {
                "number": "16",
                "stem": None,
                "parts": [
                    {
                        "label": "",
                        "text": "Explain why the resistance falls.",
                        "marks": 4,
                        "answer": {"type": "lines", "lines": 6},
                    }
                ],
            }
        )
    }
    blocks = [
        BlockPlacement.model_validate(
            {
                "question_number": "16",
                "part_label": "",
                "block": {"type": "passage", "text": "The extract."},
            }
        )
    ]

    question = merge(shape(questions=[stub("16")]), answered, blocks).questions[0]

    assert question.stem == "Explain why the resistance falls."
    assert question.parts == ()
    assert question.marks == 4
    assert question.answer is not None
    assert question.answer.lines == 6
    assert [block.type for block in question.blocks] == ["passage"]


def test_a_lone_unlabelled_parts_own_parts_come_up_with_it() -> None:
    answered = {
        "16": BatchQuestion.model_validate(
            {
                "number": "16",
                "parts": [
                    {
                        "label": " ",
                        "text": "A trolley on a ramp.",
                        "parts": [part("i", "State the force."), part("ii", "Find it.")],
                    }
                ],
            }
        )
    }

    question = merge(shape(questions=[stub("16")]), answered).questions[0]

    assert question.stem == "A trolley on a ramp."
    assert [nested.label for nested in question.parts] == ["i", "ii"]


def test_a_labelled_part_or_a_second_part_leaves_the_question_as_it_was() -> None:
    answered = {
        "1": BatchQuestion.model_validate({"number": "1", "parts": [part("a", "Find it.")]}),
        "2": BatchQuestion.model_validate(
            {"number": "2", "parts": [part("", "First."), part("", "Second.")]}
        ),
    }

    paper = merge(shape(questions=[stub("1"), stub("2")]), answered)

    assert paper.questions[0].stem is None
    assert [nested.label for nested in paper.questions[0].parts] == ["a"]
    assert [nested.text for nested in paper.questions[1].parts] == ["First.", "Second."]


def test_a_question_whose_stem_is_its_lone_part_is_not_wordless() -> None:
    batch = QuestionBatch.model_validate(
        {
            "figures": [figure_request()],
            "questions": [{"number": "1", "parts": [part("", "The circuit shown is series.")]}],
        }
    )

    assert wordless(batch) == ()


def test_a_lone_unlabelled_part_with_no_wording_leaves_the_question_with_none() -> None:
    batch = QuestionBatch.model_validate(
        {"figures": [figure_request()], "questions": [{"number": "1", "parts": [part("", "  ")]}]}
    )

    assert wordless(batch) == ("question 1",)


def answered_question(number: str) -> CanonicalMarkSchemeQuestion:
    return CanonicalMarkSchemeQuestion(number=number, answer=f"Answer {number}")


def sectioned(*numbers: str) -> CanonicalPaper:
    return CanonicalPaper.model_validate(
        {
            "title": "Physics Paper 1",
            "sections": [{"questions": [{"number": number} for number in numbers]}],
        }
    )


def test_a_mark_scheme_missing_entries_is_refused_rather_than_stored() -> None:
    """The live scheme held 26 of 31 answers and nothing noticed. Five questions are named."""
    with pytest.raises(GenerationError) as raised:
        merge_scheme(sectioned("01", "02", "03"), [answered_question("01")])

    assert "no answer for question 02, 03" in str(raised.value)


def test_a_mark_scheme_that_answered_nothing_says_so_in_its_own_words() -> None:
    with pytest.raises(GenerationError) as raised:
        merge_scheme(sectioned("01", "02"), [])

    assert "answers none of this paper's questions" in str(raised.value)


def test_a_complete_mark_scheme_comes_back_in_the_papers_own_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    given = [answered_question("02"), answered_question("9"), answered_question("01")]

    with caplog.at_level(logging.WARNING):
        scheme = merge_scheme(sectioned("01", "02"), given)

    assert scheme.title == "Physics Paper 1: mark scheme"
    assert [question.number for question in scheme.questions] == ["01", "02"]
    assert "the mark scheme answered question 9" in caplog.text


def parted(number: str, *labels: str) -> CanonicalPaper:
    return CanonicalPaper.model_validate(
        {
            "title": "Physics Paper 1",
            "questions": [
                {
                    "number": number,
                    "parts": [{"label": label, "text": f"Part {label}."} for label in labels],
                }
            ],
        }
    )


def test_a_scheme_that_answers_a_question_under_too_few_labels_is_refused() -> None:
    """Question 01 came back carrying one part where the paper prints five."""
    answered = CanonicalMarkSchemeQuestion.model_validate(
        {"number": "01", "parts": [{"label": "a", "answer": "$3 x^2$"}]}
    )

    with pytest.raises(GenerationError) as raised:
        merge_scheme(parted("01", "a", "b", "c"), [answered])

    assert "no answer under question 01 parts b, c" in str(raised.value)


def test_a_scheme_answering_every_label_the_paper_prints_is_merged() -> None:
    answered = CanonicalMarkSchemeQuestion.model_validate(
        {"number": "01", "parts": [{"label": "a", "answer": "A"}, {"label": "b", "answer": "B"}]}
    )

    scheme = merge_scheme(parted("01", "a", "b"), [answered])

    assert [part.label for part in scheme.questions[0].parts] == ["a", "b"]


def test_a_question_with_no_parts_and_no_answer_of_its_own_is_refused() -> None:
    entry = CanonicalMarkSchemeQuestion.model_validate(
        {"number": "01", "notes": "allow ecf", "answer": "  "}
    )

    with pytest.raises(GenerationError) as raised:
        merge_scheme(sectioned("01"), [entry])

    assert "no answer under question 01 itself" in str(raised.value)


def test_a_parted_question_answered_as_a_whole_merges_rather_than_refusing() -> None:
    """The same accommodation `_covered` gives a bare part label, one level up."""
    answered = CanonicalMarkSchemeQuestion.model_validate({"number": "01", "answer": "3x^2"})

    scheme = merge_scheme(parted("01", "a", "b"), [answered])

    assert scheme.questions[0].answer == "3x^2"
    assert scheme.questions[0].parts == ()


def test_a_parted_question_with_a_blank_whole_answer_and_no_parts_is_still_a_gap() -> None:
    entry = CanonicalMarkSchemeQuestion.model_validate({"number": "01", "answer": "  "})

    with pytest.raises(GenerationError) as raised:
        merge_scheme(parted("01", "a", "b"), [entry])

    assert "no answer under question 01 parts a, b" in str(raised.value)


def test_a_scheme_carrying_some_but_not_all_of_a_questions_parts_is_still_refused() -> None:
    """The live fault: question 01 came back with one part where the paper prints five."""
    answered = CanonicalMarkSchemeQuestion.model_validate(
        {"number": "01", "parts": [{"label": "1", "answer": "A"}]}
    )

    with pytest.raises(GenerationError) as raised:
        merge_scheme(parted("01", "1", "2", "3", "4", "5"), [answered])

    assert "no answer under question 01 parts 2, 3, 4, 5" in str(raised.value)


def test_a_sub_part_covered_by_its_parts_whole_answer_is_unchanged() -> None:
    paper = CanonicalPaper.model_validate(
        {
            "title": "Physics Paper 1",
            "questions": [
                {
                    "number": "01",
                    "parts": [
                        {
                            "label": "a",
                            "text": "Part a.",
                            "parts": [
                                {"label": "i", "text": "Part a(i)."},
                                {"label": "ii", "text": "Part a(ii)."},
                            ],
                        }
                    ],
                }
            ],
        }
    )
    answered = CanonicalMarkSchemeQuestion.model_validate(
        {"number": "01", "parts": [{"label": "a", "answer": "A"}]}
    )

    scheme = merge_scheme(paper, [answered])

    assert [part.label for part in scheme.questions[0].parts] == ["a"]


def test_a_block_that_only_restates_the_question_is_not_kept() -> None:
    """The live paper: a block call answered a choice question with the question itself."""
    stem = (
        "A parachutist descends to the ground at a constant speed with the parachute open. "
        "Which force, together with the parachutist's weight, makes a pair according to "
        "Newton's third law of motion?"
    )
    answered = {
        "25": BatchQuestion.model_validate(
            {
                "number": "25",
                "stem": stem,
                "answer": {
                    "type": "multiple_choice",
                    "options": [{"label": "A", "text": "the drag force"}],
                },
            }
        )
    }
    blocks = [
        BlockPlacement.model_validate(
            {
                "question_number": "25",
                "part_label": None,
                "block": {"type": "passage", "text": f"{stem}\n\nA the drag force"},
            }
        ),
        BlockPlacement.model_validate(
            {
                "question_number": "25",
                "part_label": None,
                "block": {"type": "passage", "title": "Extract", "text": "Material it needs."},
            }
        ),
    ]

    question = merge(shape(questions=[stub("25", material=True)]), answered, blocks).questions[0]

    kept = [block for block in question.blocks if isinstance(block, CanonicalPassageBlock)]
    assert [block.title for block in kept] == ["Extract"]


def test_a_passage_that_merely_shares_a_phrase_with_its_question_is_kept() -> None:
    answered = {
        "1": BatchQuestion.model_validate(
            {"number": "1", "stem": "Read the extract and answer the question below."}
        )
    }
    blocks = [
        BlockPlacement.model_validate(
            {
                "question_number": "1",
                "part_label": None,
                "block": {"type": "passage", "text": "Read the extract. Then the poem begins."},
            }
        )
    ]

    question = merge(shape(questions=[stub("1", material=True)]), answered, blocks).questions[0]

    assert len(question.blocks) == 1
