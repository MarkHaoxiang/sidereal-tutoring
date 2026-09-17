"""A paper split into calls whose schemas a provider will compile, and merged back.

A batch of whole `CanonicalQuestion`s is a grammar the provider refuses, so each call
carries a narrower shape of its own and the paper is rebuilt here.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict
from sidereal_core.canonical import (
    CanonicalAnswer,
    CanonicalCodeBlock,
    CanonicalMarkScheme,
    CanonicalMarkSchemeQuestion,
    CanonicalPaper,
    CanonicalPart,
    CanonicalPassage,
    CanonicalPassageBlock,
    CanonicalPassageRefBlock,
    CanonicalQuestion,
    CanonicalSection,
    CanonicalSubPart,
    CanonicalTableBlock,
)

from sidereal_generate.base import GenerationError
from sidereal_generate.models import FigureRequest

logger = logging.getLogger(__name__)

# How many question numbers one call transcribes. The grammar does not care; the output
# budget does, and a batch is what a model can finish before it runs out of one.
BATCH_QUESTIONS = 6

UNTRANSCRIBED = (
    "No call transcribed question {numbers}, so the paper would carry a one-line summary where "
    "its wording belongs. Try the extraction again."
)
UNANSWERED = (
    "The mark scheme has no answer for question {numbers}, so it covers only part of the paper. "
    "Read the mark scheme again."
)
NOTHING_ANSWERED = (
    "That mark scheme answers none of this paper's questions. Check it is the scheme for this "
    "paper, then read it again."
)

_BATCH = ConfigDict(frozen=True, extra="forbid")

# The model never authors a `figure` block: the app crops those out of the PDF and places
# them. Leaving it out of the union is part of what keeps these schemas compilable.
type PrintedBlock = (
    CanonicalPassageBlock | CanonicalPassageRefBlock | CanonicalCodeBlock | CanonicalTableBlock
)


class QuestionStub(BaseModel):
    """`page` and `has_material` steer later calls, so neither may be left to a default."""

    model_config = _BATCH

    number: str
    stem: str
    page: int
    has_material: bool
    marks: int | None = None


class SkeletonSection(BaseModel):
    model_config = _BATCH

    title: str | None = None
    instructions: str | None = None
    choose: int | None = None
    questions: tuple[QuestionStub, ...] = ()


class PaperSkeleton(BaseModel):
    model_config = _BATCH

    title: str
    source: str | None = None
    board: str | None = None
    year: int | None = None
    time_minutes: int | None = None
    total_marks: int | None = None
    instructions: str | None = None
    questions: tuple[QuestionStub, ...] = ()
    sections: tuple[SkeletonSection, ...] = ()
    passages: tuple[CanonicalPassage, ...] = ()


class BatchSubPart(BaseModel):
    model_config = _BATCH

    label: str
    text: str
    marks: int | None = None
    answer: CanonicalAnswer | None = None


class BatchPart(BaseModel):
    model_config = _BATCH

    label: str
    text: str
    marks: int | None = None
    answer: CanonicalAnswer | None = None
    parts: tuple[BatchSubPart, ...] = ()


class BatchQuestion(BaseModel):
    model_config = _BATCH

    number: str
    stem: str | None = None
    marks: int | None = None
    answer: CanonicalAnswer | None = None
    parts: tuple[BatchPart, ...] = ()


class QuestionBatch(BaseModel):
    """`figures` carries no default: an omitted key must not read as a paper with none."""

    model_config = _BATCH

    figures: tuple[FigureRequest, ...]
    questions: tuple[BatchQuestion, ...] = ()


class BlockPlacement(BaseModel):
    model_config = _BATCH

    question_number: str
    block: PrintedBlock
    part_label: str | None = None


class BlockBatch(BaseModel):
    model_config = _BATCH

    blocks: tuple[BlockPlacement, ...] = ()


class SchemePart(BaseModel):
    model_config = _BATCH

    label: str
    answer: str
    marks: int | None = None
    notes: str | None = None
    blocks: tuple[PrintedBlock, ...] = ()


class SchemeQuestion(BaseModel):
    model_config = _BATCH

    number: str
    parts: tuple[SchemePart, ...] = ()
    answer: str | None = None
    notes: str | None = None
    blocks: tuple[PrintedBlock, ...] = ()


class MarkSchemeBatch(BaseModel):
    model_config = _BATCH

    questions: tuple[SchemeQuestion, ...] = ()


@dataclass(frozen=True, slots=True)
class Batch:
    """One call's worth of questions, and the pages it is shown, by 1-based number."""

    stubs: tuple[QuestionStub, ...]
    pages: tuple[int, ...]

    @property
    def numbers(self) -> tuple[str, ...]:
        return tuple(stub.number for stub in self.stubs)


