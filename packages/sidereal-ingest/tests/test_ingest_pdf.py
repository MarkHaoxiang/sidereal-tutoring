from __future__ import annotations

import io
from collections.abc import Callable, Sequence
from typing import Any

import pypdfium2
import pytest
from PIL import Image
from sidereal_core.canonical import MAX_FIGURE_WIDTH_MM
from sidereal_ingest.base import IngestError
from sidereal_ingest.pdf import (
    FIGURE_DPI,
    POINTS_PER_INCH,
    figure,
    layout_text,
    needs_page_images,
    page_count,
    page_images,
    raster_page_count,
    raster_pages,
)

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
PAGE_MM = PAGE_WIDTH / POINTS_PER_INCH * 25.4

type Draw = tuple[float, float, float, str]
type Rect = tuple[float, float, float, float]


def text_pdf(*pages: Sequence[Draw]) -> bytes:
    """A PDF drawing `(x, y, size, text)` per page, in points from the page's bottom-left."""
    streams = [
        "BT /F1 12 Tf\n"
        + "".join(f"1 0 0 1 {x} {y} Tm /F1 {size} Tf ({t}) Tj\n" for x, y, size, t in page)
        + "ET\n"
        for page in pages
    ]
    font = 3 + 2 * len(streams)
    kids = " ".join(f"{3 + 2 * n} 0 R" for n in range(len(streams)))
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(streams)} >>",
    ]
    for number, stream in enumerate(streams):
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 {font} 0 R >> >> /Contents {4 + 2 * number} 0 R >>"
        )
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}endstream")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    return _assemble(objs)


def _assemble(objs: list[str]) -> bytes:
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1"))
    start = out.tell()
    out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    trailer = f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n"
    out.write(trailer.encode())
    return out.getvalue()


def image_pdf(*pages: Image.Image) -> bytes:
    buffer = io.BytesIO()
    first, rest = pages[0], list(pages[1:])
    first.save(buffer, format="PDF", save_all=bool(rest), append_images=rest)
    return buffer.getvalue()


