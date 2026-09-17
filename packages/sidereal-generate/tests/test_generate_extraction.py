from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

import pytest
from sidereal_core.models import Document, DocumentKind
from sidereal_generate.base import GenerationError, strict_schema
from sidereal_generate.chunks import (
    BlockBatch,
    MarkSchemeBatch,
    PaperSkeleton,
    QuestionBatch,
)
from sidereal_generate.extraction import Ask, ChunkedPaperExtractor
from sidereal_generate.models import MarkSchemeExtraction, PaperExtraction
from sidereal_generate.prompts import (
    BLOCKS_TOOL,
    MARK_SCHEME_TOOL,
    QUESTIONS_TOOL,
    SKELETON_TOOL,
)
from sidereal_generate.usage import UsageTally

DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")
# What the provider proved it would compile. `test_generate_chunks` holds the same pair.
MAX_SCHEMA_BYTES = 4101
MAX_SCHEMA_DEFS = 8


class Caller:
    """The seam the chunking sits on, answered from a queue instead of a gateway."""

    model = "fake-caller"

    def __init__(self, replies: dict[str, list[Any]]) -> None:
        self.replies = {tool: list(queue) for tool, queue in replies.items()}
        self.asks: list[Ask] = []

    async def ask(self, ask: Ask, *, usage: UsageTally | None = None) -> object:
        self.asks.append(ask)
        if usage is not None:
            usage.record(prompt_tokens=10, completion_tokens=5)
        queue = self.replies[ask.tool]
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def asked(self, tool: str) -> list[Ask]:
        return [ask for ask in self.asks if ask.tool == tool]


def document() -> Document:
    return Document(
        id=DOCUMENT_ID,
        title="Mock paper 1",
        kind=DocumentKind.UPLOAD,
        text="1. Find $(d y) / (d x)$ when $y = x^3$.",
    )


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


def shape(**overrides: Any) -> dict[str, Any]:
    return {"title": "Pure Mathematics 1", **overrides}


def batch(*numbers: str, figures: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "questions": [{"number": number, "stem": f"Stem {number}"} for number in numbers],
        "figures": figures or [],
    }


def answers(*numbers: str) -> dict[str, Any]:
    """A mark-scheme run that answers every number it was asked about."""
    return {"questions": [{"number": number, "answer": f"Answer {number}"} for number in numbers]}


def extractor(replies: dict[str, list[Any]], *, size: int = 6) -> tuple[Caller, Any]:
    caller = Caller(replies)
    return caller, ChunkedPaperExtractor(caller, size=size)


async def test_the_questions_come_back_in_the_order_the_shape_gave_them() -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub(str(number)) for number in range(1, 8)])],
            # Each batch answers out of order: the shape is what fixes the paper's.
            QUESTIONS_TOOL: [batch("3", "1", "2"), batch("6", "4", "5"), batch("7")],
        },
        size=3,
    )

    extraction = await reader.extract(document())

    assert [question.number for question in extraction.paper.questions] == [
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
    ]
    assert len(caller.asked(QUESTIONS_TOOL)) == 3


async def test_a_sectioned_paper_keeps_its_top_level_questions_empty() -> None:
    """The live paper's 31 questions were all inside sections, and that is not a loss."""
    _, reader = extractor(
        {
            SKELETON_TOOL: [
                shape(
                    sections=[
                        {"title": "Section A", "choose": 1, "questions": [stub("1"), stub("2")]},
                        {"title": "Section B", "questions": [stub("3")]},
                    ]
                )
            ],
            QUESTIONS_TOOL: [batch("1", "2", "3")],
        }
    )

    paper = (await reader.extract(document())).paper

    assert paper.questions == ()
    assert [section.title for section in paper.sections] == ["Section A", "Section B"]
    assert [question.number for question in paper.sections[0].questions] == ["1", "2"]
    assert paper.sections[0].choose == 1
    assert [question.number for question in paper.sections[1].questions] == ["3"]


