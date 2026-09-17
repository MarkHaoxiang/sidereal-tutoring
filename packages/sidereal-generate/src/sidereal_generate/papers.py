"""The paper path: a document read into a canonical paper, rendered, and filed."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Container, Iterator, Sequence
from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError
from sidereal_core.canonical import (
    CanonicalFigureBlock,
    CanonicalMarkScheme,
    CanonicalPaper,
    CanonicalPart,
    CanonicalQuestion,
    CanonicalSubPart,
    CanonicalWorksheet,
    RenderKind,
    RenderOutput,
)
from sidereal_core.directus import DirectusClient, DirectusClientError
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
from sidereal_core.typeset import (
    MAX_ASSET_BYTES,
    MAX_ASSETS_BYTES,
    TypesetClient,
    TypesetClientError,
    TypesetError,
)
from sidereal_ingest.base import IngestError
from sidereal_ingest.pdf import crop_figure, needs_page_images, page_images, raster_pages

from sidereal_generate.base import GenerationError, PaperExtractor
from sidereal_generate.models import FigureRequest, MarkSchemeExtraction, PaperExtraction
from sidereal_generate.typst import upload_pdf
from sidereal_generate.typst_maths import normalise_model
from sidereal_generate.usage import UsageTally

logger = logging.getLogger(__name__)

RENDER_WARNING = (
    "The paper could not be rendered, so it has no PDFs yet. Its structure is saved; "
    "render it again once the typeset service answers."
)
NO_PDF = "That document has no PDF, so its pages cannot be read as images."
# Two rounds: the compiler names one fault at a time, and a third round has never been the
# difference between a paper that renders and one that does not.
REPAIR_ROUNDS = 2
FIGURE_TYPE = "image/jpeg"
# The service refuses an asset name that is not a file name, so the file id carries a suffix.
FIGURE_SUFFIX = ".jpg"
FIGURE_BLOCK = "figure"


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
    *,
    mark_scheme_id: UUID | None = None,
    pages: bool | None = None,
    usage: UsageTally | None = None,
) -> UUID:
    """Read a ready document into a `papers` row, its PDFs and its `questions` rows.

    `pages` sends the source PDF's pages as images as well as its text; `None` decides from
    how much of the paper is drawn rather than written.
    """
    document = await _readable(
        client, document_id, "That document has no text yet, so there is no paper to read."
    )
    scheme = (
        None
        if mark_scheme_id is None
        else await _readable(client, mark_scheme_id, "That mark scheme has no text yet.")
    )
    source = await _source_pdf(client, document)
    images, drawn = _pages(source, pages)
    if images:
        logger.info(
            "document %s goes up as %d page images, %d of them drawn: %s",
            document_id,
            len(images),
            len(drawn),
            ", ".join(str(page) for page in drawn),
        )
    extraction = normalise_model(
        await extractor.extract(document, pages=images, drawn=drawn, usage=usage)
    )
    extraction = await _place_figures(client, source, extraction)
    marks = (
        None
        if scheme is None
        else normalise_model(
            await extractor.extract_mark_scheme(scheme, extraction.paper, usage=usage)
        )
    )
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
            mark_scheme=_dump(None if marks is None else marks.mark_scheme),
            generated_from=provenance,
        ),
    )
    extraction, marks = await _link_pdfs(
        client, typeset, extractor, paper.id, extraction, marks, usage
    )
    await _write_questions(client, paper.id, document_id, extraction, marks)
    return paper.id


async def rerender_paper(
    client: DirectusClient,
    typeset: TypesetClient,
    paper_id: UUID,
    extractor: PaperExtractor,
    *,
    usage: UsageTally | None = None,
) -> Paper:
    """Render the stored structure again, repairing maths the compiler refuses as it goes.

    What compiles is what is stored: a repair that works is written back, so the tutor's
    next render starts from source the renderer accepts.
    """
    paper = await client.get_item(Collection.PAPERS, Paper, paper_id)
    extraction = normalise_model(
        PaperExtraction(
            paper=_canonical(CanonicalPaper, paper.structure, "This paper has no structure."),
            figures=(),
        )
    )
    marks = (
        None
        if not paper.mark_scheme
        else normalise_model(
            MarkSchemeExtraction(
                mark_scheme=_canonical(
                    CanonicalMarkScheme, paper.mark_scheme, "This paper has no mark scheme."
                )
            )
        )
    )
    extraction, marks, pdfs = await _rendered(client, typeset, extractor, extraction, marks, usage)
    updates: dict[str, Any] = {
        **_structure(extraction, marks),
        "rendered_pdf": str(pdfs[0]),
    }
    if pdfs[1] is not None:
        updates["mark_scheme_pdf"] = str(pdfs[1])
    # The row rendered, so an earlier failure's warning is no longer true of it.
    generated_from = dict(paper.generated_from or {})
    if generated_from.pop("warning", None) is not None:
        updates["generated_from"] = generated_from
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
    # The PDF is rendered rather than compiled from the source: `/compile` carries no assets,
    # so a figure in the source would resolve to nothing.
    renderable, assets = await _with_assets(client, worksheet)
    source = await typeset.render(
        RenderKind.WORKSHEET, renderable, RenderOutput.SOURCE, assets=assets
    )
    pdf = await typeset.render(RenderKind.WORKSHEET, renderable, RenderOutput.PDF, assets=assets)
    return WorksheetResult(
        source=source, pdf_file_id=await upload_pdf(client, worksheet.title, pdf)
    )


async def _link_pdfs(
    client: DirectusClient,
    typeset: TypesetClient,
    extractor: PaperExtractor,
    paper_id: UUID,
    extraction: PaperExtraction,
    marks: MarkSchemeExtraction | None,
    usage: UsageTally | None,
) -> tuple[PaperExtraction, MarkSchemeExtraction | None]:
    """A render that fails leaves the row and a warning: the structure is the work, not the PDF."""
    paper = await client.get_item(Collection.PAPERS, Paper, paper_id)
    generated_from = dict(paper.generated_from or {})
    try:
        extraction, marks, pdfs = await _rendered(
            client, typeset, extractor, extraction, marks, usage
        )
    except TypesetClientError:
        logger.exception("paper %s could not be rendered", paper_id)
        updates: dict[str, Any] = {"generated_from": {**generated_from, "warning": RENDER_WARNING}}
    else:
        updates = {
            **_structure(extraction, marks),
            "rendered_pdf": str(pdfs[0]),
            "mark_scheme_pdf": None if pdfs[1] is None else str(pdfs[1]),
            "generated_from": generated_from,
        }
    spent = None if usage is None else usage.provenance()
    if spent is not None:
        updates["generated_from"] = {**updates["generated_from"], "usage": spent}
    await client.update_item(Collection.PAPERS, Paper, paper_id, updates)
    return extraction, marks


async def _rendered(
    client: DirectusClient,
    typeset: TypesetClient,
    extractor: PaperExtractor,
    extraction: PaperExtraction,
    marks: MarkSchemeExtraction | None,
    usage: UsageTally | None,
) -> tuple[PaperExtraction, MarkSchemeExtraction | None, tuple[UUID, UUID | None]]:
    """Each document rendered and, where the compiler refuses it, repaired on its own.

    The repaired structures come back with the file ids so the caller stores what compiled:
    a row that keeps source the renderer refused fails the tutor's next render too.
    """
    extraction, rendered = await _with_repairs(
        "paper",
        extraction,
        lambda document: _render(client, typeset, RenderKind.PAPER, document.paper),
        lambda document, diagnostics: extractor.repair(document, diagnostics, usage=usage),
    )
    if marks is None:
        return extraction, None, (rendered, None)
    marks, scheme = await _with_repairs(
        "mark scheme",
        marks,
        lambda document: _render(client, typeset, RenderKind.MARK_SCHEME, document.mark_scheme),
        lambda document, diagnostics: extractor.repair_mark_scheme(
            document, diagnostics, usage=usage
        ),
    )
    return extraction, marks, (rendered, scheme)


async def _with_repairs[M: BaseModel](
    named: str,
    document: M,
    render: Callable[[M], Awaitable[UUID]],
    repair: Callable[[M, str], Awaitable[M]],
) -> tuple[M, UUID]:
    for attempt in range(REPAIR_ROUNDS + 1):
        try:
            return document, await render(document)
        except TypesetError as exc:
            if attempt == REPAIR_ROUNDS or not exc.diagnostics:
                raise
            logger.warning("the %s did not compile, asking for a repair: %s", named, exc)
            document = await _repair(document, exc, repair)
    raise AssertionError  # pragma: no cover - the loop returns or raises.


async def _repair[M: BaseModel](
    document: M, error: TypesetError, repair: Callable[[M, str], Awaitable[M]]
) -> M:
    """A repair that is itself unusable leaves the compiler's own error to be raised."""
    diagnostics = "\n".join(str(diagnostic) for diagnostic in error.diagnostics)
    try:
        return normalise_model(await repair(document, diagnostics))
    except GenerationError:
        logger.exception("the repair of an uncompilable document could not be read")
        raise error from None


