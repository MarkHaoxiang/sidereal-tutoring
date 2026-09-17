from __future__ import annotations

import json
from pathlib import Path

import pytest
from sidereal_core.typst_text import plain_text

FIXTURE = Path(__file__).parent / "fixtures" / "typst_text.json"
VECTORS: list[dict[str, str]] = json.loads(FIXTURE.read_text())["vectors"]


@pytest.mark.parametrize("vector", VECTORS, ids=[vector["typst"] for vector in VECTORS])
def test_the_shared_vectors_hold(vector: dict[str, str]) -> None:
    assert plain_text(vector["typst"]) == vector["text"]


def test_a_frac_inside_a_frac_is_transformed_too() -> None:
    assert plain_text("$frac(frac(1, 2), 3)$") == "1/2/3"


def test_a_sqrt_of_more_than_one_atom_keeps_its_brackets() -> None:
    assert plain_text("$sqrt(x + 1)$") == "√(x + 1)"


def test_an_unbalanced_bracket_is_left_as_a_character() -> None:
    assert plain_text("$sqrt(2$") == "sqrt(2"


def test_operator_spellings_and_a_dotted_symbol_name() -> None:
    assert plain_text("$a <= b != c$") == "a ≤ b ≠ c"
    assert plain_text("$plus.minus 3$") == "± 3"


def test_a_script_of_characters_with_no_form_stays_literal() -> None:
    assert plain_text("$sum_(i=1)$") == "Σ_(i=1)"