async def test_a_question_printed_before_the_first_section_stays_loose() -> None:
    _, reader = extractor(
        {
            SKELETON_TOOL: [
                shape(questions=[stub("1")], sections=[{"questions": [stub("2")]}]),
            ],
            QUESTIONS_TOOL: [batch("1", "2")],
        }
    )

    paper = (await reader.extract(document())).paper

    assert [question.number for question in paper.questions] == ["1"]
    assert [question.number for question in paper.sections[0].questions] == ["2"]


async def test_the_passages_the_shape_read_are_carried_into_the_paper() -> None:
    _, reader = extractor(
        {
            SKELETON_TOOL: [
                shape(
                    questions=[stub("1")],
                    passages=[{"id": "source-a", "title": "Source A", "text": "Line one\n\nTwo"}],
                )
            ],
            QUESTIONS_TOOL: [batch("1")],
        }
    )

    paper = (await reader.extract(document())).paper

    assert [passage.id for passage in paper.passages] == ["source-a"]
    assert paper.passages[0].text == "Line one\n\nTwo"


async def test_a_block_is_attached_to_the_question_or_the_part_that_names_it() -> None:
    _, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1", material=True)])],
            QUESTIONS_TOOL: [
                {
                    "questions": [
                        {
                            "number": "1",
                            "stem": "Read the extract.",
                            "parts": [{"label": "a", "text": "Explain."}],
                        }
                    ],
                    "figures": [],
                }
            ],
            BLOCKS_TOOL: [
                {
                    "blocks": [
                        {
                            "question_number": "1",
                            "part_label": None,
                            "block": {"type": "passage", "text": "The extract."},
                        },
                        {
                            "question_number": "1",
                            "part_label": "a",
                            "block": {"type": "code", "language": "python", "text": "x = 1"},
                        },
                    ]
                }
            ],
        }
    )

    question = (await reader.extract(document())).paper.questions[0]

    assert [block.type for block in question.blocks] == ["passage"]
    assert [block.type for block in question.parts[0].blocks] == ["code"]


async def test_a_paper_that_prints_no_material_is_never_asked_for_blocks() -> None:
    """Most maths papers print none, and a call that asks for none is a call not made."""
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1"), stub("2")])],
            QUESTIONS_TOOL: [batch("1", "2")],
        }
    )

    await reader.extract(document())

    assert caller.asked(BLOCKS_TOOL) == []


async def test_a_batch_is_shown_only_the_pages_its_questions_span() -> None:
    pages = [f"page-{number}".encode() for number in range(1, 9)]
    caller, reader = extractor(
        {
            SKELETON_TOOL: [
                shape(
                    questions=[
                        stub("1", page=1),
                        stub("2", page=2),
                        stub("3", page=3),
                        stub("4", page=5),
                        stub("5", page=6),
                    ]
                )
            ],
            QUESTIONS_TOOL: [batch("1", "2", "3"), batch("4", "5")],
        },
        size=3,
    )

    await reader.extract(document(), pages=pages)

    shown = [ask.pages for ask in caller.asked(QUESTIONS_TOOL)]
    # The first run reaches the page its successor starts on; the last runs to the end.
    assert shown[0] == (b"page-1", b"page-2", b"page-3", b"page-4", b"page-5")
    assert shown[1] == (b"page-5", b"page-6", b"page-7", b"page-8")
    # The shape is the one call that sees the whole paper: it says which page each starts on.
    assert caller.asked(SKELETON_TOOL)[0].pages == tuple(pages)
    assert "pages 1, 2, 3, 4, 5 of the paper" in caller.asked(QUESTIONS_TOOL)[0].prompt


async def test_a_text_only_extraction_is_shown_no_pages_at_all() -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1")])],
            QUESTIONS_TOOL: [batch("1")],
        }
    )

    await reader.extract(document())

    assert all(ask.pages == () for ask in caller.asks)
    assert "Find $(d y) / (d x)$" in caller.asks[0].prompt


