from __future__ import annotations

import io
from collections.abc import Callable, Sequence

import pypdfium2
import pytest
from PIL import Image
from sidereal_ingest.base import IngestError
from sidereal_ingest.pdf import (
    crop_figure,
    layout_text,
    needs_page_images,
    page_count,
    page_images,
    raster_page_count,
    raster_pages,
)

PAGE_WIDTH = 595
PAGE_HEIGHT = 842

type Draw = tuple[float, float, float, str]


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
    content = image_pdf(corner_page((255, 0, 0)))

    red, green, blue = centre(crop_figure(content, page=1, bbox=(0.1, 0.1, 0.4, 0.4)))

    assert red > 200
    assert green < 60
    assert blue < 60


def test_a_box_low_on_the_page_is_not_the_top_one() -> None:
    content = image_pdf(corner_page((255, 0, 0)))

    red, green, blue = centre(crop_figure(content, page=1, bbox=(0.6, 0.6, 0.9, 0.9)))

    assert min(red, green, blue) > 200


def test_an_inverted_box_is_read_the_right_way_round() -> None:
    content = image_pdf(corner_page((255, 0, 0)))

    upright = crop_figure(content, page=1, bbox=(0.1, 0.1, 0.4, 0.4))
    inverted = crop_figure(content, page=1, bbox=(0.4, 0.4, 0.1, 0.1))

    assert Image.open(io.BytesIO(inverted)).size == Image.open(io.BytesIO(upright)).size


def test_a_box_outside_the_page_is_clamped_to_it() -> None:
    content = image_pdf(corner_page((255, 0, 0)))

    whole = crop_figure(content, page=1, bbox=(-3.0, -3.0, 4.0, 4.0))
    page = crop_figure(content, page=1, bbox=(0.0, 0.0, 1.0, 1.0))

    assert Image.open(io.BytesIO(whole)).size == Image.open(io.BytesIO(page)).size


def test_a_degenerate_box_is_refused() -> None:
    content = image_pdf(corner_page((255, 0, 0)))

    with pytest.raises(IngestError):
        crop_figure(content, page=1, bbox=(0.5, 0.5, 0.5, 0.5))


def test_a_box_that_is_not_a_box_is_refused() -> None:
    content = image_pdf(corner_page((255, 0, 0)))

    with pytest.raises(IngestError):
        crop_figure(content, page=1, bbox=(0.1, 0.1, float("nan"), 0.4))


def test_a_page_the_pdf_does_not_have_is_refused() -> None:
    content = image_pdf(corner_page((255, 0, 0)))

    with pytest.raises(IngestError):
        crop_figure(content, page=2, bbox=(0.1, 0.1, 0.4, 0.4))
    with pytest.raises(IngestError):
        crop_figure(content, page=0, bbox=(0.1, 0.1, 0.4, 0.4))


@pytest.mark.parametrize(
    "call",
    [
        layout_text,
        page_count,
        raster_page_count,
        raster_pages,
        needs_page_images,
        page_images,
        lambda content: crop_figure(content, page=1, bbox=(0.1, 0.1, 0.4, 0.4)),
    ],
)
def test_bytes_that_are_not_a_pdf_are_an_ingest_error(call: Callable[[bytes], object]) -> None:
    with pytest.raises(IngestError):
        call(b"not a pdf at all")


def test_a_page_with_no_text_reads_as_nothing() -> None:
    assert layout_text(image_pdf(corner_page((255, 0, 0)))) == ""
