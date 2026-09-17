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
from sidereal_core.canonical import MAX_FIGURE_WIDTH_MM

from sidereal_ingest.base import IngestError

POINTS_PER_INCH = 72.0
MM_PER_INCH = 25.4

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
SNAP_MARGIN = 0.0025
MIN_FIGURE_SIDE = 0.005
MIN_FIGURE_WIDTH_MM = 20

# A path reaching this far across the page, and a hairline this thin across the other way.
FURNITURE_SPAN = 0.7
FURNITURE_THINNESS = 0.005

# Lines this close together are one band of prose, and a band this close to an edge sits on it.
TEXT_BAND_GAP = 0.02

RASTER_PAGE_FRACTION = 0.2

UNOPENABLE = "That file could not be opened as a PDF."
UNRENDERABLE = "That page could not be turned into an image."


type Box = tuple[float, float, float, float]
"""`(x0, y0, x1, y1)` in PDF points from the page's bottom-left."""


@dataclass(frozen=True, slots=True)
class PageImage:
    """One page as the JPEG a vision model is shown. `index` is 1-based."""

    index: int
    jpeg: bytes


@dataclass(frozen=True, slots=True)
class Figure:
    """A crop and what placed it: `width_mm` is how wide the figure prints on the source page."""

    jpeg: bytes
    snapped: bool
    width_mm: int


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


def figure(
    content: bytes,
    *,
    page: int,
    bbox: tuple[float, float, float, float],
    dpi: float = FIGURE_DPI,
) -> Figure:
    """`page` is 1-based; `bbox` is `(x0, y0, x1, y1)` in 0-1 from the page's top-left."""
    region = _region(bbox)
    with _document(content) as document:
        if not 1 <= page <= len(document):
            raise IngestError(f"That PDF has no page {page}.")
        sheet = document[page - 1]
        size = _page_size(sheet)
        box, snapped = _figure_box(sheet, _points(region, size), size)
        image = _render(sheet, dpi / POINTS_PER_INCH)
    jpeg = _jpeg(_crop(image, box, size), FIGURE_MAX_EDGE, JPEG_QUALITY)
    return Figure(jpeg=jpeg, snapped=snapped, width_mm=_width_mm(box, size))


def _figure_box(sheet: Any, box: Box, size: tuple[float, float]) -> tuple[Box, bool]:
    """A model's box onto what is drawn under it: images, else paths, else the box less prose."""
    images, paths, texts = _page_objects(sheet, size)
    for drawn in (images, paths):
        hits = [bounds for bounds in drawn if _overlaps(box, bounds)]
        if hits:
            return _clamped(_grown(_union(hits), SNAP_MARGIN, size), size), True
    return _trimmed(_clamped(_grown(box, FIGURE_MARGIN, size), size), texts, size), False


def _page_objects(sheet: Any, size: tuple[float, float]) -> tuple[list[Box], list[Box], list[Box]]:
    """Images, figure-worthy paths and text: a path that is page furniture is none of them."""
    images: list[Box] = []
    paths: list[Box] = []
    texts: list[Box] = []
    for obj in sheet.get_objects():
        bounds = _object_bounds(obj)
        if bounds is None:
            continue
        if obj.type == pypdfium2.raw.FPDF_PAGEOBJ_IMAGE:
            images.append(bounds)
        elif obj.type == pypdfium2.raw.FPDF_PAGEOBJ_PATH and not _furniture(bounds, size):
            paths.append(bounds)
        elif obj.type == pypdfium2.raw.FPDF_PAGEOBJ_TEXT:
            texts.append(bounds)
    return images, paths, texts


def _object_bounds(obj: Any) -> Box | None:
    try:
        x0, y0, x1, y1 = obj.get_bounds()
    except pypdfium2.PdfiumError:
        return None
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _furniture(bounds: Box, size: tuple[float, float]) -> bool:
    """A border or a rule: it crosses the page, and where it crosses only one way, a hairline."""
    width, height = size
    across = bounds[2] - bounds[0] >= width * FURNITURE_SPAN
    down = bounds[3] - bounds[1] >= height * FURNITURE_SPAN
    hairline_across = bounds[2] - bounds[0] <= width * FURNITURE_THINNESS
    hairline_down = bounds[3] - bounds[1] <= height * FURNITURE_THINNESS
    return (across and down) or (across and hairline_down) or (down and hairline_across)