async def test_the_drawn_pages_a_batch_spans_are_named_to_it() -> None:
    pages = [b"one", b"two", b"three"]
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1", page=1), stub("2", page=3)])],
            QUESTIONS_TOOL: [batch("1"), batch("2")],
        },
        size=1,
    )

    await reader.extract(document(), pages=pages, drawn=[2])

    asked = caller.asked(QUESTIONS_TOOL)
    # The first run spans pages 1 to 3 and so carries the drawn one; the second spans page 3.
    assert "Pages 2 carry drawn content" in asked[0].prompt
    assert "carry drawn content" not in asked[1].prompt


async def test_a_batch_that_does_not_fit_the_structure_is_asked_once_more(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1")])],
            QUESTIONS_TOOL: [{"questions": [{"stem": "no number"}], "figures": []}, batch("1")],
        }
    )

    with caplog.at_level(logging.WARNING):
        extraction = await reader.extract(document())

    assert [question.number for question in extraction.paper.questions] == ["1"]
    asked = caller.asked(QUESTIONS_TOOL)
    assert len(asked) == 2
    assert "did not fit the structure" in asked[1].prompt
    assert "number" in asked[1].prompt
    assert "questions 1 did not fit the structure" in caplog.text


async def test_a_second_unusable_batch_fails_with_a_sentence_a_tutor_can_read() -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1"), stub("2")])],
            QUESTIONS_TOOL: [{"questions": [{"stem": "no number"}], "figures": []}],
        }
    )

    with pytest.raises(GenerationError) as raised:
        await reader.extract(document())

    assert str(raised.value) == (
        "Questions 1, 2 could not be read after two tries. Try the extraction again."
    )
    assert len(caller.asked(QUESTIONS_TOOL)) == 2


async def test_a_shape_that_cannot_be_read_stops_before_any_batch() -> None:
    caller, reader = extractor({SKELETON_TOOL: [{"questions": [stub("1")]}]})

    with pytest.raises(GenerationError, match="The paper's shape could not be read"):
        await reader.extract(document())

    assert caller.asked(QUESTIONS_TOOL) == []


async def test_a_merge_the_canonical_paper_refuses_is_a_generation_error() -> None:
    """A section offering two questions cannot ask the student to answer five."""
    _, reader = extractor(
        {
            SKELETON_TOOL: [shape(sections=[{"choose": 5, "questions": [stub("1"), stub("2")]}])],
            QUESTIONS_TOOL: [batch("1", "2")],
        }
    )

    with pytest.raises(GenerationError, match="did not fit together"):
        await reader.extract(document())


async def test_a_question_no_batch_transcribed_fails_instead_of_keeping_a_summary() -> None:
    """A one-line stub stored as the paper's wording is the same fault as an invented answer."""
    _, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1", marks=4), stub("2")])],
            QUESTIONS_TOOL: [batch("1")],
        }
    )

    with pytest.raises(GenerationError, match="No call transcribed question 2"):
        await reader.extract(document())


