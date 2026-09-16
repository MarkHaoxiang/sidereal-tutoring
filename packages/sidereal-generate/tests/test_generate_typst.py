from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from sidereal_core.models import Collection, GenerationKind, HomeworkFormat, JobStatus, Student
from sidereal_core.testing import FAIL_MARKER, FakeDirectus, FakeTypeset
from sidereal_generate.fake import (
    FakeFeedbackGenerator,
    FakeHomeworkGenerator,
    FakePaperExtractor,
    FakePlanGenerator,
)
from sidereal_generate.jobs import Generators, JobInput, run_job, start_job
from sidereal_generate.models import GeneratedQuestion, GenerationRequest, HomeworkOutput
from sidereal_generate.typst import NotTypstError, recompile_homework, slug
from sidereal_generate.usage import UsageTally

STUDENT_ID = UUID("11111111-1111-4111-8111-111111111111")
GOOD_BODY = "#question[Factorise $x^2 - 5x + 6$.]\n#answerlines(4)\n"
BAD_BODY = f"#question[Factorise $x^2 - 5x + 6$.]\n{FAIL_MARKER}\n"


def homework(content: str) -> HomeworkOutput:
    return HomeworkOutput(
        title="Quadratics: week 3",
        content=content,
        questions=(
            GeneratedQuestion(
                text="Factorise x^2 - 5x + 6.", answer="(x-2)(x-3)", topic="algebra", difficulty=2
            ),
        ),
    )


class SequenceGenerator:
    """One output per call, in order. The last one repeats."""

    model = "fake-homework"

    def __init__(self, *outputs: HomeworkOutput) -> None:
        self.outputs = outputs
        self.requests: list[GenerationRequest] = []

    async def generate(
        self, request: GenerationRequest, *, usage: UsageTally | None = None
    ) -> HomeworkOutput:
        self.requests.append(request)
        if usage is not None:
            usage.record(prompt_tokens=1, completion_tokens=2, cost_usd=0.5)
        return self.outputs[min(len(self.requests) - 1, len(self.outputs) - 1)]


def generators(homework_generator: SequenceGenerator) -> Generators:
    return Generators(
        homework=homework_generator,
        feedback=FakeFeedbackGenerator(),
        plan=FakePlanGenerator(),
        paper=FakePaperExtractor(),
    )


def seeded() -> tuple[FakeDirectus, JobInput]:
    fake = FakeDirectus()
    student = fake.seed(Collection.STUDENTS, {"name": "A. Tutee", "subjects": ["maths"]})
    return fake, JobInput(
        student=UUID(student["id"]),
        instructions="Six questions.",
        format=HomeworkFormat.TYPST,
    )


async def run(
    fake: FakeDirectus, job_input: JobInput, generator: SequenceGenerator
) -> dict[str, Any]:
    typeset = FakeTypeset().client()
    async with fake.client() as client:
        job = await start_job(client, GenerationKind.HOMEWORK, job_input, model="fake-homework")
        finished = await run_job(client, generators(generator), job.id, typeset=typeset)
    assert finished.status is JobStatus.SUCCEEDED
    return fake.rows(Collection.HOMEWORK)[0]


async def test_a_typst_job_stores_the_source_and_links_the_compiled_pdf() -> None:
    fake, job_input = seeded()

    row = await run(fake, job_input, SequenceGenerator(homework(GOOD_BODY)))

    assert row["format"] == "typst"
    assert row.get("compile_error") is None
    assert GOOD_BODY.strip() in row["content"]
    assert "Quadratics: week 3" in row["content"]
    stored_row, stored_bytes = fake.files[row["pdf"]]
    assert stored_bytes.startswith(b"%PDF")
    assert stored_row["filename_download"] == "quadratics-week-3.pdf"
    assert stored_row["title"] == "Quadratics: week 3"


async def test_a_body_that_fails_is_generated_again_with_the_diagnostics() -> None:
    fake, job_input = seeded()
    generator = SequenceGenerator(homework(BAD_BODY), homework(GOOD_BODY))

    row = await run(fake, job_input, generator)

    assert len(generator.requests) == 2
    retry = generator.requests[1].instructions or ""
    assert "Six questions." in retry
    assert "did not compile" in retry
    assert "does-not-compile" in retry
    assert row.get("compile_error") is None
    assert row["pdf"]


