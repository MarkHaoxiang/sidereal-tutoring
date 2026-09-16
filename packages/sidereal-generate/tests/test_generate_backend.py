from __future__ import annotations

from uuid import UUID

import pytest
from sidereal_core.models import Document, DocumentKind, Student, StudentStatus
from sidereal_generate.claude import AnthropicGenerator
from sidereal_generate.fake import (
    FAKE_MODEL,
    FAKE_PREFIX,
    FakeFeedbackGenerator,
    FakeHomeworkGenerator,
    FakePlanGenerator,
)
from sidereal_generate.jobs import default_generators
from sidereal_generate.models import GenerationRequest
from sidereal_generate.openrouter import OpenRouterGenerator, OpenRouterPaperExtractor
from sidereal_generate.settings import (
    DEFAULT_EXTRACT_MAX_TOKENS,
    DEFAULT_MAX_TOKENS,
    DEFAULT_OPENROUTER_MODEL,
    GenerateBackend,
    ReasoningEffort,
    generate_settings,
)

STUDENT = Student(
    id=UUID("44444444-4444-4444-8444-444444444444"),
    name="A. Tutee",
    subjects=["maths"],
    status=StudentStatus.ACTIVE,
)


def test_the_backend_defaults_to_claude_reads_the_environment_and_names_what_it_accepts() -> None:
    assert generate_settings({}).backend is GenerateBackend.CLAUDE
    assert generate_settings({"SIDEREAL_GENERATE_BACKEND": "fake"}).backend is GenerateBackend.FAKE
    assert (
        generate_settings({"SIDEREAL_GENERATE_BACKEND": "openrouter"}).backend
        is GenerateBackend.OPENROUTER
    )
    with pytest.raises(ValueError, match="claude, openrouter, fake"):
        generate_settings({"SIDEREAL_GENERATE_BACKEND": "gpt"})


def test_the_model_health_reports_is_the_one_the_chosen_backend_calls() -> None:
    claude = generate_settings({"SIDEREAL_GENERATE_MODEL": "claude-opus-5"})
    openrouter = generate_settings({"SIDEREAL_GENERATE_BACKEND": "openrouter"})

    assert claude.active_model == "claude-opus-5"
    assert openrouter.active_model == DEFAULT_OPENROUTER_MODEL
    assert generate_settings({"OPENROUTER_API_KEY": "  "}).openrouter.api_key is None
    assert "secret" not in repr(generate_settings({"OPENROUTER_API_KEY": "secret"}).openrouter)


def test_the_reasoning_effort_reads_the_environment_and_names_what_it_accepts() -> None:
    assert generate_settings({}).extract_reasoning is ReasoningEffort.LOW
    assert (
        generate_settings({"SIDEREAL_GENERATE_REASONING": "high"}).extract_reasoning
        is ReasoningEffort.HIGH
    )
    with pytest.raises(ValueError, match="low, medium, high"):
        generate_settings({"SIDEREAL_GENERATE_REASONING": "none"})


def test_an_extraction_is_budgeted_above_every_other_answer() -> None:
    settings = generate_settings({})

    assert settings.max_tokens == DEFAULT_MAX_TOKENS
    assert settings.extract_max_tokens > settings.max_tokens
    assert (
        generate_settings({"SIDEREAL_GENERATE_EXTRACT_MAX_TOKENS": "99"}).extract_max_tokens == 99
    )
    assert DEFAULT_EXTRACT_MAX_TOKENS > DEFAULT_MAX_TOKENS


def test_default_generators_builds_anthropic_generators_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SIDEREAL_GENERATE_BACKEND", raising=False)

    generators = default_generators()

    assert isinstance(generators.homework, AnthropicGenerator)
    assert isinstance(generators.plan, AnthropicGenerator)


def test_default_generators_builds_openrouter_generators_when_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIDEREAL_GENERATE_BACKEND", "openrouter")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    generators = default_generators()

    assert isinstance(generators.homework, OpenRouterGenerator)
    assert isinstance(generators.feedback, OpenRouterGenerator)
    assert isinstance(generators.plan, OpenRouterGenerator)
    assert isinstance(generators.paper, OpenRouterPaperExtractor)
    assert generators.plan.model == DEFAULT_OPENROUTER_MODEL


def test_default_generators_builds_fake_generators_when_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIDEREAL_GENERATE_BACKEND", "fake")

    generators = default_generators()

    assert isinstance(generators.homework, FakeHomeworkGenerator)
    assert generators.feedback.model == FAKE_MODEL
    assert generators.plan.model == FAKE_MODEL


async def test_the_fake_homework_names_the_student_and_admits_what_it_is() -> None:
    output = await FakeHomeworkGenerator().generate(
        GenerationRequest(student=STUDENT, instructions="Six questions.")
    )

    assert output.title == f"{FAKE_PREFIX} Homework for A. Tutee"
    assert "No model was called" in output.content
    assert "Six questions." in output.content
    assert len(output.questions) == 1
    assert output.questions[0].text.startswith(FAKE_PREFIX)


async def test_the_fake_feedback_and_plan_list_the_material_they_were_given() -> None:
    document = Document(
        id=UUID("55555555-5555-4555-8555-555555555555"),
        title="Lesson 3",
        kind=DocumentKind.TRANSCRIPT,
    )
    request = GenerationRequest(student=STUDENT, documents=(document,))

    feedback = await FakeFeedbackGenerator().generate(request)
    plan = await FakePlanGenerator().generate(request)

    assert "- Lesson 3" in feedback.content
    assert plan.title == f"{FAKE_PREFIX} Study plan for A. Tutee"
    assert "- Lesson 3" in plan.content