async def test_a_batch_question_the_shape_split_into_parts_replaces_those_stubs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The live Physics paper: the shape read AQA's `01.1` labels as questions of their own."""
    caller, reader = extractor(
        {
            SKELETON_TOOL: [
                shape(
                    sections=[
                        {
                            "title": "Section A",
                            "questions": [stub("01.1", material=True), stub("01.2"), stub("01.3")],
                        },
                        {"title": "Section B", "questions": [stub("02")]},
                    ]
                )
            ],
            QUESTIONS_TOOL: [
                {
                    "questions": [
                        {
                            "number": "01",
                            "stem": "A trolley rolls down a ramp.",
                            "parts": [
                                {"label": "1", "text": "State the force."},
                                {"label": "2", "text": "Calculate it."},
                                {"label": "3", "text": "Explain why."},
                            ],
                        },
                        {"number": "02", "stem": "A second question."},
                    ],
                    "figures": [],
                }
            ],
            BLOCKS_TOOL: [{"blocks": []}],
        }
    )

    with caplog.at_level(logging.WARNING):
        paper = (await reader.extract(document())).paper

    assert [question.number for question in paper.sections[0].questions] == ["01"]
    assert paper.sections[0].title == "Section A"
    assert paper.sections[0].questions[0].stem == "A trolley rolls down a ramp."
    assert [part.label for part in paper.sections[0].questions[0].parts] == ["1", "2", "3"]
    assert [question.number for question in paper.sections[1].questions] == ["02"]
    assert "About 01.1" not in paper.model_dump_json()
    # The block call asks under the numbering the transcription settled on, not the shape's.
    assert '<question number="01"' in caller.asked(BLOCKS_TOOL)[0].prompt


async def test_the_figures_of_every_batch_are_gathered_into_one_list() -> None:
    figure = {
        "page": 2,
        "bbox": [0.1, 0.1, 0.8, 0.6],
        "caption": "Figure 1",
        "question_number": "2",
        "part_label": None,
    }
    _, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1"), stub("2", page=2)])],
            QUESTIONS_TOOL: [batch("1"), batch("2", figures=[figure])],
        },
        size=1,
    )

    extraction = await reader.extract(document(), pages=[b"one", b"two"])

    assert [request.question_number for request in extraction.figures] == ["2"]
    assert extraction.figures[0].page == 2


async def test_the_mark_scheme_is_read_in_runs_under_the_papers_own_numbering() -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1"), stub("2")])],
            QUESTIONS_TOOL: [
                {
                    "questions": [
                        {"number": "1", "parts": [{"label": "a", "text": "Find it.", "marks": 2}]},
                        {"number": "2", "stem": "Differentiate."},
                    ],
                    "figures": [],
                }
            ],
            MARK_SCHEME_TOOL: [
                {"questions": [{"number": "1", "parts": [{"label": "a", "answer": "$3 x^2$"}]}]},
                {"questions": [{"number": "2", "answer": "$2 x$"}]},
            ],
        },
        size=1,
    )
    paper = (await reader.extract(document())).paper

    scheme = await reader.extract_mark_scheme(document(), paper, usage=None)

    assert scheme.mark_scheme.title == "Pure Mathematics 1: mark scheme"
    assert [question.number for question in scheme.mark_scheme.questions] == ["1", "2"]
    assert scheme.mark_scheme.questions[0].parts[0].answer == "$3 x^2$"
    asked = caller.asked(MARK_SCHEME_TOOL)
    assert len(asked) == 2
    assert '<part number="1" label="a" marks="2"/>' in asked[0].prompt
    assert '<question number="2"/>' in asked[1].prompt


async def test_the_usage_tally_sums_the_shape_the_batches_and_the_mark_scheme() -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1"), stub("2")])],
            QUESTIONS_TOOL: [batch("1"), batch("2")],
            MARK_SCHEME_TOOL: [answers("1"), answers("2")],
        },
        size=1,
    )
    usage = UsageTally()

    extraction = await reader.extract(document(), usage=usage)
    await reader.extract_mark_scheme(document(), extraction.paper, usage=usage)

    # The shape, one call per question, and one mark-scheme call per question.
    assert len(caller.asks) == 5
    assert usage.calls == 5
    assert (usage.provenance() or {})["prompt_tokens"] == 50


async def test_every_call_carries_the_schema_of_the_answer_it_asks_for() -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1", material=True)])],
            QUESTIONS_TOOL: [batch("1")],
            BLOCKS_TOOL: [{"blocks": []}],
            MARK_SCHEME_TOOL: [answers("1")],
        }
    )

    extraction = await reader.extract(document())
    await reader.extract_mark_scheme(document(), extraction.paper)

    sent = {ask.tool: ask.schema for ask in caller.asks}
    assert sent[SKELETON_TOOL] == strict_schema(PaperSkeleton)
    assert sent[QUESTIONS_TOOL] == strict_schema(QuestionBatch)
    assert sent[BLOCKS_TOOL] == strict_schema(BlockBatch)
    assert sent[MARK_SCHEME_TOOL] == strict_schema(MarkSchemeBatch)