def _structure(extraction: PaperExtraction, marks: MarkSchemeExtraction | None) -> dict[str, Any]:
    return {
        "structure": extraction.paper.model_dump(mode="json"),
        "mark_scheme": _dump(None if marks is None else marks.mark_scheme),
    }


async def _readable(client: DirectusClient, document_id: UUID, missing: str) -> Document:
    document = await client.get_item(Collection.DOCUMENTS, Document, document_id)
    if not (document.text or "").strip():
        raise PaperError(missing)
    return document


async def _render(
    client: DirectusClient,
    typeset: TypesetClient,
    kind: RenderKind,
    document: CanonicalPaper | CanonicalMarkScheme | CanonicalWorksheet,
) -> UUID:
    renderable, assets = await _with_assets(client, document)
    return await upload_pdf(
        client, document.title, await typeset.render(kind, renderable, assets=assets)
    )


async def _write_questions(
    client: DirectusClient,
    paper_id: UUID,
    document_id: UUID,
    extraction: PaperExtraction,
    marks: MarkSchemeExtraction | None,
) -> None:
    """One row per top-level question, each carrying its own slice of the structure."""
    scheme = {
        question.number: question
        for question in (() if marks is None else marks.mark_scheme.questions)
    }
    for question in _questions(extraction.paper):
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


