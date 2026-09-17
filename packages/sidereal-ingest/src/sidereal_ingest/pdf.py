"""A PDF's page as text that keeps its arrangement, as an image, and as a figure crop."""

from __future__ import annotations

import io
import math
import statistics
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from typing import Any

import pypdfium2
from PIL import Image

from sidereal_ingest.base import IngestError

POINTS_PER_INCH = 72.0

# Line grouping and word spacing, as multiples of the page's own median character box.
LINE_GAP = 0.25
LINE_SPAN = 0.45
WORD_GAP = 0.62

PAGE_DPI = 110.0
MAX_PAGE_IMAGES = 40
MAX_EDGE = 1400
JPEG_QUALITY = 80

FIGURE_DPI = 200.0
FIGURE_MAX_EDGE = 1600
FIGURE_MARGIN = 0.015
MIN_FIGURE_SIDE = 0.005

RASTER_PAGE_FRACTION = 0.2

UNOPENABLE = "That file could not be opened as a PDF."
UNRENDERABLE = "That page could not be turned into an image."


@dataclass(frozen=True, slots=True)
class PageImage:
    """One page as the JPEG a vision model is shown. `index` is 1-based."""

    index: int
    jpeg: bytes


def layout_text(content: bytes) -> str:
    """The text of every page, each character placed in the column it sits in."""
    with _document(content) as document:
        pages = [_page_text(page).strip("\n") for page in document]
    return "\n\n".join(page for page in pages if page.strip())


def page_count(content: bytes) -> int:
    with _document(content) as document:
        return len(document)


def raster_page_count(content: bytes) -> int:
    """Pages carrying at least one image object — a scan, a photograph, a drawn figure."""
    return len(raster_pages(content))


def raster_pages(content: bytes) -> tuple[int, ...]:
    """1-based numbers, ascending, of the pages carrying at least one image object."""
    with _document(content) as document:
        return _raster_pages(document)


def needs_page_images(content: bytes) -> bool:
    """Whether enough of the page count is drawn that reading the text alone loses the paper."""
    with _document(content) as document:
        total = len(document)
        raster = len(_raster_pages(document))
    return total > 0 and raster >= total * RASTER_PAGE_FRACTION


def page_images(
    content: bytes,
    *,
    dpi: float = PAGE_DPI,
    max_pages: int = MAX_PAGE_IMAGES,
    max_edge: int = MAX_EDGE,
    quality: int = JPEG_QUALITY,
) -> list[PageImage]:
    """The first `max_pages` pages as JPEGs; a longer PDF is truncated, not refused."""
    with _document(content) as document:
        scale = dpi / POINTS_PER_INCH
        kept = min(len(document), max_pages)
        return [
            PageImage(
                index=number,
                jpeg=_jpeg(_render(document[number - 1], scale), max_edge, quality),
            )
            for number in range(1, kept + 1)
        ]


def crop_figure(
    content: bytes,
    *,
    page: int,
    bbox: tuple[float, float, float, float],
    dpi: float = FIGURE_DPI,
) -> bytes:
    """`page` is 1-based; `bbox` is `(x0, y0, x1, y1)` in 0-1 from the page's top-left."""
    x0, y0, x1, y1 = _region(bbox)
    with _document(content) as document:
        if not 1 <= page <= len(document):
            raise IngestError(f"That PDF has no page {page}.")
        image = _render(document[page - 1], dpi / POINTS_PER_INCH)
    width, height = image.size
    left, top = round(x0 * width), round(y0 * height)
    right, bottom = max(round(x1 * width), left + 1), max(round(y1 * height), top + 1)
    return _jpeg(image.crop((left, top, right, bottom)), FIGURE_MAX_EDGE, JPEG_QUALITY)


@contextmanager
def _document(content: bytes) -> Iterator[Any]:
    try:
        with pypdfium2.PdfDocument(content) as document:
            yield document
    except pypdfium2.PdfiumError as exc:
        raise IngestError(UNOPENABLE) from exc


def _raster_pages(document: Any) -> tuple[int, ...]:
    return tuple(
        number
        for number, page in enumerate(document, start=1)
        if any(obj.type == pypdfium2.raw.FPDF_PAGEOBJ_IMAGE for obj in page.get_objects())
    )


def _render(page: Any, scale: float) -> Image.Image:
    try:
        rendered: Image.Image = page.render(scale=scale).to_pil()
    except (OSError, ValueError) as exc:
        raise IngestError(UNRENDERABLE) from exc
    return rendered


def _jpeg(image: Image.Image, max_edge: int, quality: int) -> bytes:
    try:
        image.thumbnail((max_edge, max_edge))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
    except (OSError, ValueError) as exc:
        raise IngestError(UNRENDERABLE) from exc
    return buffer.getvalue()


def _region(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """A model's box made safe: finite, in order, inside the page, with a little air."""
    if not all(math.isfinite(value) for value in bbox):
        raise IngestError("That figure region is not a box.")
    x0, x1 = sorted((_clamp(bbox[0]), _clamp(bbox[2])))
    y0, y1 = sorted((_clamp(bbox[1]), _clamp(bbox[3])))
    if x1 - x0 < MIN_FIGURE_SIDE or y1 - y0 < MIN_FIGURE_SIDE:
        raise IngestError("That figure region has no area.")
    return (
        max(x0 - FIGURE_MARGIN, 0.0),
        max(y0 - FIGURE_MARGIN, 0.0),
        min(x1 + FIGURE_MARGIN, 1.0),
        min(y1 + FIGURE_MARGIN, 1.0),
    )


def _clamp(value: float) -> float:
    return min(max(value, 0.0), 1.0)


@dataclass(frozen=True, slots=True)
class _Char:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float


def _page_text(page: Any) -> str:
    chars = _characters(page)
    if not chars:
        return ""
    unit = statistics.median(char.x1 - char.x0 for char in chars)
    height = statistics.median(char.y1 - char.y0 for char in chars)
    if unit <= 0 or height <= 0:
        return ""
    chars.sort(key=lambda char: (-char.y0, char.x0))
    return "\n".join(_place(row, unit) for row in _rows(chars, height))


def _characters(page: Any) -> list[_Char]:
    """Every glyph with its loose box: the tight one drops descenders onto a line of their own."""
    chars: list[_Char] = []
    with closing(page.get_textpage()) as textpage:
        for index in range(textpage.count_chars()):
            text = textpage.get_text_range(index, 1)
            if not text or text in "\r\n":
                continue
            x0, y0, x1, y1 = textpage.get_charbox(index, loose=True)
            chars.append(_Char(text, x0, y0, x1, y1))
    return chars


def _rows(chars: list[_Char], height: float) -> Iterator[list[_Char]]:
    row: list[_Char] = []
    for char in chars:
        if _joins(row, char, height):
            row.append(char)
            continue
        if row:
            yield row
        row = [char]
    if row:
        yield row


def _joins(row: list[_Char], char: _Char, height: float) -> bool:
    return (
        bool(row)
        and abs(char.y0 - row[-1].y0) <= height * LINE_GAP
        and abs(char.y0 - row[0].y0) <= height * LINE_SPAN
    )


def _place(row: list[_Char], unit: float) -> str:
    """A row into columns: a gap under `WORD_GAP` stays inside a word, a wider one is spaces."""
    row.sort(key=lambda char: char.x0)
    text = ""
    previous: _Char | None = None
    for char in row:
        column = round(char.x0 / unit)
        if previous is not None:
            joined = char.x0 - previous.x1 <= unit * WORD_GAP
            column = len(text) if joined else max(column, len(text))
        text = text.ljust(column) + char.text
        previous = char
    return text.rstrip()