async def test_a_body_that_never_compiles_is_still_written_with_the_report() -> None:
    fake, job_input = seeded()
    generator = SequenceGenerator(homework(BAD_BODY))

    row = await run(fake, job_input, generator)

    assert len(generator.requests) == 2
    assert row["format"] == "typst"
    assert row.get("pdf") is None
    assert "does-not-compile" in row["compile_error"]
    assert FAIL_MARKER in row["content"]
    assert "warning" in row["generated_from"]
    assert fake.files == {}


async def test_a_markdown_job_touches_neither_format_nor_the_typeset_service() -> None:
    fake, job_input = seeded()
    typeset = FakeTypeset()

    async with fake.client() as client:
        job = await start_job(
            client,
            GenerationKind.HOMEWORK,
            job_input.model_copy(update={"format": HomeworkFormat.MARKDOWN}),
            model="fake-homework",
        )
        await run_job(
            client,
            generators(SequenceGenerator(homework("## Quadratics"))),
            job.id,
            typeset=typeset.client(),
        )

    row = fake.rows(Collection.HOMEWORK)[0]
    assert row["format"] == "markdown"
    assert row["content"] == "## Quadratics"
    assert typeset.compiled == []


async def test_the_fake_backends_typst_body_compiles_and_uses_only_the_house_helpers() -> None:
    request = GenerationRequest(
        student=Student(id=STUDENT_ID, name="A_Tutee [maths]"), format=HomeworkFormat.TYPST
    )
    typeset = FakeTypeset()

    output = await FakeHomeworkGenerator().generate(request)
    async with typeset.client() as client:
        source = await client.wrap_homework(
            title=output.title, student=request.student.name, due=None, body=output.content
        )
        assert (await client.compile_pdf(source)).startswith(b"%PDF")

    assert "#question[" in output.content
    assert "#answerlines(" in output.content
    assert "#import" not in output.content
    assert "#set page" not in output.content
    # A name is characters, not markup: nothing a tutor types can open emphasis or a call.
    assert "A\\_Tutee \\[maths\\]" in output.content


async def test_recompiling_replaces_the_pdf_and_clears_the_error() -> None:
    fake = FakeDirectus()
    stale = fake.register_file("quadratics-week-3.pdf", b"%PDF-old", media_type="application/pdf")
    row = fake.seed(
        Collection.HOMEWORK,
        {
            "student": str(STUDENT_ID),
            "title": "Quadratics: week 3",
            "content": GOOD_BODY,
            "format": "typst",
            "pdf": stale,
            "compile_error": "the last attempt failed",
        },
    )

    async with fake.client() as client:
        updated = await recompile_homework(client, FakeTypeset().client(), UUID(row["id"]))

    assert updated.compile_error is None
    assert str(updated.pdf) != stale
    assert fake.files[str(updated.pdf)][1].startswith(b"%PDF")


async def test_a_recompile_that_fails_keeps_the_pdf_that_is_already_there() -> None:
    fake = FakeDirectus()
    current = fake.register_file("quadratics-week-3.pdf", b"%PDF-old", media_type="application/pdf")
    row = fake.seed(
        Collection.HOMEWORK,
        {
            "student": str(STUDENT_ID),
            "title": "Quadratics: week 3",
            "content": BAD_BODY,
            "format": "typst",
            "pdf": current,
            "compile_error": None,
        },
    )

    async with fake.client() as client:
        updated = await recompile_homework(client, FakeTypeset().client(), UUID(row["id"]))

    assert str(updated.pdf) == current
    assert updated.compile_error is not None
    assert "does-not-compile" in updated.compile_error


async def test_a_markdown_row_has_nothing_to_compile() -> None:
    fake = FakeDirectus()
    row = fake.seed(
        Collection.HOMEWORK,
        {"student": str(STUDENT_ID), "title": "Week 3", "content": "## Quadratics"},
    )

    async with fake.client() as client:
        with pytest.raises(NotTypstError, match="not written in Typst"):
            await recompile_homework(client, FakeTypeset().client(), UUID(row["id"]))


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Quadratics: week 3", "quadratics-week-3"),
        ("  — ", "homework"),
        ("Trigonometry (sin/cos)", "trigonometry-sin-cos"),
    ],
)
def test_a_title_becomes_a_filename_a_tutor_recognises(title: str, expected: str) -> None:
    assert slug(title) == expected