def _questions(paper: CanonicalPaper) -> Iterator[CanonicalQuestion]:
    """Every question the paper asks: the loose ones, then each section's own."""
    yield from paper.questions
    for section in paper.sections:
        yield from section.questions


def _chosen(
    paper: CanonicalPaper, question_numbers: Sequence[str]
) -> tuple[CanonicalQuestion, ...]:
    if not question_numbers:
        raise PaperError("Choose at least one question for the worksheet.")
    by_number = {question.number: question for question in _questions(paper)}
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


async def _source_pdf(client: DirectusClient, document: Document) -> bytes | None:
    """The PDF behind the document, when it has one. A scan or a transcript has none."""
    if document.file is None:
        return None
    name, content = await client.download_file(document.file)
    if not name.lower().endswith(".pdf"):
        return None
    return content


def _pages(source: bytes | None, wanted: bool | None) -> tuple[tuple[bytes, ...], tuple[int, ...]]:
    """The page JPEGs to send and which of them are drawn, by 1-based number.

    A PDF a tutor asked for pages of and that has none is an error.
    """
    if wanted is False:
        return (), ()
    if source is None:
        if wanted:
            raise PaperError(NO_PDF)
        return (), ()
    try:
        if wanted is None and not needs_page_images(source):
            return (), ()
        images = tuple(page.jpeg for page in page_images(source))
        # `page_images` truncates a long PDF, and a page that did not go cannot be named.
        return images, tuple(page for page in raster_pages(source) if page <= len(images))
    except IngestError as exc:
        if wanted:
            raise PaperError(str(exc)) from exc
        logger.warning("a paper's pages could not be turned into images: %s", exc)
        return (), ()


async def _place_figures(
    client: DirectusClient, source: bytes | None, extraction: PaperExtraction
) -> PaperExtraction:
    """Every request cropped, filed and placed. The requests are consumed, never stored."""
    if not extraction.figures or source is None:
        return extraction.model_copy(update={"figures": ()})
    placed: list[tuple[FigureRequest, CanonicalFigureBlock]] = []
    for number, request in enumerate(extraction.figures, start=1):
        block = await _figure(client, source, request, number)
        if block is not None:
            placed.append((request, block))
    return extraction.model_copy(
        update={"paper": _with_figures(extraction.paper, placed), "figures": ()}
    )


async def _figure(
    client: DirectusClient, source: bytes, request: FigureRequest, number: int
) -> CanonicalFigureBlock | None:
    """A crop that fails is logged and dropped: the paper is the work, not the picture."""
    try:
        jpeg = crop_figure(source, page=request.page, bbox=request.region)
    except IngestError as exc:
        logger.warning("figure %d could not be cropped: %s", number, exc)
        return None
    uploaded = await client.upload_file(
        f"figure-{number}{FIGURE_SUFFIX}",
        jpeg,
        FIGURE_TYPE,
        title=request.caption or f"Figure {number}",
    )
    return CanonicalFigureBlock(asset=f"{uploaded.id}{FIGURE_SUFFIX}", caption=request.caption)


