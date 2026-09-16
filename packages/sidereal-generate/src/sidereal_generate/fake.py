"""Generators that call nothing: the `fake` backend, and the doubles tests inject."""

from __future__ import annotations

import re

from pydantic import BaseModel
from sidereal_core.canonical import (
    CanonicalMarkScheme,
    CanonicalMarkSchemePart,
    CanonicalMarkSchemeQuestion,
    CanonicalPaper,
    CanonicalPart,
    CanonicalQuestion,
)
from sidereal_core.models import Document, HomeworkFormat

from sidereal_generate.models import (
    FeedbackOutput,
    GeneratedQuestion,
    GenerationRequest,
    HomeworkOutput,
    PaperExtraction,
    PlanOutput,
)
from sidereal_generate.usage import UsageTally

FAKE_MODEL = "fake"
FAKE_PREFIX = "[fake]"
# Typst reads these as markup; a backslash in front makes each one a character again.
TYPST_SPECIAL = frozenset("\\`#$*_[]<>@=~+-/'\"")


class FakeGenerator[OutputT: BaseModel]:
    def __init__(self, output: OutputT, *, model: str = FAKE_MODEL) -> None:
        self.output = output
        self.requests: list[GenerationRequest] = []
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self, request: GenerationRequest, *, usage: UsageTally | None = None
    ) -> OutputT:
        self.requests.append(request)
        _spend(usage)
        return self.output


class FailingGenerator[OutputT: BaseModel]:
    def __init__(self, error: Exception, *, model: str = FAKE_MODEL) -> None:
        self.error = error
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self, request: GenerationRequest, *, usage: UsageTally | None = None
    ) -> OutputT:
        raise self.error


class FakeHomeworkGenerator:
    """The `fake` backend. Well-formed homework that never claims to be generated."""

    model = FAKE_MODEL

    async def generate(
        self, request: GenerationRequest, *, usage: UsageTally | None = None
    ) -> HomeworkOutput:
        _spend(usage)
        typst = request.format is HomeworkFormat.TYPST
        return HomeworkOutput(
            title=f"{FAKE_PREFIX} Homework for {request.student.name}",
            content=_typst_body(request) if typst else _content("Homework", request),
            questions=(
                GeneratedQuestion(
                    text=f"{FAKE_PREFIX} No question was generated: the fake backend is in use.",
                    answer=None,
                    topic=None,
                    difficulty=1,
                ),
            ),
        )


class FakeFeedbackGenerator:
    model = FAKE_MODEL

    async def generate(
        self, request: GenerationRequest, *, usage: UsageTally | None = None
    ) -> FeedbackOutput:
        _spend(usage)
        return FeedbackOutput(content=_content("Feedback", request))


class FakePlanGenerator:
    model = FAKE_MODEL

    async def generate(
        self, request: GenerationRequest, *, usage: UsageTally | None = None
    ) -> PlanOutput:
        _spend(usage)
        return PlanOutput(
            title=f"{FAKE_PREFIX} Study plan for {request.student.name}",
            content=_content("Study plan", request),
        )


class FakePaperExtractor:
    """The `fake` backend. A small paper that renders, and never claims to be the source's."""

    model = FAKE_MODEL

    async def extract(
        self,
        document: Document,
        mark_scheme: Document | None = None,
        *,
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        _spend(usage)
        title = f"{FAKE_PREFIX} {document.title}"
        return PaperExtraction(
            paper=CanonicalPaper(
                title=title,
                source=document.title,
                board="none",
                year=None,
                time_minutes=30,
                total_marks=7,
                instructions=(
                    "No paper was read: the fake backend is in use. Nothing here is the "
                    "source's own work."
                ),
                questions=(
                    CanonicalQuestion(
                        number="1",
                        stem="The fake backend writes two questions. This is the first.",
                        marks=4,
                        parts=(
                            CanonicalPart(
                                label="a", text="Show that $1 + 1 = 2$.", marks=1, answer_lines=2
                            ),
                            CanonicalPart(
                                label="b", text="Hence find $2 + 2$.", marks=3, answer_lines=4
                            ),
                        ),
                    ),
                    CanonicalQuestion(
                        number="2",
                        stem="Differentiate $y = x^2$ with respect to $x$.",
                        marks=3,
                        answer_lines=5,
                    ),
                ),
            ),
            mark_scheme=CanonicalMarkScheme(
                title=f"{title}: mark scheme",
                questions=(
                    CanonicalMarkSchemeQuestion(
                        number="1",
                        parts=(
                            CanonicalMarkSchemePart(label="a", answer="$1 + 1 = 2$", marks=1),
                            CanonicalMarkSchemePart(label="b", answer="$2 + 2 = 4$", marks=3),
                        ),
                    ),
                    CanonicalMarkSchemeQuestion(number="2", answer="$(d y) / (d x) = 2 x$"),
                ),
            ),
        )

    async def repair(
        self,
        extraction: PaperExtraction,
        diagnostics: str,
        *,
        usage: UsageTally | None = None,
    ) -> PaperExtraction:
        _spend(usage)
        return _repaired(extraction)


def _repaired(extraction: PaperExtraction) -> PaperExtraction:
    """What the fake `repair` returns: the same paper with `$PQ$`-style names spaced."""
    fixed = re.sub(r"\$([A-Z])([A-Z])\$", r"$\1 \2$", extraction.model_dump_json())
    return PaperExtraction.model_validate_json(fixed)


def _spend(usage: UsageTally | None) -> None:
    """A fake call costs nothing, and a tally that counted it would say otherwise."""
    if usage is not None:
        usage.record(prompt_tokens=0, completion_tokens=0, cost_usd=0.0)


def _typst_body(request: GenerationRequest) -> str:
    """A Typst body for the house template: only `#question` and `#answerlines`, and it compiles."""
    material = "\n".join(f"- {_typst(document.title)}" for document in request.documents)
    return (
        f"{_typst(FAKE_PREFIX)} No model was called: the fake backend is in use. "
        "Nothing on this page is real work.\n\n"
        f"Student: {_typst(request.student.name)}\n\n"
        f"Instructions: {_typst(request.instructions or 'none given')}\n\n"
        "Material:\n\n"
        f"{material or '- none'}\n\n"
        "#question[The fake backend writes one question and it is this one. "
        "Show that $1 + 1 = 2$.]\n"
        "#answerlines(3)\n"
    )


def _typst(value: str) -> str:
    """A tutor's words as characters, not as Typst markup."""
    return "".join(f"\\{char}" if char in TYPST_SPECIAL else char for char in value)


def _content(heading: str, request: GenerationRequest) -> str:
    material = "\n".join(f"- {document.title}" for document in request.documents)
    return (
        f"# {FAKE_PREFIX} {heading}\n\n"
        "No model was called: SIDEREAL_GENERATE_BACKEND=fake. Nothing below is real work.\n\n"
        f"- Student: {request.student.name}\n"
        f"- Instructions: {request.instructions or 'none given'}\n\n"
        f"## Material\n\n{material or '- none'}\n"
    )