def _asked(paper: CanonicalPaper) -> tuple[CanonicalQuestion, ...]:
    """Every question the paper asks, loose ones first, then each section's own."""
    return (*paper.questions, *(q for section in paper.sections for q in section.questions))


def stubs(skeleton: PaperSkeleton) -> tuple[QuestionStub, ...]:
    """Every question the skeleton names, loose ones first, then each section's own."""
    return (
        *skeleton.questions,
        *(stub for section in skeleton.sections for stub in section.questions),
    )


def question_batches(
    skeleton: PaperSkeleton, *, size: int = BATCH_QUESTIONS, page_count: int = 0
) -> tuple[Batch, ...]:
    return _batched(stubs(skeleton), size=size, page_count=page_count)


def block_batches(
    skeleton: PaperSkeleton, *, size: int = BATCH_QUESTIONS, page_count: int = 0
) -> tuple[Batch, ...]:
    """Only the questions the skeleton flagged: most papers print no material at all."""
    ordered = stubs(skeleton)
    wanted = tuple(stub for stub in ordered if stub.has_material)
    if not wanted:
        return ()
    return _batched(wanted, size=size, page_count=page_count, following=ordered)


def question_runs(
    paper: CanonicalPaper, *, size: int = BATCH_QUESTIONS
) -> tuple[tuple[CanonicalQuestion, ...], ...]:
    """A read paper's own questions, in the runs one mark-scheme or repair call takes."""
    questions = _asked(paper)
    return tuple(questions[start : start + size] for start in range(0, len(questions), size))


def scheme_runs(
    scheme: CanonicalMarkScheme, *, size: int = BATCH_QUESTIONS
) -> tuple[tuple[CanonicalMarkSchemeQuestion, ...], ...]:
    return tuple(
        scheme.questions[start : start + size] for start in range(0, len(scheme.questions), size)
    )


def as_batch(question: CanonicalQuestion) -> BatchQuestion:
    """A read question in the shape a repair call answers in: its blocks stay behind."""
    return BatchQuestion(
        number=question.number,
        stem=question.stem,
        marks=question.marks,
        answer=question.answer,
        parts=tuple(
            BatchPart(
                label=part.label,
                text=part.text,
                marks=part.marks,
                answer=part.answer,
                parts=tuple(
                    BatchSubPart(label=sub.label, text=sub.text, marks=sub.marks, answer=sub.answer)
                    for sub in part.parts
                ),
            )
            for part in question.parts
        ),
    )


def as_scheme_batch(question: CanonicalMarkSchemeQuestion) -> SchemeQuestion:
    return SchemeQuestion.model_validate(
        question.model_dump(exclude={"blocks", "parts"})
        | {"parts": [part.model_dump(exclude={"blocks"}) for part in question.parts]}
    )


def repaired(paper: CanonicalPaper, corrected: Mapping[str, BatchQuestion]) -> CanonicalPaper:
    """The paper with corrected wording put back. A repair may change only what it says."""
    return paper.model_copy(
        update={
            "questions": tuple(_repaired(question, corrected) for question in paper.questions),
            "sections": tuple(
                section.model_copy(
                    update={
                        "questions": tuple(
                            _repaired(question, corrected) for question in section.questions
                        )
                    }
                )
                for section in paper.sections
            ),
        }
    )


