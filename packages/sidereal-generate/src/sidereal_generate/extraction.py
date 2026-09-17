"""A paper read in calls small enough for a provider to compile a grammar for each."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError
from sidereal_core.canonical import CanonicalMarkScheme, CanonicalMarkSchemeQuestion, CanonicalPaper
from sidereal_core.models import Document

from sidereal_generate.base import GenerationError, strict_schema, unstringify
from sidereal_generate.chunks import (
    BATCH_QUESTIONS,
    Batch,
    BatchQuestion,
    BlockBatch,
    BlockPlacement,
    MarkSchemeBatch,
    PaperSkeleton,
    QuestionBatch,
    SchemeQuestion,
    as_batch,
    as_scheme_batch,
    block_batches,
    images,
    merge,
    question_batches,
    question_runs,
    repaired,
    repaired_scheme,
    scheme_runs,
)
from sidereal_generate.models import FigureRequest, MarkSchemeExtraction, PaperExtraction
from sidereal_generate.prompts import (
    BATCH_RETRY,
    BLOCK_BATCH_PAGES_PROMPT,
    BLOCK_BATCH_PROMPT,
    BLOCKS_TOOL,
    MARK_SCHEME_PROMPT,
    MARK_SCHEME_REPAIR,
    MARK_SCHEME_TOOL,
    PAPER_REPAIR,
    QUESTION_BATCH_PAGES_PROMPT,
    QUESTION_BATCH_TEXT_PROMPT,
    QUESTIONS_TOOL,
    SKELETON_PAGES_PROMPT,
    SKELETON_PROMPT,
    SKELETON_TOOL,
    render_document,
    render_mark_scheme,
    render_pages,
    render_wanted,
)
from sidereal_generate.usage import UsageTally

logger = logging.getLogger(__name__)

UNREADABLE = "{named} could not be read after two tries. Try the extraction again."
UNMERGEABLE = "The pieces this paper was read in did not fit together. Try the extraction again."


@dataclass(frozen=True, slots=True)
class Ask:
    """One model call: what to send, and the schema the answer must fit."""

    system: str
    prompt: str
    tool: str
    description: str
    schema: dict[str, Any]
    pages: tuple[bytes, ...] = ()


class BatchCaller(Protocol):
    """One call, made by whichever backend is configured. The seam the chunking sits on."""

    @property
    def model(self) -> str: ...

    async def ask(self, ask: Ask, *, usage: UsageTally | None = None) -> object: ...


class ChunkedPaperExtractor:
    """A paper's shape, then its questions in runs, then the material they print.

    Every call's schema stays under the size a provider will compile a strict grammar for,
    and the merged result is validated as a whole `CanonicalPaper` or it is nothing.
    """

    def __init__(self, caller: BatchCaller, *, size: int = BATCH_QUESTIONS) -> None:
        self._caller = caller
        self._size = size

    @property
    def model(self) -> str:
        return self._caller.model

    async def extract(
        self,
        document: Document,
        *,
        pages: Sequence[bytes] = (),
        drawn: Sequence[int] = (),
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        sheets = tuple(pages)
        marked = tuple(drawn) if sheets else ()
        text = render_document(document)
        skeleton = await self._read(
            PaperSkeleton,
            system=SKELETON_PAGES_PROMPT if sheets else SKELETON_PROMPT,
            prompt=_joined(text, render_pages(range(1, len(sheets) + 1))),
            tool=SKELETON_TOOL,
            named="the paper's shape",
            pages=sheets,
            usage=usage,
        )
        answered, figures = await self._questions(skeleton, text, sheets, marked, usage)
        blocks = await self._blocks(skeleton, text, sheets, usage)
        try:
            paper = merge(skeleton, answered, blocks)
        except ValidationError as exc:
            logger.warning("the pieces of %s did not merge: %s", skeleton.title, exc)
            raise GenerationError(UNMERGEABLE) from exc
        return PaperExtraction(paper=paper, figures=figures)

    async def extract_mark_scheme(
        self,
        document: Document,
        paper: CanonicalPaper,
        *,
        usage: UsageTally | None = None,
    ) -> MarkSchemeExtraction:
        answers: list[CanonicalMarkSchemeQuestion] = []
        for run in question_runs(paper, size=self._size):
            named = f"the mark scheme for questions {_listed(q.number for q in run)}"
            batch = await self._read(
                MarkSchemeBatch,
                system=MARK_SCHEME_PROMPT,
                prompt=render_mark_scheme(document, run),
                tool=MARK_SCHEME_TOOL,
                named=named,
                usage=usage,
            )
            answers.extend(
                CanonicalMarkSchemeQuestion.model_validate(answer.model_dump())
                for answer in batch.questions
            )
        return MarkSchemeExtraction(
            mark_scheme=CanonicalMarkScheme(
                title=f"{paper.title}: mark scheme", questions=tuple(answers)
            )
        )

    async def repair(
        self,
        extraction: PaperExtraction,
        diagnostics: str,
        *,
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        """The same runs the extraction used, so a repair's schema fits the same ceiling."""
        corrected: dict[str, BatchQuestion] = {}
        for run in question_runs(extraction.paper, size=self._size):
            answer = await self._read(
                QuestionBatch,
                system=PAPER_REPAIR,
                prompt=_repair_prompt([as_batch(question) for question in run], diagnostics),
                tool=QUESTIONS_TOOL,
                named=f"the repair of questions {_listed(q.number for q in run)}",
                usage=usage,
            )
            corrected.update({question.number: question for question in answer.questions})
        return extraction.model_copy(update={"paper": repaired(extraction.paper, corrected)})

    async def repair_mark_scheme(
        self,
        extraction: MarkSchemeExtraction,
        diagnostics: str,
        *,
        usage: UsageTally | None = None,
    ) -> MarkSchemeExtraction:
        corrected: dict[str, SchemeQuestion] = {}
        for run in scheme_runs(extraction.mark_scheme, size=self._size):
            answer = await self._read(
                MarkSchemeBatch,
                system=MARK_SCHEME_REPAIR,
                prompt=_repair_prompt([as_scheme_batch(question) for question in run], diagnostics),
                tool=MARK_SCHEME_TOOL,
                named=f"the repair of the mark scheme for questions {_listed(q.number for q in run)}",
                usage=usage,
            )
            corrected.update({question.number: question for question in answer.questions})
        return extraction.model_copy(
            update={"mark_scheme": repaired_scheme(extraction.mark_scheme, corrected)}
        )

    async def _questions(
        self,
        skeleton: PaperSkeleton,
        text: str,
        sheets: tuple[bytes, ...],
        marked: Sequence[int],
        usage: UsageTally | None,
    ) -> tuple[dict[str, BatchQuestion], tuple[FigureRequest, ...]]:
        answered: dict[str, BatchQuestion] = {}
        figures: list[FigureRequest] = []
        for batch in question_batches(skeleton, size=self._size, page_count=len(sheets)):
            answer = await self._read(
                QuestionBatch,
                system=QUESTION_BATCH_PAGES_PROMPT if sheets else QUESTION_BATCH_TEXT_PROMPT,
                prompt=_batch_prompt(text, batch, marked),
                tool=QUESTIONS_TOOL,
                named=f"questions {_listed(batch.numbers)}",
                pages=images(sheets, batch.pages),
                usage=usage,
            )
            answered.update({question.number: question for question in answer.questions})
            figures.extend(answer.figures)
        return answered, tuple(figures)

    async def _blocks(
        self,
        skeleton: PaperSkeleton,
        text: str,
        sheets: tuple[bytes, ...],
        usage: UsageTally | None,
    ) -> list[BlockPlacement]:
        """Only the questions the shape flagged: most papers print no material at all."""
        placements: list[BlockPlacement] = []
        for batch in block_batches(skeleton, size=self._size, page_count=len(sheets)):
            answer = await self._read(
                BlockBatch,
                system=BLOCK_BATCH_PAGES_PROMPT if sheets else BLOCK_BATCH_PROMPT,
                prompt=_batch_prompt(text, batch, ()),
                tool=BLOCKS_TOOL,
                named=f"the material printed with questions {_listed(batch.numbers)}",
                pages=images(sheets, batch.pages),
                usage=usage,
            )
            placements.extend(answer.blocks)
        return placements

    async def _read[M: BaseModel](
        self,
        model: type[M],
        *,
        system: str,
        prompt: str,
        tool: str,
        named: str,
        pages: tuple[bytes, ...] = (),
        usage: UsageTally | None = None,
    ) -> M:
        """One call, and one more when the answer does not fit. A third is not asked for."""
        ask = Ask(
            system=system,
            prompt=prompt,
            tool=tool,
            description=f"Return {named}.",
            schema=strict_schema(model),
            pages=pages,
        )
        try:
            return _fitted(model, await self._caller.ask(ask, usage=usage))
        except ValidationError as first:
            logger.warning("%s did not fit the structure, asking once more: %s", named, first)
            retry = replace(ask, prompt=f"{ask.prompt}\n\n{BATCH_RETRY}\n{first}")
            try:
                return _fitted(model, await self._caller.ask(retry, usage=usage))
            except ValidationError as second:
                logger.warning("%s did not fit a second time: %s", named, second)
                raise GenerationError(UNREADABLE.format(named=named.capitalize())) from second


def _repair_prompt(run: Sequence[BaseModel], diagnostics: str) -> str:
    listed = json.dumps([node.model_dump(mode="json") for node in run], indent=1)
    return f"{listed}\n\n{diagnostics}"


def _fitted[M: BaseModel](model: type[M], payload: object) -> M:
    return model.model_validate(unstringify(payload, model))


def _batch_prompt(text: str, batch: Batch, marked: Sequence[int]) -> str:
    return _joined(text, render_pages(batch.pages, marked), render_wanted(batch.stubs))


def _joined(*parts: str) -> str:
    return "\n".join(part for part in parts if part)


def _listed(numbers: Iterable[object]) -> str:
    return ", ".join(str(number) for number in numbers)