async def test_a_repair_keeps_everything_it_did_not_show_the_model() -> None:
    """A repair may change wording alone: marks, answers and blocks are not its to move."""
    extraction = PaperExtraction.model_validate(
        {
            "paper": {
                "title": "Pure Mathematics 1",
                "questions": [
                    {
                        "number": "1",
                        "stem": "The chord $PQ$.",
                        "marks": 5,
                        "answer_lines": 4,
                        "blocks": [{"type": "passage", "text": "Verbatim."}],
                        "parts": [{"label": "a", "text": "Find $PQ$.", "marks": 2}],
                    }
                ],
            },
            "figures": [],
        }
    )
    caller, reader = extractor(
        {
            QUESTIONS_TOOL: [
                {
                    "questions": [
                        {
                            "number": "1",
                            "stem": "The chord $P Q$.",
                            "marks": 99,
                            "parts": [{"label": "a", "text": "Find $P Q$.", "marks": 99}],
                        }
                    ],
                    "figures": [],
                }
            ]
        }
    )

    repaired = await reader.repair(extraction, "line 3: unknown variable: PQ")

    question = repaired.paper.questions[0]
    assert question.stem == "The chord $P Q$."
    assert question.parts[0].text == "Find $P Q$."
    assert question.marks == 5
    assert question.parts[0].marks == 2
    assert question.answer_lines == 4
    assert [block.type for block in question.blocks] == ["passage"]
    assert "does not compile" in caller.asks[0].system
    assert "unknown variable: PQ" in caller.asks[0].prompt


async def test_a_mark_scheme_repair_keeps_the_marks_and_notes_it_was_shown() -> None:
    extraction = MarkSchemeExtraction.model_validate(
        {
            "mark_scheme": {
                "title": "Pure Mathematics 1: mark scheme",
                "questions": [
                    {
                        "number": "1",
                        "notes": "allow ecf",
                        "parts": [{"label": "a", "answer": "$PQ = 3$", "marks": 2}],
                    }
                ],
            }
        }
    )
    _, reader = extractor(
        {
            MARK_SCHEME_TOOL: [
                {"questions": [{"number": "1", "parts": [{"label": "a", "answer": "$P Q = 3$"}]}]}
            ]
        }
    )

    repaired = await reader.repair_mark_scheme(extraction, "unknown variable: PQ")

    question = repaired.mark_scheme.questions[0]
    assert question.parts[0].answer == "$P Q = 3$"
    assert question.parts[0].marks == 2
    assert question.notes == "allow ecf"


async def test_every_call_an_extraction_makes_stays_under_the_measured_ceiling() -> None:
    """The provider compiled 4,101 bytes and refused 6,521. A repair is a call like any other."""
    extraction = PaperExtraction.model_validate(
        {"paper": {"title": "P", "questions": [{"number": "1"}]}, "figures": []}
    )
    scheme = MarkSchemeExtraction.model_validate(
        {"mark_scheme": {"title": "P: mark scheme", "questions": [{"number": "1"}]}}
    )
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1", material=True)])],
            QUESTIONS_TOOL: [batch("1")],
            BLOCKS_TOOL: [{"blocks": []}],
            MARK_SCHEME_TOOL: [answers("1")],
        }
    )

    read = await reader.extract(document(), pages=[b"one"])
    await reader.extract_mark_scheme(document(), read.paper)
    await reader.repair(extraction, "unknown variable: PQ")
    await reader.repair_mark_scheme(scheme, "unknown variable: PQ")

    assert {ask.tool for ask in caller.asks} == {
        SKELETON_TOOL,
        QUESTIONS_TOOL,
        BLOCKS_TOOL,
        MARK_SCHEME_TOOL,
    }
    for ask in caller.asks:
        assert len(json.dumps(ask.schema)) <= MAX_SCHEMA_BYTES, ask.tool
        assert len(ask.schema.get("$defs", {})) <= MAX_SCHEMA_DEFS, ask.tool


