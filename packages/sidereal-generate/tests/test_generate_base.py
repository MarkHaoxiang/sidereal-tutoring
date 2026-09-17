from __future__ import annotations

import json
import logging
from typing import Any

import pytest
from sidereal_generate.base import unstringify
from sidereal_generate.models import PaperExtraction

PAPER: dict[str, Any] = {
    "title": "Physics A: Modelling Physics",
    "questions": [
        {"number": "1", "stem": "Find the pressure when $p = F / A$.", "answer_lines": 4}
    ],
}


def stringified(paper: dict[str, Any]) -> str:
    """What the live failure sent: the paper as newline-formatted JSON text, not an object."""
    return f"{json.dumps(paper, indent=2)}\n"


def with_a_stray_escape() -> str:
    r"""The same, with a `\p` a model wrote into a maths field. `json.loads` refuses it."""
    return stringified(PAPER).replace("F / A", "F / A, so $p\\phi$")


def test_a_stringified_object_is_parsed_back_and_named() -> None:
    payload = {"paper": stringified(PAPER), "figures": []}

    fixed = unstringify(payload, PaperExtraction)

    assert PaperExtraction.model_validate(fixed).paper.title == "Physics A: Modelling Physics"


def test_a_stray_invalid_escape_is_reported_repaired_and_parsed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The second live failure: this used to return the string with nothing logged at all."""
    text = with_a_stray_escape()
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)

    with caplog.at_level(logging.WARNING):
        fixed = unstringify({"paper": text, "figures": []}, PaperExtraction)

    extraction = PaperExtraction.model_validate(fixed)
    assert "so $p\\phi$" in (extraction.paper.questions[0].stem or "")
    assert "PaperExtraction.paper reads as JSON but would not parse" in caplog.text
    assert "Invalid \\escape" in caplog.text
    assert "parsed once its invalid escapes were doubled" in caplog.text


def test_a_string_that_will_not_parse_at_all_says_so_and_is_left_to_be_refused(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        fixed = unstringify({"paper": '{"title": "Half a pa', "figures": []}, PaperExtraction)

    assert fixed == {"paper": '{"title": "Half a pa', "figures": []}
    assert "would not parse" in caplog.text
    with pytest.raises(ValueError, match="paper"):
        PaperExtraction.model_validate(fixed)


def test_a_string_that_is_not_json_is_untouched_and_unremarked(
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = {"paper": "the paper you asked for", "figures": []}

    with caplog.at_level(logging.WARNING):
        assert unstringify(payload, PaperExtraction) == payload

    assert caplog.text == ""


def test_a_scalar_that_parses_as_json_is_still_left_alone() -> None:
    assert unstringify({"paper": "123", "figures": []}, PaperExtraction) == {
        "paper": "123",
        "figures": [],
    }


def test_a_field_that_legitimately_holds_a_string_is_never_parsed() -> None:
    """A stem that reads as JSON is the paper's own text: only object fields are considered."""
    paper = {**PAPER, "questions": [{"number": "1", "stem": '{"a": 1}'}]}

    fixed = unstringify({"paper": paper, "figures": []}, PaperExtraction)

    assert PaperExtraction.model_validate(fixed).paper.questions[0].stem == '{"a": 1}'


def test_a_backslash_json_already_knows_is_not_doubled() -> None:
    """A repair that broke `\\\\` would turn a valid escape into a literal pair."""
    paper = {**PAPER, "instructions": "A backslash: \\ and a newline follow.\n"}
    text = stringified(paper).replace("A backslash", "A $\\pm$ backslash")

    fixed = unstringify({"paper": text, "figures": []}, PaperExtraction)

    assert PaperExtraction.model_validate(fixed).paper.instructions == (
        "A $\\pm$ backslash: \\ and a newline follow.\n"
    )