def repaired_scheme(
    scheme: CanonicalMarkScheme, corrected: Mapping[str, SchemeQuestion]
) -> CanonicalMarkScheme:
    return scheme.model_copy(
        update={
            "questions": tuple(
                _repaired_answer(question, corrected) for question in scheme.questions
            )
        }
    )


def page_span(batch: Sequence[QuestionStub], following: int, page_count: int) -> tuple[int, ...]:
    """The pages a run of questions covers: its own, through to where the next one starts."""
    if page_count <= 0 or not batch:
        return ()
    first = min(_page(stub, page_count) for stub in batch)
    last = max(max(_page(stub, page_count) for stub in batch), _clamp(following, page_count))
    return tuple(range(first, last + 1))


def images(pages: Sequence[bytes], wanted: Sequence[int]) -> tuple[bytes, ...]:
    """The JPEGs of the pages a batch is shown, by 1-based page number."""
    return tuple(pages[number - 1] for number in wanted if 1 <= number <= len(pages))


def merge(
    skeleton: PaperSkeleton,
    answered: Mapping[str, BatchQuestion],
    blocks: Sequence[BlockPlacement] = (),
) -> CanonicalPaper:
    """The skeleton filled in: its order, its sections, and the blocks each question names."""
    placed = _placements(blocks)
    skeleton = reconciled(skeleton, answered)
    listed = stubs(skeleton)
    for number in sorted(set(answered) - {stub.number for stub in listed}):
        logger.warning("a batch returned question %s, which the paper's shape has not", number)
    silent = tuple(stub.number for stub in listed if stub.number not in answered)
    if silent:
        raise GenerationError(UNTRANSCRIBED.format(numbers=", ".join(silent)))
    paper = CanonicalPaper(
        title=skeleton.title,
        source=skeleton.source,
        board=skeleton.board,
        year=skeleton.year,
        time_minutes=skeleton.time_minutes,
        total_marks=skeleton.total_marks,
        instructions=skeleton.instructions,
        questions=tuple(_question(stub, answered, placed) for stub in skeleton.questions),
        sections=tuple(
            CanonicalSection(
                title=section.title,
                instructions=section.instructions,
                choose=section.choose,
                questions=tuple(_question(stub, answered, placed) for stub in section.questions),
            )
            for section in skeleton.sections
        ),
        passages=skeleton.passages,
    )
    for number, label in placed:
        logger.warning("a block names question %s part %s, which this paper has not", number, label)
    return paper


def merge_scheme(
    paper: CanonicalPaper, answered: Sequence[CanonicalMarkSchemeQuestion]
) -> CanonicalMarkScheme:
    """The paper's questions, each under the answer read for it. A gap is refused, never stored."""
    wanted = tuple(question.number for question in _asked(paper))
    answers = {answer.number: answer for answer in answered}
    for number in sorted(set(answers) - set(wanted)):
        logger.warning("the mark scheme answered question %s, which the paper has not", number)
    missing = tuple(number for number in wanted if number not in answers)
    if missing and len(missing) == len(wanted):
        raise GenerationError(NOTHING_ANSWERED)
    if missing:
        raise GenerationError(UNANSWERED.format(numbers=", ".join(missing)))
    return CanonicalMarkScheme(
        title=f"{paper.title}: mark scheme",
        questions=tuple(answers[number] for number in wanted),
    )


def reconciled(skeleton: PaperSkeleton, answered: Mapping[str, BatchQuestion]) -> PaperSkeleton:
    """The shape resettled on what was transcribed, where the two disagree about a question.

    A batch that returned `01` where the shape has only `01.1`, `01.2` read the paper right:
    those stubs are that question's parts, so they give up their place — and their section —
    to it. Without such a batch answer nothing is renumbered.
    """
    plan = _folded(skeleton, answered)
    if not plan:
        return skeleton
    return skeleton.model_copy(
        update={
            "questions": _folded_stubs(skeleton.questions, plan),
            "sections": tuple(
                section.model_copy(update={"questions": _folded_stubs(section.questions, plan)})
                for section in skeleton.sections
            ),
        }
    )


