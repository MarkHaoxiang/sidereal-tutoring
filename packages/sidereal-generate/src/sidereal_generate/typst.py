"""The Typst path: a generated body, wrapped in the house template, compiled and filed."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sidereal_core.directus import DirectusClient
from sidereal_core.models import Collection, Homework, HomeworkFormat
from sidereal_core.typeset import TypesetClient, TypesetError

from sidereal_generate.base import HomeworkGenerator
from sidereal_generate.models import GenerationRequest, HomeworkOutput
from sidereal_generate.usage import UsageTally

PDF_TYPE = "application/pdf"
RETRY_NOTE = (
    "Your previous answer did not compile. Return the whole body again, corrected. "
    "The Typst compiler reported:"
)
TYPST_WARNING = (
    "The Typst source did not compile, so this homework has no PDF. "
    "The compiler's report is in compile_error."
)


class NotTypstError(Exception):
    """A homework row asked to be compiled that is not written in Typst."""


@dataclass(frozen=True, slots=True)
class Compiled:
    """A wrapped Typst source and the PDF it produced, or what stopped it."""

    source: str
    pdf: bytes | None
    error: str | None


async def compile_body(
    typeset: TypesetClient, *, title: str, student: str, due: date | None, body: str
) -> Compiled:
    """Wrap a body in the house template and compile it. A compile error is a value, not a raise."""
    source = await typeset.wrap_homework(title=title, student=student, due=due, body=body)
    try:
        return Compiled(source, await typeset.compile_pdf(source), None)
    except TypesetError as exc:
        return Compiled(source, None, str(exc))


async def generate_typst(
    generator: HomeworkGenerator,
    typeset: TypesetClient,
    request: GenerationRequest,
    *,
    due: date | None = None,
    usage: UsageTally | None = None,
) -> tuple[HomeworkOutput, Compiled]:
    """One attempt, then one retry with the diagnostics in the prompt. Then whatever we have."""
    output = await generator.generate(request, usage=usage)
    compiled = await _compile(typeset, output, request, due)
    if compiled.error is None:
        return output, compiled
    retry = request.model_copy(update={"instructions": _with_diagnostics(request, compiled.error)})
    output = await generator.generate(retry, usage=usage)
    return output, await _compile(typeset, output, retry, due)


async def upload_pdf(client: DirectusClient, title: str, pdf: bytes) -> UUID:
    uploaded = await client.upload_file(f"{slug(title)}.pdf", pdf, PDF_TYPE, title=title)
    return uploaded.id


async def recompile_homework(
    client: DirectusClient, typeset: TypesetClient, homework_id: UUID
) -> Homework:
    """Compile a row's `content` again. A failure keeps the PDF that is already there."""
    homework = await client.get_item(Collection.HOMEWORK, Homework, homework_id)
    if homework.format is not HomeworkFormat.TYPST:
        raise NotTypstError(
            "This homework is not written in Typst, so there is nothing to compile."
        )
    try:
        pdf = await typeset.compile_pdf(homework.content)
    except TypesetError as exc:
        return await _patch(client, homework_id, {"compile_error": str(exc)})
    file_id = await upload_pdf(client, homework.title, pdf)
    return await _patch(client, homework_id, {"pdf": str(file_id), "compile_error": None})


def slug(title: str) -> str:
    """A title as a filename a tutor can recognise in their downloads folder."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "homework"


async def _patch(client: DirectusClient, homework_id: UUID, data: dict[str, object]) -> Homework:
    return await client.update_item(Collection.HOMEWORK, Homework, homework_id, data)


async def _compile(
    typeset: TypesetClient, output: HomeworkOutput, request: GenerationRequest, due: date | None
) -> Compiled:
    return await compile_body(
        typeset,
        title=output.title,
        student=request.student.name,
        due=due,
        body=output.content,
    )


def _with_diagnostics(request: GenerationRequest, error: str) -> str:
    parts = [request.instructions, f"{RETRY_NOTE}\n{error}"]
    return "\n\n".join(part for part in parts if part)