def merged(*pdfs: bytes) -> bytes:
    document = pypdfium2.PdfDocument.new()
    for pdf in pdfs:
        source = pypdfium2.PdfDocument(pdf)
        document.import_pages(source, list(range(len(source))))
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def corner_page(colour: tuple[int, int, int], size: tuple[int, int] = (240, 160)) -> Image.Image:
    """A white page with a coloured patch filling its top-left quarter."""
    page = Image.new("RGB", size, "white")
    page.paste(Image.new("RGB", (size[0] // 2, size[1] // 2), colour), (0, 0))
    return page


def blank_page() -> Image.Image:
    return Image.new("RGB", (240, 160), "white")


def centre(jpeg: bytes) -> tuple[int, int, int]:
    image = Image.open(io.BytesIO(jpeg)).convert("RGB")
    pixel = image.getpixel((image.width // 2, image.height // 2))
    assert isinstance(pixel, tuple)
    return pixel[0], pixel[1], pixel[2]


def drawn_pdf(
    *,
    texts: Sequence[Draw] = (),
    image: Rect | None = None,
    rects: Sequence[Rect] = (),
) -> bytes:
    """One page of `text_pdf` text carrying a red image object and stroked rectangles."""
    document = pypdfium2.PdfDocument(text_pdf(list(texts)))
    page = document[0]
    if image is not None:
        page.insert_obj(_image_object(document, image))
    for rect in rects:
        page.insert_obj(_rect_object(document, rect))
    page.gen_content()
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _image_object(document: Any, box: Rect) -> Any:
    x0, y0, x1, y1 = box
    source = io.BytesIO()
    Image.new("RGB", (120, 80), (255, 0, 0)).save(source, format="JPEG")
    source.seek(0)
    obj = pypdfium2.PdfImage.new(document)
    obj.load_jpeg(source)
    obj.set_matrix(pypdfium2.PdfMatrix().scale(x1 - x0, y1 - y0).translate(x0, y0))
    return obj


def _rect_object(document: Any, box: Rect) -> Any:
    x0, y0, x1, y1 = box
    raw = pypdfium2.raw
    handle = raw.FPDFPageObj_CreateNewRect(x0, y0, x1 - x0, y1 - y0)
    raw.FPDFPageObj_SetStrokeColor(handle, 0, 0, 0, 255)
    raw.FPDFPageObj_SetStrokeWidth(handle, 1.0)
    raw.FPDFPath_SetDrawMode(handle, raw.FPDF_FILLMODE_NONE, True)
    return pypdfium2.PdfObject(handle, pdf=document)


def figure_page() -> bytes:
    """A 300 x 200 pt figure with a line of prose above it and another below."""
    return drawn_pdf(
        texts=[(60, 700, 12, "Prose above the figure"), (60, 350, 12, "Prose below the figure")],
        image=(150.0, 400.0, 450.0, 600.0),
    )


def span(jpeg: bytes) -> tuple[float, float]:
    """The crop back in points of the page it was taken from."""
    image = Image.open(io.BytesIO(jpeg))
    scale = FIGURE_DPI / POINTS_PER_INCH
    return image.width / scale, image.height / scale


def sampled(jpeg: bytes) -> list[tuple[int, int, int]]:
    """The crop's centre and the points a fifth of the way in from each corner."""
    image = Image.open(io.BytesIO(jpeg)).convert("RGB")
    pixels = []
    for x in (image.width // 5, image.width // 2, image.width * 4 // 5):
        for y in (image.height // 5, image.height // 2, image.height * 4 // 5):
            pixel = image.getpixel((x, y))
            assert isinstance(pixel, tuple)
            pixels.append((pixel[0], pixel[1], pixel[2]))
    return pixels


def all_red(jpeg: bytes) -> bool:
    return all(red > 180 and green < 80 and blue < 80 for red, green, blue in sampled(jpeg))


def darkest(jpeg: bytes) -> int:
    """The darkest pixel in the crop: ink, where any of the page's text came with it."""
    return min(Image.open(io.BytesIO(jpeg)).convert("L").tobytes())


def line_with(text: str, word: str) -> str:
    return next(line for line in text.splitlines() if word in line)


def test_a_stacked_fraction_keeps_its_rows_and_columns() -> None:
    text = layout_text(
        text_pdf(
            [
                (200, 700, 12, "6"),
                (240, 700, 12, "11"),
                (60, 685, 12, "Simplify fully"),
                (215, 685, 12, "-"),
                (200, 670, 12, "a"),
                (240, 670, 12, "4a"),
            ]
        )
    )

    numerators, middle, denominators = text.splitlines()
    assert numerators.split() == ["6", "11"]
    assert denominators.split() == ["a", "4a"]
    assert "Simplify fully" in middle
    assert numerators.index("6") == denominators.index("a")
    assert numerators.index("11") == denominators.index("4a")


def test_a_word_is_not_split_by_its_own_letter_spacing() -> None:
    text = layout_text(text_pdf([(60, 700, 12, "Simplify fully")]))

    assert text.strip() == "Simplify fully"


def test_columns_far_apart_keep_their_gap() -> None:
    text = layout_text(text_pdf([(60, 700, 12, "Answer"), (400, 700, 12, "[2 marks]")]))

    line = line_with(text, "Answer")
    assert line.index("[2 marks]") - line.index("Answer") > len("Answer") + 10


def test_pages_are_joined_by_a_blank_line() -> None:
    content = text_pdf([(60, 700, 12, "First page")], [(60, 700, 12, "Second page")])

    assert page_count(content) == 2
    text = layout_text(content)
    assert [line.strip() for line in text.splitlines()] == ["First page", "", "Second page"]


def test_text_only_pages_carry_no_raster_image() -> None:
    content = text_pdf([(60, 700, 12, "Solve x^2 - 5x + 6 = 0")])

    assert raster_page_count(content) == 0
    assert needs_page_images(content) is False


def test_a_drawn_page_asks_for_page_images() -> None:
    content = image_pdf(corner_page((255, 0, 0)))

    assert raster_page_count(content) == 1
    assert needs_page_images(content) is True


def test_one_drawn_page_in_ten_stays_below_the_threshold() -> None:
    content = merged(image_pdf(blank_page()), text_pdf(*([(60, 700, 12, "Prose")],) * 9))

    assert page_count(content) == 10
    assert raster_page_count(content) == 1
    assert needs_page_images(content) is False


def test_two_drawn_pages_in_ten_reach_the_threshold() -> None:
    content = merged(
        image_pdf(blank_page(), blank_page()), text_pdf(*([(60, 700, 12, "Prose")],) * 8)
    )

    assert raster_page_count(content) == 2
    assert needs_page_images(content) is True


def test_raster_pages_is_empty_for_an_all_text_document() -> None:
    content = text_pdf([(60, 700, 12, "Solve x^2 - 5x + 6 = 0")], [(60, 700, 12, "Factorise")])

    assert raster_pages(content) == ()


def test_raster_pages_names_only_the_drawn_pages_in_a_mixed_document() -> None:
    content = merged(
        text_pdf([(60, 700, 12, "Prose")]),
        image_pdf(blank_page()),
        text_pdf([(60, 700, 12, "More prose")]),
        image_pdf(blank_page()),
    )

    assert raster_pages(content) == (2, 4)


def test_raster_page_count_never_drifts_from_raster_pages() -> None:
    content = merged(
        image_pdf(blank_page(), blank_page()), text_pdf(*([(60, 700, 12, "Prose")],) * 8)
    )

    assert raster_page_count(content) == len(raster_pages(content))


def test_page_images_are_jpegs_numbered_from_one() -> None:
    images = page_images(image_pdf(corner_page((255, 0, 0)), corner_page((0, 0, 255))))

    assert [image.index for image in images] == [1, 2]
    for image in images:
        assert Image.open(io.BytesIO(image.jpeg)).format == "JPEG"


def test_a_long_pdf_is_truncated_not_refused() -> None:
    content = image_pdf(*(blank_page() for _ in range(6)))

    images = page_images(content, max_pages=4)

    assert [image.index for image in images] == [1, 2, 3, 4]
    assert page_count(content) == 6


def test_a_page_image_is_capped_on_its_long_edge() -> None:
    content = image_pdf(Image.new("RGB", (2000, 1000), "white"))

    [image] = page_images(content, dpi=300, max_edge=200)

    assert max(Image.open(io.BytesIO(image.jpeg)).size) == 200


def test_a_figure_is_cropped_from_the_top_left() -> None:
    content = drawn_pdf(image=(60.0, 500.0, 290.0, 780.0))

    red, green, blue = centre(figure(content, page=1, bbox=(0.1, 0.1, 0.4, 0.4)).jpeg)

    assert red > 200
    assert green < 60
    assert blue < 60


def test_a_box_low_on_the_page_is_not_the_top_one() -> None:
    content = drawn_pdf(image=(60.0, 500.0, 290.0, 780.0))

    red, green, blue = centre(figure(content, page=1, bbox=(0.6, 0.6, 0.9, 0.9)).jpeg)

    assert min(red, green, blue) > 200


def test_a_box_that_spills_into_the_prose_snaps_back_to_the_image() -> None:
    result = figure(figure_page(), page=1, bbox=(0.1, 0.14, 0.9, 0.62))

    assert result.snapped is True
    assert all_red(result.jpeg)
    width, height = span(result.jpeg)
    assert 300 <= width <= 310
    assert 200 <= height <= 210


def test_a_box_with_nothing_drawn_in_it_keeps_its_edges_less_the_prose() -> None:
    content = drawn_pdf(
        texts=[(60, 700, 12, "Prose the box ran into"), (60, 686, 12, "over two lines")]
    )

    result = figure(content, page=1, bbox=(0.1, 0.16, 0.9, 0.41))

    assert result.snapped is False
    assert darkest(result.jpeg) > 150
    _, height = span(result.jpeg)
    assert 190 <= height <= 208


def test_prose_below_an_unsnapped_box_is_trimmed_off_its_foot() -> None:
    content = drawn_pdf(
        texts=[(60, 400, 12, "Prose under the figure"), (60, 386, 12, "over two lines")]
    )

    result = figure(content, page=1, bbox=(0.1, 0.2874, 0.9, 0.5368))

    assert result.snapped is False
    assert darkest(result.jpeg) > 150
    _, height = span(result.jpeg)
    assert 195 <= height <= 210


def test_a_box_that_is_prose_all_the_way_down_keeps_what_it_had() -> None:
    content = drawn_pdf(texts=[(60, 700, 12, "Prose"), (60, 686, 12, "and more prose")])

    result = figure(content, page=1, bbox=(0.1, 0.1556, 0.9, 0.1888))

    assert result.snapped is False
    assert darkest(result.jpeg) < 100


def test_width_mm_is_the_figure_s_width_on_its_own_page() -> None:
    content = drawn_pdf(image=(100.0, 400.0, 100.0 + PAGE_WIDTH / 2, 600.0))

    result = figure(content, page=1, bbox=(0.1, 0.2, 0.9, 0.7))

    assert abs(result.width_mm - PAGE_MM / 2) <= 2


def test_a_full_bleed_box_is_capped_at_the_text_column() -> None:
    content = drawn_pdf(texts=[(60, 700, 12, "Prose")])

    assert figure(content, page=1, bbox=(0.0, 0.0, 1.0, 1.0)).width_mm == MAX_FIGURE_WIDTH_MM


def test_page_furniture_does_not_capture_the_crop() -> None:
    content = drawn_pdf(image=(200.0, 500.0, 320.0, 580.0), rects=[(20.0, 20.0, 575.0, 822.0)])

    result = figure(content, page=1, bbox=(0.05, 0.2, 0.95, 0.6))

    assert result.snapped is True
    assert result.width_mm < 50
    assert all_red(result.jpeg)


def test_a_rule_across_the_page_is_furniture_and_a_small_path_is_the_figure() -> None:
    content = drawn_pdf(rects=[(39.0, 76.0, 556.0, 76.5), (200.0, 500.0, 320.0, 580.0)])

    result = figure(content, page=1, bbox=(0.05, 0.2, 0.95, 0.95))

    assert result.snapped is True
    assert result.width_mm < 50


def test_an_inverted_box_is_read_the_right_way_round() -> None:
    content = drawn_pdf(image=(60.0, 500.0, 290.0, 780.0))

    upright = figure(content, page=1, bbox=(0.1, 0.1, 0.4, 0.4)).jpeg
    inverted = figure(content, page=1, bbox=(0.4, 0.4, 0.1, 0.1)).jpeg

    assert Image.open(io.BytesIO(inverted)).size == Image.open(io.BytesIO(upright)).size


def test_a_box_outside_the_page_is_clamped_to_it() -> None:
    content = text_pdf([(60, 700, 12, "Prose")])

    whole = figure(content, page=1, bbox=(-3.0, -3.0, 4.0, 4.0)).jpeg
    page = figure(content, page=1, bbox=(0.0, 0.0, 1.0, 1.0)).jpeg

    assert Image.open(io.BytesIO(whole)).size == Image.open(io.BytesIO(page)).size


def test_a_degenerate_box_is_refused() -> None:
    content = drawn_pdf(image=(60.0, 500.0, 290.0, 780.0))

    with pytest.raises(IngestError):
        figure(content, page=1, bbox=(0.5, 0.5, 0.5, 0.5))


def test_a_box_that_is_not_a_box_is_refused() -> None:
    content = drawn_pdf(image=(60.0, 500.0, 290.0, 780.0))

    with pytest.raises(IngestError):
        figure(content, page=1, bbox=(0.1, 0.1, float("nan"), 0.4))


def test_a_page_the_pdf_does_not_have_is_refused() -> None:
    content = drawn_pdf(image=(60.0, 500.0, 290.0, 780.0))

    with pytest.raises(IngestError):
        figure(content, page=2, bbox=(0.1, 0.1, 0.4, 0.4))
    with pytest.raises(IngestError):
        figure(content, page=0, bbox=(0.1, 0.1, 0.4, 0.4))


@pytest.mark.parametrize(
    "call",
    [
        layout_text,
        page_count,
        raster_page_count,
        raster_pages,
        needs_page_images,
        page_images,
        lambda content: figure(content, page=1, bbox=(0.1, 0.1, 0.4, 0.4)),
    ],
)
def test_bytes_that_are_not_a_pdf_are_an_ingest_error(call: Callable[[bytes], object]) -> None:
    with pytest.raises(IngestError):
        call(b"not a pdf at all")


def test_a_page_with_no_text_reads_as_nothing() -> None:
    assert layout_text(image_pdf(corner_page((255, 0, 0)))) == ""