def wordless(batch: QuestionBatch) -> tuple[str, ...]:
    """The nodes this batch asked a figure for and gave no wording of their own."""
    questions = {question.number: question for question in batch.questions}
    named: list[str] = []
    for request in batch.figures:
        question = questions.get(request.question_number)
        if question is None:
            continue
        if request.part_label is None:
            lone = _hoistable(question.stem, question.parts)
            stem = question.stem if lone is None else lone.text
            under = question.parts if lone is None else lone.parts
            if not (stem or "").strip() and not under:
                named.append(f"question {question.number}")
            continue
        text = _labelled(question, request.part_label)
        if text is not None and not text.strip():
            named.append(f"question {question.number} part {request.part_label}")
    return tuple(dict.fromkeys(named))


type _Plan = dict[str, QuestionStub | None]


def _folded(skeleton: PaperSkeleton, answered: Mapping[str, BatchQuestion]) -> _Plan:
    """Which stubs one transcribed question stands in for, and which of them it replaces."""
    listed = stubs(skeleton)
    unknown = sorted(set(answered) - {stub.number for stub in listed})
    plan: _Plan = {}
    for number in unknown:
        group = tuple(
            stub
            for stub in listed
            if stub.number not in answered
            and stub.number not in plan
            and _is_part_of(stub.number, number)
        )
        if not group:
            continue
        logger.warning(
            "the shape split question %s into %s; its transcription replaces them",
            number,
            ", ".join(stub.number for stub in group),
        )
        plan[group[0].number] = QuestionStub(
            number=number,
            stem=group[0].stem,
            page=min(stub.page for stub in group),
            has_material=any(stub.has_material for stub in group),
        )
        for stub in group[1:]:
            plan[stub.number] = None
    return plan


def _folded_stubs(listed: Sequence[QuestionStub], plan: _Plan) -> tuple[QuestionStub, ...]:
    kept: list[QuestionStub] = []
    for stub in listed:
        folded = plan.get(stub.number, stub)
        if folded is not None:
            kept.append(folded)
    return tuple(kept)


def _is_part_of(label: str, number: str) -> bool:
    """`01.1` is part 1 of question `01`; `10` is no part of question `1`."""
    suffix = label.removeprefix(number)
    return suffix != label and bool(suffix) and not suffix[0].isalnum()


def _labelled(question: BatchQuestion, label: str) -> str | None:
    for part in question.parts:
        if part.label == label:
            return part.text
        for sub in part.parts:
            if sub.label == label:
                return sub.text
    return None


def _repaired(
    question: CanonicalQuestion, corrected: Mapping[str, BatchQuestion]
) -> CanonicalQuestion:
    """Wording alone comes back from a repair: marks, answers and blocks are not its to move."""
    fixed = corrected.get(question.number)
    if fixed is None:
        return question
    labelled = {part.label: part for part in fixed.parts}
    return question.model_copy(
        update={
            "stem": question.stem if fixed.stem is None else fixed.stem,
            "parts": tuple(
                _repaired_part(part, labelled.get(part.label)) for part in question.parts
            ),
        }
    )


def _repaired_part(part: CanonicalPart, fixed: BatchPart | None) -> CanonicalPart:
    if fixed is None:
        return part
    labelled = {sub.label: sub for sub in fixed.parts}
    return part.model_copy(
        update={
            "text": fixed.text,
            "parts": tuple(_repaired_sub(sub, labelled.get(sub.label)) for sub in part.parts),
        }
    )


def _repaired_sub(sub: CanonicalSubPart, fixed: BatchSubPart | None) -> CanonicalSubPart:
    return sub if fixed is None else sub.model_copy(update={"text": fixed.text})