async def test_a_sub_part_carries_its_own_answer_block_and_scheme_label() -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1", material=True)])],
            QUESTIONS_TOOL: [
                {
                    "questions": [
                        {
                            "number": "1",
                            "parts": [
                                {
                                    "label": "a",
                                    "text": "Consider the table.",
                                    "parts": [
                                        {
                                            "label": "i",
                                            "text": "State the units.",
                                            "marks": 1,
                                            "answer": {"type": "lines", "lines": 2},
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                    "figures": [],
                }
            ],
            BLOCKS_TOOL: [
                {
                    "blocks": [
                        {
                            "question_number": "1",
                            "part_label": "i",
                            "block": {"type": "table", "header": ["t", "v"], "rows": [["1", "2"]]},
                        }
                    ]
                }
            ],
            MARK_SCHEME_TOOL: [
                {"questions": [{"number": "1", "parts": [{"label": "a(i)", "answer": "m/s"}]}]}
            ],
        }
    )

    paper = (await reader.extract(document())).paper
    await reader.extract_mark_scheme(document(), paper)

    sub = paper.questions[0].parts[0].parts[0]
    assert sub.answer is not None
    assert sub.marks == 1
    assert [block.type for block in sub.blocks] == ["table"]
    assert '<part number="1" label="a(i)"' in caller.asked(MARK_SCHEME_TOOL)[0].prompt


async def test_a_repair_that_answers_for_nothing_leaves_everything_as_it_was() -> None:
    extraction = PaperExtraction.model_validate(
        {
            "paper": {
                "title": "Pure Mathematics 1",
                "questions": [
                    {
                        "number": "1",
                        "stem": "The chord $PQ$.",
                        "parts": [
                            {
                                "label": "a",
                                "text": "Find $PQ$.",
                                "parts": [{"label": "i", "text": "State $PQ$."}],
                            }
                        ],
                    }
                ],
            },
            "figures": [],
        }
    )
    _, reader = extractor({QUESTIONS_TOOL: [{"questions": [], "figures": []}]})

    repaired = await reader.repair(extraction, "unknown variable: PQ")

    assert repaired.paper == extraction.paper


async def test_a_part_a_repair_left_out_is_kept_as_it_was() -> None:
    """A repair that drops a part is not a repair: what it did not answer for stands."""
    extraction = PaperExtraction.model_validate(
        {
            "paper": {
                "title": "Pure Mathematics 1",
                "questions": [
                    {
                        "number": "1",
                        "parts": [
                            {
                                "label": "a",
                                "text": "Find $PQ$.",
                                "parts": [{"label": "i", "text": "State $PQ$."}],
                            },
                            {"label": "b", "text": "Hence find $RS$."},
                        ],
                    }
                ],
            },
            "figures": [],
        }
    )
    _, reader = extractor(
        {
            QUESTIONS_TOOL: [
                {
                    "questions": [
                        {"number": "1", "parts": [{"label": "a", "text": "Find $P Q$."}]}
                    ],
                    "figures": [],
                }
            ]
        }
    )

    parts = (await reader.repair(extraction, "unknown variable: PQ")).paper.questions[0].parts

    assert parts[0].text == "Find $P Q$."
    assert parts[0].parts[0].text == "State $PQ$."
    assert parts[1].text == "Hence find $RS$."


def wordless_batch(stem: str | None) -> dict[str, Any]:
    """One question with a figure and, until the model is asked again, nothing to read."""
    return {
        "questions": [{"number": "1", "stem": stem}],
        "figures": [
            {
                "page": 1,
                "bbox": [0.1, 0.1, 0.8, 0.6],
                "caption": None,
                "question_number": "1",
                "part_label": None,
            }
        ],
    }


async def test_a_question_whose_wording_was_left_in_a_figure_is_asked_for_once_more(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1")])],
            QUESTIONS_TOOL: [wordless_batch(""), wordless_batch("The circuit shown.")],
        }
    )

    with caplog.at_level(logging.WARNING):
        paper = (await reader.extract(document(), pages=[b"one"])).paper

    assert paper.questions[0].stem == "The circuit shown."
    asked = caller.asked(QUESTIONS_TOOL)
    assert len(asked) == 2
    assert "figure and no wording" in asked[1].prompt
    assert "question 1 came back with a figure and no wording" in caplog.text


async def test_a_second_answer_that_still_leaves_the_wording_in_the_figure_fails() -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1")])],
            QUESTIONS_TOOL: [wordless_batch(None)],
        }
    )

    with pytest.raises(GenerationError) as raised:
        await reader.extract(document(), pages=[b"one"])

    assert str(raised.value) == (
        "The wording of question 1 was left inside a figure and did not come back when it was "
        "asked for again. Try the extraction again."
    )
    # One extra ask per batch, and no more.
    assert len(caller.asked(QUESTIONS_TOOL)) == 2


async def test_a_question_that_came_back_with_its_wording_is_asked_nothing_extra() -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1")])],
            QUESTIONS_TOOL: [wordless_batch("The circuit shown.")],
        }
    )

    await reader.extract(document(), pages=[b"one"])

    assert len(caller.asked(QUESTIONS_TOOL)) == 1


