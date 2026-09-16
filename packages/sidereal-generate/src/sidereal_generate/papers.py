"""The paper path: a document read into a canonical paper, rendered, and filed."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError
from sidereal_core.canonical import (
    CanonicalDocument,
    CanonicalMarkScheme,
    CanonicalPaper,
    CanonicalQuestion,
    CanonicalWorksheet,
    RenderKind,
    RenderOutput,
)
from sidereal_core.directus import DirectusClient
from sidereal_core.models import (
    Collection,
    Document,
    Paper,
    PaperDraft,
    PaperStatus,
    Question,
    QuestionDraft,
)
from sidereal_core.students import visible_student
from sidereal_core.typeset import TypesetClient, TypesetClientError

from sidereal_generate.base import PaperExtractor
from sidereal_generate.models import PaperExtraction
from sidereal_generate.typst import upload_pdf

logger = logging.getLogger(__name__)

RENDER_WARNING = (
    "The paper could not be rendered, so it has no PDFs yet. Its structure is saved; "
    "render it again once the typeset service answers."
)


class PaperError(Exception):
    """A paper operation that cannot go ahead. The message is what a tutor reads."""


class WorksheetResult(BaseModel):
    """A worksheet as it was rendered: the Typst it compiled from, and the filed PDF."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    pdf_file_id: UUID


async def extract_paper(
    client: DirectusClient,
    extractor: PaperExtractor,
    typeset: TypesetClient,
    document_id: UUID,
    provenance: dict[str, Any],
) -> UUID:
    """Read a ready document into a `papers` row, its PDFs and its `questions` rows."""
    document = await client.get_item(Collection.DOCUMENTS, Document, document_id)
    if not (document.text or "").strip():
        raise PaperError("That document has no text yet, so there is no paper to read.")
    extraction = await extractor.extract(document)
    paper = await client.create_item(
        Collection.PAPERS,
        Paper,
        PaperDraft(
            title=extraction.paper.title,
            source=extraction.paper.source,
            board=extraction.paper.board,
            year=extraction.paper.year,
            time_minutes=extraction.paper.time_minutes,
            total_marks=extraction.paper.total_marks,
            instructions=extraction.paper.instructions,
            status=PaperStatus.DRAFT,
            document=document_id,
            structure=extraction.paper.model_dump(mode="json"),
            mark_scheme=_dump(extraction.mark_scheme),
            generated_from=provenance,
        ),
    )
    await _link_pdfs(client, typeset, paper.id, extraction, provenance)
    await _write_questions(client, paper.id, document_id, extraction)
    return paper.id


async def rerender_paper(client: DirectusClient, typeset: TypesetClient, paper_id: UUID) -> Paper:
    """Render the stored structure again: it is the source of truth and the PDFs follow it."""
    paper = await client.get_item(Collection.PAPERS, Paper, paper_id)
    structure = _canonical(CanonicalPaper, paper.structure, "This paper has no structure.")
    updates = {"rendered_pdf": str(await _render(client, typeset, RenderKind.PAPER, structure))}
    if paper.mark_scheme:
        scheme = _canonical(
            CanonicalMarkScheme, paper.mark_scheme, "This paper has no mark scheme."
        )
        updates["mark_scheme_pdf"] = str(
            await _render(client, typeset, RenderKind.MARK_SCHEME, scheme)
        )
    return await client.update_item(Collection.PAPERS, Paper, paper_id, updates)


async def paper_worksheet(
    client: DirectusClient,
    typeset: TypesetClient,
    paper_id: UUID,
    question_numbers: Sequence[str],
    *,
    student_id: UUID | None = None,
    title: str | None = None,
    due: date | None = None,
) -> WorksheetResult:
    """Some of a paper's questions, in the order asked for, as a worksheet a student answers."""
    paper = await client.get_item(Collection.PAPERS, Paper, paper_id)
    structure = _canonical(CanonicalPaper, paper.structure, "This paper has no structure.")
    student = None if student_id is None else await visible_student(client, student_id)
    worksheet = CanonicalWorksheet(
        title=title or structure.title,
        student=None if student is None else student.name,
        due=None if due is None else due.isoformat(),
        questions=_chosen(structure, question_numbers),
    )
    source = await typeset.render(RenderKind.WORKSHEET, worksheet, RenderOutput.SOURCE)
    pdf = await typeset.compile_pdf(source)
    return WorksheetResult(
        source=source, pdf_file_id=await upload_pdf(client, worksheet.title, pdf)
    )


async def _link_pdfs(
    client: DirectusClient,
    typeset: TypesetClient,
    paper_id: UUID,
    extraction: PaperExtraction,
    provenance: dict[str, Any],
) -> None:
    """A render that fails leaves the row and a warning: the structure is the work, not the PDF."""
    try:
        rendered = await _render(client, typeset, RenderKind.PAPER, extraction.paper)
        scheme = (
            None
            if extraction.mark_scheme is None
            else await _render(client, typeset, RenderKind.MARK_SCHEME, extraction.mark_scheme)
        )
    except TypesetClientError:
        logger.exception("paper %s could not be rendered", paper_id)
        await client.update_item(
            Collection.PAPERS,
            Paper,
            paper_id,
            {"generated_from": {**provenance, "warning": RENDER_WARNING}},
        )
        return
    await client.update_item(
        Collection.PAPERS,
        Paper,
        paper_id,
        {
            "rendered_pdf": str(rendered),
            "mark_scheme_pdf": None if scheme is None else str(scheme),
        },
    )


async def _render(
    client: DirectusClient, typeset: TypesetClient, kind: RenderKind, document: CanonicalDocument
) -> UUID:
    return await upload_pdf(client, document.title, await typeset.render(kind, document))


async def _write_questions(
    client: DirectusClient, paper_id: UUID, document_id: UUID, extraction: PaperExtraction
) -> None:
    """One row per top-level question, each carrying its own slice of the structure."""
    scheme = {
        question.number: question
        for question in (() if extraction.mark_scheme is None else extraction.mark_scheme.questions)
    }
    for question in extraction.paper.questions:
        await client.create_item(
            Collection.QUESTIONS,
            Question,
            QuestionDraft(
                text=_text(question),
                number=question.number,
                marks=question.marks,
                answer_lines=question.answer_lines,
                parts=[part.model_dump(mode="json") for part in question.parts] or None,
                mark_scheme=_dump(scheme.get(question.number)),
                paper=paper_id,
                document=document_id,
            ),
        )


def _text(question: CanonicalQuestion) -> str:
    """What a tutor searching the bank reads: the stem, or the first part when there is none."""
    if question.stem:
        return question.stem
    return question.parts[0].text if question.parts else ""


def _chosen(
    paper: CanonicalPaper, question_numbers: Sequence[str]
) -> tuple[CanonicalQuestion, ...]:
    if not question_numbers:
        raise PaperError("Choose at least one question for the worksheet.")
    by_number = {question.number: question for question in paper.questions}
    missing = [number for number in question_numbers if number not in by_number]
    if missing:
        raise PaperError(f"This paper has no question {', '.join(missing)}.")
    return tuple(by_number[number] for number in question_numbers)


def _canonical[M: BaseModel](model: type[M], stored: dict[str, Any] | None, missing: str) -> M:
    """A stored structure back as a model. A hand edit that broke it says which field."""
    if not stored:
        raise PaperError(missing)
    try:
        return model.model_validate(stored)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        raise PaperError(
            f"This paper's structure could not be read: {where}: {first['msg']}"
        ) from exc


def _dump(document: BaseModel | None) -> dict[str, Any] | None:
    return None if document is None else document.model_dump(mode="json")