def _trimmed(box: Box, texts: list[Box], size: tuple[float, float]) -> Box:
    """A band of text against the top or bottom edge is prose the box ran into, not the figure."""
    gap = size[1] * TEXT_BAND_GAP
    bands = _bands(box, texts, gap)
    if not bands:
        return box
    x0, y0, x1, y1 = box
    if bands[-1][1] >= y1 - gap:
        y1 = bands[-1][0]
    if bands[0][0] <= y0 + gap:
        y0 = bands[0][1]
    if y1 - y0 < size[1] * MIN_FIGURE_SIDE:
        return box
    return (x0, y0, x1, y1)


def _bands(box: Box, texts: list[Box], gap: float) -> list[tuple[float, float]]:
    """The text inside the box as `(low, high)` runs, ascending, lines closer than `gap` merged."""
    bands: list[tuple[float, float]] = []
    spans = sorted(
        (max(text[1], box[1]), min(text[3], box[3])) for text in texts if _overlaps(box, text)
    )
    for low, high in spans:
        if bands and low - bands[-1][1] <= gap:
            bands[-1] = (bands[-1][0], max(bands[-1][1], high))
        else:
            bands.append((low, high))
    return bands


def _overlaps(box: Box, other: Box) -> bool:
    """A shared area, not a shared edge."""
    return (
        min(box[2], other[2]) - max(box[0], other[0]) > 0.0
        and min(box[3], other[3]) - max(box[1], other[1]) > 0.0
    )


def _union(boxes: list[Box]) -> Box:
    return (
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    )


def _grown(box: Box, margin: float, size: tuple[float, float]) -> Box:
    width, height = size
    return (
        box[0] - width * margin,
        box[1] - height * margin,
        box[2] + width * margin,
        box[3] + height * margin,
    )


def _clamped(box: Box, size: tuple[float, float]) -> Box:
    width, height = size
    return (
        min(max(box[0], 0.0), width),
        min(max(box[1], 0.0), height),
        min(max(box[2], 0.0), width),
        min(max(box[3], 0.0), height),
    )


def _points(region: tuple[float, float, float, float], size: tuple[float, float]) -> Box:
    """0-1 from the top-left to points from the bottom-left."""
    width, height = size
    x0, y0, x1, y1 = region
    return (x0 * width, (1.0 - y1) * height, x1 * width, (1.0 - y0) * height)


def _width_mm(box: Box, size: tuple[float, float]) -> int:
    width, _ = size
    page_mm = width / POINTS_PER_INCH * MM_PER_INCH
    millimetres = round((box[2] - box[0]) / width * page_mm)
    return min(max(millimetres, MIN_FIGURE_WIDTH_MM), MAX_FIGURE_WIDTH_MM)


def _crop(image: Image.Image, box: Box, size: tuple[float, float]) -> Image.Image:
    width, height = size
    across, down = image.width / width, image.height / height
    left, top = round(box[0] * across), round((height - box[3]) * down)
    right = max(round(box[2] * across), left + 1)
    bottom = max(round((height - box[1]) * down), top + 1)
    return image.crop((left, top, right, bottom))


def _page_size(sheet: Any) -> tuple[float, float]:
    width, height = sheet.get_size()
    if width <= 0 or height <= 0:
        raise IngestError(UNRENDERABLE)
    return float(width), float(height)


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
    """A model's box made safe: finite, in order, inside the page."""
    if not all(math.isfinite(value) for value in bbox):
        raise IngestError("That figure region is not a box.")
    x0, x1 = sorted((_clamp(bbox[0]), _clamp(bbox[2])))
    y0, y1 = sorted((_clamp(bbox[1]), _clamp(bbox[3])))
    if x1 - x0 < MIN_FIGURE_SIDE or y1 - y0 < MIN_FIGURE_SIDE:
        raise IngestError("That figure region has no area.")
    return (x0, y0, x1, y1)


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
