from __future__ import annotations

import base64
import io
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import httpx2
import pytest
from anthropic import AsyncAnthropic
from PIL import Image
from pydantic import ValidationError
from sidereal_core.canonical import (
    CanonicalCodeBlock,
    CanonicalFigureBlock,
    CanonicalPaper,
    CanonicalPart,
    CanonicalQuestion,
    CanonicalSection,
    CanonicalSubPart,
)
from sidereal_core.models import Collection, Document
from sidereal_core.testing import FakeDirectus, FakeTypeset
from sidereal_core.typeset import MAX_ASSET_BYTES
from sidereal_generate.base import GenerationError
from sidereal_generate.claude import NO_PAGES, AnthropicPaperExtractor
from sidereal_generate.fake import FakePaperExtractor
from sidereal_generate.models import FigureRequest, PaperExtraction
from sidereal_generate.papers import PaperError, extract_paper, paper_worksheet, rerender_paper
from sidereal_generate.typst_maths import normalise_model
from sidereal_generate.usage import UsageTally

DOCUMENT_ID = UUID("22222222-2222-4222-8222-222222222222")
PAGE_WIDTH = 595
PAGE_HEIGHT = 842


def image_pdf(pages: int = 1) -> bytes:
    """A PDF whose every page carries a raster image, which is what auto mode keys on."""
    drawn = [Image.new("RGB", (240, 160), "white") for _ in range(pages)]
    buffer = io.BytesIO()
    drawn[0].save(buffer, format="PDF", save_all=pages > 1, append_images=drawn[1:])
    return buffer.getvalue()


def text_pdf(text: str = "1. A question.") -> bytes:
    """A PDF of text alone, written by hand so nothing rasterises into it."""
    stream = f"BT /F1 12 Tf 1 0 0 1 72 720 Tm ({text}) Tj ET\n"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        f"<< /Length {len(stream)} >>\nstream\n{stream}endstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
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
    out.write(
        f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()
    )
    return out.getvalue()


def seeded(pdf: bytes | None = None, *, filename: str = "paper.pdf") -> FakeDirectus:
    fake = FakeDirectus()
    file_id = (
        None if pdf is None else fake.register_file(filename, pdf, media_type="application/pdf")
    )
    fake.seed(
        Collection.DOCUMENTS,
        {
            "id": str(DOCUMENT_ID),
            "title": "Mock paper 1",
            "kind": "upload",
            "status": "ready",
            "text": "1. A question.",
            "file": file_id,
        },
    )
    return fake