def _with_figures(
    paper: CanonicalPaper, placed: Sequence[tuple[FigureRequest, CanonicalFigureBlock]]
) -> CanonicalPaper:
    wanted: dict[tuple[str, str | None], list[CanonicalFigureBlock]] = {}
    for request, block in placed:
        wanted.setdefault((request.question_number, request.part_label), []).append(block)
    if not wanted:
        return paper
    questions = tuple(_question_figures(question, wanted) for question in paper.questions)
    sections = tuple(
        section.model_copy(
            update={
                "questions": tuple(
                    _question_figures(question, wanted) for question in section.questions
                )
            }
        )
        for section in paper.sections
    )
    for number, label in wanted:
        logger.warning(
            "a figure names question %s part %s, which this paper has not", number, label
        )
    return paper.model_copy(update={"questions": questions, "sections": sections})


type _Wanted = dict[tuple[str, str | None], list[CanonicalFigureBlock]]


def _question_figures(question: CanonicalQuestion, wanted: _Wanted) -> CanonicalQuestion:
    blocks = wanted.pop((question.number, None), [])
    parts = tuple(_part_figures(question.number, part, wanted) for part in question.parts)
    update: dict[str, Any] = {}
    if blocks:
        update["blocks"] = (*question.blocks, *blocks)
    if parts != question.parts:
        update["parts"] = parts
    return question.model_copy(update=update) if update else question


def _part_figures(number: str, part: CanonicalPart, wanted: _Wanted) -> CanonicalPart:
    blocks = wanted.pop((number, part.label), [])
    parts = tuple(_sub_part_figures(number, sub, wanted) for sub in part.parts)
    update: dict[str, Any] = {}
    if blocks:
        update["blocks"] = (*part.blocks, *blocks)
    if parts != part.parts:
        update["parts"] = parts
    return part.model_copy(update=update) if update else part


def _sub_part_figures(number: str, sub: CanonicalSubPart, wanted: _Wanted) -> CanonicalSubPart:
    blocks = wanted.pop((number, sub.label), [])
    return sub.model_copy(update={"blocks": (*sub.blocks, *blocks)}) if blocks else sub


async def _with_assets[D: BaseModel](
    client: DirectusClient, document: D
) -> tuple[D, dict[str, bytes]]:
    """A document as it can be rendered, and the figure bytes that go with it.

    An asset that will not fit the service's limits is left out, and the `figure` block that
    names it is dropped from this copy: the stored structure keeps it, so a later render prints
    it once there is room.
    """
    names = list(dict.fromkeys(_asset_names(document.model_dump(mode="json"))))
    if not names:
        return document, {}
    assets: dict[str, bytes] = {}
    total = 0
    for name in names:
        content = await _asset(client, name)
        if content is None:
            continue
        if len(content) > MAX_ASSET_BYTES:
            logger.warning(
                "figure %s is larger than %d bytes and was left out", name, MAX_ASSET_BYTES
            )
            continue
        if total + len(content) > MAX_ASSETS_BYTES:
            logger.warning(
                "this document's figures pass %d bytes; the rest are left out", MAX_ASSETS_BYTES
            )
            break
        assets[name] = content
        total += len(content)
    if len(assets) == len(names):
        return document, assets
    return _without_figures(document, assets.keys()), assets


async def _asset(client: DirectusClient, name: str) -> bytes | None:
    """The bytes behind an asset name. A figure whose file is gone is not a failed render."""
    identifier, _, _ = name.rpartition(".")
    try:
        file_id = UUID(identifier)
    except ValueError:
        logger.warning("figure asset %s does not name a file", name)
        return None
    try:
        _, content = await client.download_file(file_id)
    except DirectusClientError as exc:
        logger.warning("figure asset %s could not be read: %s", name, exc)
        return None
    return content


def _asset_names(value: Any) -> Iterator[str]:
    match value:
        case dict():
            if value.get("type") == FIGURE_BLOCK and isinstance(value.get("asset"), str):
                yield value["asset"]
            for item in value.values():
                yield from _asset_names(item)
        case list():
            for item in value:
                yield from _asset_names(item)
        case _:
            return


def _without_figures[D: BaseModel](document: D, keep: Container[str]) -> D:
    return type(document).model_validate(_dropped(document.model_dump(mode="json"), keep))


def _dropped(value: Any, keep: Container[str]) -> Any:
    match value:
        case dict():
            return {key: _dropped(item, keep) for key, item in value.items()}
        case list():
            return [_dropped(item, keep) for item in value if not _unsent(item, keep)]
        case _:
            return value


def _unsent(value: Any, keep: Container[str]) -> bool:
    """A `figure` block whose bytes are not going is a 422 at the service, so it does not go."""
    return (
        isinstance(value, dict)
        and value.get("type") == FIGURE_BLOCK
        and value.get("asset") not in keep
    )
