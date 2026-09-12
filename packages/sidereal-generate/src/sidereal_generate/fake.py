"""Generators that call nothing: the `fake` backend, and the doubles tests inject."""

from __future__ import annotations

from pydantic import BaseModel
from sidereal_core.models import HomeworkFormat

from sidereal_generate.models import (
    FeedbackOutput,
    GeneratedQuestion,
    GenerationRequest,
    HomeworkOutput,
    PlanOutput,
)

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

    async def generate(self, request: GenerationRequest) -> OutputT:
        self.requests.append(request)
        return self.output


class FailingGenerator[OutputT: BaseModel]:
    def __init__(self, error: Exception, *, model: str = FAKE_MODEL) -> None:
        self.error = error
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, request: GenerationRequest) -> OutputT:
        raise self.error


class FakeHomeworkGenerator:
    """The `fake` backend. Well-formed homework that never claims to be generated."""

    model = FAKE_MODEL

    async def generate(self, request: GenerationRequest) -> HomeworkOutput:
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

    async def generate(self, request: GenerationRequest) -> FeedbackOutput:
        return FeedbackOutput(content=_content("Feedback", request))


class FakePlanGenerator:
    model = FAKE_MODEL

    async def generate(self, request: GenerationRequest) -> PlanOutput:
        return PlanOutput(
            title=f"{FAKE_PREFIX} Study plan for {request.student.name}",
            content=_content("Study plan", request),
        )


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