async def test_a_mark_scheme_run_that_answered_some_of_its_numbers_is_asked_once_more() -> None:
    """The live run asked about 01 to 06 and answered only 01, and nothing compared the two."""
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub(number) for number in ("01", "02", "03")])],
            QUESTIONS_TOOL: [batch("01", "02", "03")],
            MARK_SCHEME_TOOL: [answers("01"), answers("01", "02", "03")],
        }
    )
    paper = (await reader.extract(document())).paper

    scheme = await reader.extract_mark_scheme(document(), paper)

    assert [question.number for question in scheme.mark_scheme.questions] == ["01", "02", "03"]
    asked = caller.asked(MARK_SCHEME_TOOL)
    assert len(asked) == 2
    assert "no entry for 02, 03" in asked[1].prompt
    # The second ask carries the scheme itself again, not the missing numbers alone.
    assert asked[0].prompt in asked[1].prompt


async def test_a_mark_scheme_still_missing_after_the_retry_names_what_it_left_out() -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub(number) for number in ("01", "02", "03")])],
            QUESTIONS_TOOL: [batch("01", "02", "03")],
            MARK_SCHEME_TOOL: [answers("01")],
        }
    )
    paper = (await reader.extract(document())).paper

    with pytest.raises(GenerationError, match="no answer for question 02, 03"):
        await reader.extract_mark_scheme(document(), paper)

    assert len(caller.asked(MARK_SCHEME_TOOL)) == 2


async def test_a_mark_scheme_that_answers_nothing_at_all_says_so_differently() -> None:
    _, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("01"), stub("02")])],
            QUESTIONS_TOOL: [batch("01", "02")],
            MARK_SCHEME_TOOL: [{"questions": []}],
        }
    )
    paper = (await reader.extract(document())).paper

    with pytest.raises(GenerationError, match="answers none of this paper"):
        await reader.extract_mark_scheme(document(), paper)


async def test_a_run_that_answered_every_number_is_asked_nothing_more() -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("01"), stub("02")])],
            QUESTIONS_TOOL: [batch("01", "02")],
            MARK_SCHEME_TOOL: [answers("01", "02")],
        }
    )
    paper = (await reader.extract(document())).paper

    await reader.extract_mark_scheme(document(), paper)

    assert len(caller.asked(MARK_SCHEME_TOOL)) == 1