class Extractor(FakePaperExtractor):
    """Says what pages it was handed, and returns the figure requests it was given."""

    def __init__(
        self, figures: Sequence[FigureRequest] = (), *, paper: CanonicalPaper | None = None
    ) -> None:
        self.pages: list[tuple[bytes, ...]] = []
        self.drawn: list[tuple[int, ...]] = []
        self._figures = tuple(figures)
        self._paper = paper

    async def extract(
        self,
        document: Document,
        *,
        pages: Sequence[bytes] = (),
        drawn: Sequence[int] = (),
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        self.pages.append(tuple(pages))
        self.drawn.append(tuple(drawn))
        extraction = await super().extract(document, usage=usage)
        update: dict[str, Any] = {"figures": self._figures}
        if self._paper is not None:
            update["paper"] = self._paper
        return extraction.model_copy(update=update)


async def extracted(
    fake: FakeDirectus,
    typeset: FakeTypeset,
    extractor: Extractor,
    *,
    pages: bool | None = None,
) -> UUID:
    async with fake.client() as client:
        return await extract_paper(
            client, extractor, typeset.client(), DOCUMENT_ID, {}, pages=pages
        )


def figure(**overrides: Any) -> FigureRequest:
    return FigureRequest.model_validate(
        {
            "page": 1,
            "bbox": [0.1, 0.1, 0.8, 0.6],
            "caption": "Figure 1",
            "question_number": "1",
            "part_label": None,
            **overrides,
        }
    )


def rendered_paper(typeset: FakeTypeset) -> dict[str, Any]:
    return [call for call in typeset.rendered if call["kind"] == "paper"][-1]


async def test_auto_mode_sends_the_pages_of_a_paper_that_is_drawn_rather_than_written() -> None:
    fake, extractor = seeded(image_pdf(2)), Extractor()

    await extracted(fake, FakeTypeset(), extractor)

    assert len(extractor.pages[0]) == 2
    assert all(page.startswith(b"\xff\xd8") for page in extractor.pages[0])


async def test_auto_mode_reads_a_paper_that_is_only_text_as_text() -> None:
    fake, extractor = seeded(text_pdf()), Extractor()

    await extracted(fake, FakeTypeset(), extractor)

    assert extractor.pages == [()]


async def test_a_document_with_no_file_is_read_as_text() -> None:
    fake, extractor = seeded(None), Extractor()

    await extracted(fake, FakeTypeset(), extractor)

    assert extractor.pages == [()]


async def test_asking_for_pages_of_a_document_that_has_no_pdf_says_so() -> None:
    fake, extractor = seeded(None), Extractor()

    with pytest.raises(PaperError, match="no PDF"):
        await extracted(fake, FakeTypeset(), extractor, pages=True)

    # A file that is not a PDF is not one to rasterise either.
    other = seeded(image_pdf(), filename="paper.png")
    with pytest.raises(PaperError, match="no PDF"):
        await extracted(other, FakeTypeset(), Extractor(), pages=True)


async def test_pages_off_reads_a_drawn_paper_as_text_anyway() -> None:
    fake, extractor = seeded(image_pdf()), Extractor()

    await extracted(fake, FakeTypeset(), extractor, pages=False)

    assert extractor.pages == [()]


async def test_a_figure_request_is_cropped_filed_and_placed_on_its_question() -> None:
    fake, typeset = seeded(image_pdf()), FakeTypeset()

    paper_id = await extracted(fake, typeset, Extractor([figure()]), pages=True)

    structure = fake.items[Collection.PAPERS][str(paper_id)]["structure"]
    block = structure["questions"][0]["blocks"][0]
    assert block["type"] == "figure"
    assert block["caption"] == "Figure 1"
    # The service refuses a bare id: an asset name is a file name.
    file_id, suffix = block["asset"].rsplit(".", 1)
    assert suffix == "jpg"
    row, content = fake.files[file_id]
    assert row["type"] == "image/jpeg"
    assert row["title"] == "Figure 1"
    assert content.startswith(b"\xff\xd8")


async def test_a_figure_can_be_placed_on_a_part() -> None:
    fake, typeset = seeded(image_pdf()), FakeTypeset()

    paper_id = await extracted(fake, typeset, Extractor([figure(part_label="a")]), pages=True)

    question = fake.items[Collection.PAPERS][str(paper_id)]["structure"]["questions"][0]
    assert question["blocks"] == []
    assert question["parts"][0]["label"] == "a"
    assert question["parts"][0]["blocks"][0]["type"] == "figure"


async def test_a_figure_can_be_placed_on_a_sub_part() -> None:
    """A sub-part is a model of its own, and a figure still reaches the second level."""
    fake, typeset = seeded(image_pdf()), FakeTypeset()
    nested = CanonicalPaper(
        title="Nested paper",
        questions=(
            CanonicalQuestion(
                number="1",
                stem="A question.",
                parts=(
                    CanonicalPart(
                        label="a",
                        text="The first part.",
                        parts=(CanonicalSubPart(label="i", text="The first sub-part."),),
                    ),
                ),
            ),
        ),
    )

    paper_id = await extracted(
        fake,
        typeset,
        Extractor([figure(part_label="i")], paper=nested),
        pages=True,
    )

    part = fake.items[Collection.PAPERS][str(paper_id)]["structure"]["questions"][0]["parts"][0]
    assert part["blocks"] == []
    assert part["parts"][0]["blocks"][0]["type"] == "figure"


async def test_a_figure_naming_a_question_the_paper_has_not_got_is_dropped() -> None:
    fake, typeset = seeded(image_pdf()), FakeTypeset()

    paper_id = await extracted(fake, typeset, Extractor([figure(question_number="99")]), pages=True)

    structure = fake.items[Collection.PAPERS][str(paper_id)]["structure"]
    assert all(question["blocks"] == [] for question in structure["questions"])
    # The crop was still filed; the paper is the work, and a figure with no home is not a failure.
    assert [row["type"] for row, _ in fake.files.values()].count("image/jpeg") == 1


async def test_the_figure_bytes_go_to_the_renderer_with_the_structure() -> None:
    fake, typeset = seeded(image_pdf()), FakeTypeset()

    paper_id = await extracted(fake, typeset, Extractor([figure()]), pages=True)

    structure = fake.items[Collection.PAPERS][str(paper_id)]["structure"]
    name = structure["questions"][0]["blocks"][0]["asset"]
    assets = rendered_paper(typeset)["assets"]
    assert list(assets) == [name]
    assert base64.b64decode(assets[name]) == fake.files[name.removesuffix(".jpg")][1]


def paper_with(fake: FakeDirectus, *blocks: CanonicalFigureBlock) -> UUID:
    structure = CanonicalPaper(
        title="Paper with a figure",
        questions=(CanonicalQuestion(number="1", stem="A question.", blocks=blocks),),
    )
    row = fake.seed(
        Collection.PAPERS,
        {
            "title": structure.title,
            "status": "draft",
            "structure": structure.model_dump(mode="json"),
        },
    )
    return UUID(row["id"])


async def test_an_asset_over_the_limit_is_left_out_and_its_block_with_it() -> None:
    fake, typeset = FakeDirectus(), FakeTypeset()
    big = fake.register_file(
        "figure-1.jpg", b"\xff\xd8" + b"x" * MAX_ASSET_BYTES, media_type="image/jpeg"
    )
    paper_id = paper_with(fake, CanonicalFigureBlock(asset=f"{big}.jpg", caption="Figure 1"))

    async with fake.client() as client:
        paper = await rerender_paper(client, typeset.client(), paper_id, FakePaperExtractor())

    sent = rendered_paper(typeset)
    assert "assets" not in sent
    assert sent["document"]["questions"][0]["blocks"] == []
    # The reference stays on the row, so a later render with room prints it.
    assert (paper.structure or {})["questions"][0]["blocks"][0]["asset"] == f"{big}.jpg"


async def test_a_figure_whose_file_is_gone_does_not_stop_the_render() -> None:
    fake, typeset = FakeDirectus(), FakeTypeset()
    paper_id = paper_with(
        fake, CanonicalFigureBlock(asset="66666666-6666-4666-8666-666666666666.jpg")
    )

    async with fake.client() as client:
        await rerender_paper(client, typeset.client(), paper_id, FakePaperExtractor())

    assert rendered_paper(typeset)["document"]["questions"][0]["blocks"] == []


async def test_a_worksheet_carries_the_figures_of_the_questions_it_takes() -> None:
    fake, typeset = FakeDirectus(), FakeTypeset()
    file_id = fake.register_file("figure-1.jpg", b"\xff\xd8jpeg", media_type="image/jpeg")
    paper_id = paper_with(fake, CanonicalFigureBlock(asset=f"{file_id}.jpg"))

    async with fake.client() as client:
        result = await paper_worksheet(client, typeset.client(), paper_id, ["1"])

    worksheet = [call for call in typeset.rendered if call["kind"] == "worksheet"][-1]
    assert list(worksheet["assets"]) == [f"{file_id}.jpg"]
    # The PDF is rendered with its assets, never compiled from a source that has none.
    assert typeset.compiled == []
    assert fake.files[str(result.pdf_file_id)][1].startswith(b"%PDF")


async def test_a_sectioned_paper_still_files_a_row_for_every_question() -> None:
    fake, typeset = seeded(None), FakeTypeset()
    sectioned = CanonicalPaper(
        title="Sectioned paper",
        questions=(CanonicalQuestion(number="1", stem="A loose question."),),
        sections=(
            CanonicalSection(
                title="Section A",
                choose=1,
                questions=(
                    CanonicalQuestion(number="01", stem="The first choice.", marks=25),
                    CanonicalQuestion(
                        number="02",
                        stem="The second choice.",
                        parts=(CanonicalPart(label="a", text="Say why."),),
                    ),
                ),
            ),
        ),
    )

    paper_id = await extracted(fake, typeset, Extractor(paper=sectioned))

    rows = fake.rows(Collection.QUESTIONS)
    assert [row["number"] for row in rows] == ["1", "01", "02"]
    assert all(row["paper"] == str(paper_id) for row in rows)
    assert rows[2]["parts"][0]["label"] == "a"


async def test_a_worksheet_can_take_a_question_that_lives_in_a_section() -> None:
    fake, typeset = seeded(None), FakeTypeset()
    sectioned = CanonicalPaper(
        title="Sectioned paper",
        sections=(
            CanonicalSection(title="Section A", questions=(CanonicalQuestion(number="01"),)),
        ),
    )
    paper_id = await extracted(fake, typeset, Extractor(paper=sectioned))

    async with fake.client() as client:
        await paper_worksheet(client, typeset.client(), paper_id, ["01"])

    worksheet = [call for call in typeset.rendered if call["kind"] == "worksheet"][-1]
    assert [question["number"] for question in worksheet["document"]["questions"]] == ["01"]


def test_a_code_block_keeps_its_dollars() -> None:
    paper = CanonicalPaper(
        title="Listing",
        questions=(
            CanonicalQuestion(
                number="1",
                stem="Read the program. Find $dy/dx$.",
                blocks=(
                    CanonicalCodeBlock(
                        language="bash", text="total=$(wc -l < data)\necho $total  # PQ"
                    ),
                ),
            ),
        ),
    )

    fixed = normalise_model(paper)

    listing = fixed.questions[0].blocks[0]
    assert isinstance(listing, CanonicalCodeBlock)
    assert listing.text == "total=$(wc -l < data)\necho $total  # PQ"
    assert fixed.questions[0].stem == "Read the program. Find $dif y/dif x$."


async def test_the_drawn_pages_are_named_to_the_extractor_by_number() -> None:
    fake, extractor = seeded(image_pdf(2)), Extractor()

    await extracted(fake, FakeTypeset(), extractor, pages=True)

    assert extractor.drawn == [(1, 2)]


async def test_a_paper_whose_pages_carry_nothing_drawn_names_none() -> None:
    fake, extractor = seeded(text_pdf()), Extractor()

    await extracted(fake, FakeTypeset(), extractor, pages=True)

    assert len(extractor.pages[0]) == 1
    assert extractor.drawn == [()]


async def test_a_backend_that_cannot_see_a_page_says_which_one_can() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:  # pragma: no cover - never called
        raise AssertionError("no request is made for pages this backend cannot read")

    extractor = AnthropicPaperExtractor(
        client=AsyncAnthropic(
            api_key="test-key",
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
        ),
        model="claude-sonnet-5",
    )

    with pytest.raises(GenerationError, match="openrouter"):
        await extractor.extract(
            Document.model_validate(
                {"id": str(DOCUMENT_ID), "title": "Mock paper 1", "kind": "upload", "text": "1."}
            ),
            pages=[b"\xff\xd8jpeg"],
        )
    assert "SIDEREAL_GENERATE_BACKEND=openrouter" in NO_PAGES


async def test_a_file_that_is_not_really_a_pdf_stops_a_page_read_and_not_a_text_one() -> None:
    fake, extractor = seeded(b"%PDF-1.4 truncated"), Extractor()

    with pytest.raises(PaperError, match="could not be opened"):
        await extracted(fake, FakeTypeset(), extractor, pages=True)

    # Auto mode falls back to the text the document already carries.
    await extracted(fake, FakeTypeset(), extractor)
    assert extractor.pages[-1] == ()


async def test_a_crop_that_cannot_be_taken_is_dropped() -> None:
    fake, typeset = seeded(image_pdf()), FakeTypeset()

    paper_id = await extracted(
        fake, typeset, Extractor([figure(page=99), figure(bbox=[0.5, 0.5, 0.5, 0.5])]), pages=True
    )

    structure = fake.items[Collection.PAPERS][str(paper_id)]["structure"]
    assert structure["questions"][0]["blocks"] == []


async def test_an_asset_that_does_not_name_a_file_is_left_out() -> None:
    fake, typeset = FakeDirectus(), FakeTypeset()
    paper_id = paper_with(fake, CanonicalFigureBlock(asset="figure-1.jpg"))

    async with fake.client() as client:
        await rerender_paper(client, typeset.client(), paper_id, FakePaperExtractor())

    assert rendered_paper(typeset)["document"]["questions"][0]["blocks"] == []


def test_a_box_that_is_not_four_finite_numbers_is_refused() -> None:
    with pytest.raises(ValidationError, match="four finite numbers"):
        figure(bbox=[0.1, 0.2, 0.3])
    with pytest.raises(ValidationError, match="four finite numbers"):
        figure(bbox=[0.1, 0.2, 0.3, float("inf")])