def _repaired_answer(
    question: CanonicalMarkSchemeQuestion, corrected: Mapping[str, SchemeQuestion]
) -> CanonicalMarkSchemeQuestion:
    fixed = corrected.get(question.number)
    if fixed is None:
        return question
    labelled = {part.label: part for part in fixed.parts}
    return question.model_copy(
        update={
            "answer": question.answer if fixed.answer is None else fixed.answer,
            "parts": tuple(
                part
                if part.label not in labelled
                else part.model_copy(update={"answer": labelled[part.label].answer})
                for part in question.parts
            ),
        }
    )


type _Placed = dict[tuple[str, str | None], list[PrintedBlock]]


def _placements(blocks: Sequence[BlockPlacement]) -> _Placed:
    placed: _Placed = {}
    for placement in blocks:
        placed.setdefault((placement.question_number, placement.part_label), []).append(
            placement.block
        )
    return placed


def _question(
    stub: QuestionStub, answered: Mapping[str, BatchQuestion], placed: _Placed
) -> CanonicalQuestion:
    question = answered[stub.number]
    blocks = tuple(placed.pop((stub.number, None), ()))
    return _hoisted(
        CanonicalQuestion(
            number=stub.number,
            stem=question.stem,
            marks=stub.marks if question.marks is None else question.marks,
            answer=question.answer,
            parts=tuple(_part(stub.number, part, placed) for part in question.parts),
            blocks=blocks,
        )
    )


def _hoisted(question: CanonicalQuestion) -> CanonicalQuestion:
    """A lone part the paper printed no label for is the question's stem, not a part of it."""
    part = _hoistable(question.stem, question.parts)
    if part is None:
        return question
    return question.model_copy(
        update={
            "stem": part.text,
            "marks": part.marks if question.marks is None else question.marks,
            "answer": question.answer if part.answer is None else part.answer,
            "blocks": (*question.blocks, *part.blocks),
            "parts": tuple(CanonicalPart.model_validate(sub.model_dump()) for sub in part.parts),
        }
    )


def _hoistable[P: (BatchPart, CanonicalPart)](stem: str | None, parts: Sequence[P]) -> P | None:
    """The one part a stemless question's wording was left in, where it was left in one."""
    if (stem or "").strip() or len(parts) != 1 or parts[0].label.strip():
        return None
    return parts[0]


def _part(number: str, part: BatchPart, placed: _Placed) -> CanonicalPart:
    return CanonicalPart(
        label=part.label,
        text=part.text,
        marks=part.marks,
        answer=part.answer,
        blocks=tuple(placed.pop((number, part.label), ())),
        parts=tuple(_sub_part(number, sub, placed) for sub in part.parts),
    )


def _sub_part(number: str, sub: BatchSubPart, placed: _Placed) -> CanonicalSubPart:
    return CanonicalSubPart(
        label=sub.label,
        text=sub.text,
        marks=sub.marks,
        answer=sub.answer,
        blocks=tuple(placed.pop((number, sub.label), ())),
    )


def _batched(
    wanted: Sequence[QuestionStub],
    *,
    size: int,
    page_count: int,
    following: Sequence[QuestionStub] | None = None,
) -> tuple[Batch, ...]:
    order = wanted if following is None else following
    return tuple(
        Batch(
            stubs=tuple(run),
            pages=page_span(run, _following(order, run[-1], page_count), page_count),
        )
        for run in _runs(wanted, size)
    )


def _runs(wanted: Sequence[QuestionStub], size: int) -> Iterator[Sequence[QuestionStub]]:
    step = max(size, 1)
    for start in range(0, len(wanted), step):
        yield wanted[start : start + step]


def _following(order: Sequence[QuestionStub], last: QuestionStub, page_count: int) -> int:
    """Where the question after this batch starts: its last one runs up to there."""
    for index, stub in enumerate(order):
        if stub is last:
            return order[index + 1].page if index + 1 < len(order) else page_count
    return page_count


def _page(stub: QuestionStub, page_count: int) -> int:
    return _clamp(stub.page, page_count)


def _clamp(page: int, page_count: int) -> int:
    return min(max(page, 1), page_count)