def parted(*labels: str) -> dict[str, Any]:
    """One question with parts the shape did not name: the batch is what prints them."""
    return {
        "questions": [
            {
                "number": "1",
                "stem": "Stem 1",
                "parts": [{"label": label, "text": f"Part {label}."} for label in labels],
            }
        ],
        "figures": [],
    }


def part_answers(*answered: tuple[str, str]) -> dict[str, Any]:
    return {
        "questions": [
            {
                "number": "1",
                "parts": [{"label": label, "answer": answer} for label, answer in answered],
            }
        ]
    }


async def test_a_mark_scheme_run_that_left_a_part_unanswered_is_asked_once_more() -> None:
    """The live question 01 carried one part where the paper prints five, and it passed."""
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1")])],
            QUESTIONS_TOOL: [parted("a", "b")],
            MARK_SCHEME_TOOL: [
                part_answers(("a", "$3 x^2$")),
                part_answers(("a", "reread"), ("b", "$6 x$")),
            ],
        }
    )
    paper = (await reader.extract(document())).paper

    scheme = await reader.extract_mark_scheme(document(), paper)

    asked = caller.asked(MARK_SCHEME_TOOL)
    assert len(asked) == 2
    assert "question 1 part b" in asked[1].prompt
    # Only the gap is taken from the second answer: the first read part a already.
    assert [(part.label, part.answer) for part in scheme.mark_scheme.questions[0].parts] == [
        ("a", "$3 x^2$"),
        ("b", "$6 x$"),
    ]


async def test_a_part_still_unanswered_after_the_retry_is_named_in_the_refusal() -> None:
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1")])],
            QUESTIONS_TOOL: [parted("a", "b")],
            MARK_SCHEME_TOOL: [part_answers(("a", "$3 x^2$"))],
        }
    )
    paper = (await reader.extract(document())).paper

    with pytest.raises(GenerationError, match="no answer under question 1 part b"):
        await reader.extract_mark_scheme(document(), paper)

    assert len(caller.asked(MARK_SCHEME_TOOL)) == 2


async def test_a_question_with_no_parts_is_answered_by_one_answer_of_its_own() -> None:
    """Every Section B multiple choice: one answer on the entry, and no part list to fill."""
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1")])],
            QUESTIONS_TOOL: [batch("1")],
            MARK_SCHEME_TOOL: [answers("1")],
        }
    )
    paper = (await reader.extract(document())).paper

    scheme = await reader.extract_mark_scheme(document(), paper)

    assert scheme.mark_scheme.questions[0].answer == "Answer 1"
    assert len(caller.asked(MARK_SCHEME_TOOL)) == 1


async def test_a_sub_parted_part_is_answered_under_its_own_label_or_each_sub_label() -> None:
    """A mark scheme part carries no parts, so `a(i)` is one label and `a` marks the whole."""
    caller, reader = extractor(
        {
            SKELETON_TOOL: [shape(questions=[stub("1")])],
            QUESTIONS_TOOL: [
                {
                    "questions": [
                        {
                            "number": "1",
                            "parts": [
                                {
                                    "label": "a",
                                    "text": "Consider the table.",
                                    "parts": [
                                        {"label": "i", "text": "State the units."},
                                        {"label": "ii", "text": "Explain why."},
                                    ],
                                }
                            ],
                        }
                    ],
                    "figures": [],
                }
            ],
            MARK_SCHEME_TOOL: [part_answers(("a", "Both marks together."))],
        }
    )
    paper = (await reader.extract(document())).paper

    scheme = await reader.extract_mark_scheme(document(), paper)

    assert scheme.mark_scheme.questions[0].parts[0].label == "a"
    assert len(caller.asked(MARK_SCHEME_TOOL)) == 1
