from __future__ import annotations

import pytest
from sidereal_core.canonical import (
    CanonicalCodeBlock,
    CanonicalPaper,
    CanonicalPart,
    CanonicalQuestion,
)
from sidereal_generate.typst_maths import normalise, normalise_model


@pytest.mark.parametrize(
    ("wrote", "compiles"),
    [
        # The three the compiler actually refused on the AQA June 2023 paper.
        ("the midpoint of $PQ$", 'the midpoint of $"PQ"$'),
        ("expand $xy$", 'expand $"xy"$'),
        ("$dy/dx$", "$dif y/dif x$"),
        ("$d x$", "$dif x$"),
        ("$cos4x$", '$"cos4x"$'),
        # A subscript word is a name too.
        ("$x_total$", '$x_"total"$'),
        # A unit exponent the model wrote as a span of its own has no base to attach to.
        ("$5.2 times 10^7$ C kg$^-1$", '$5.2 times 10^7$ C kg$""^(-1)$'),
        ("m s$^-1$", 'm s$""^(-1)$'),
        ("km h$^-1$", 'km h$""^(-1)$'),
        ("$_2^4$He", '$""_2^4$He'),
        ("$ ^-1$", '$ ""^(-1)$'),
        # A script takes one atom, so a signed exponent needs the group the model left off.
        ("$4.8 times 10^-2$ m", "$4.8 times 10^(-2)$ m"),
        ("$2.4 times 10^+3$", "$2.4 times 10^(+3)$"),
        ("$10^-2.5$", "$10^(-2.5)$"),
        ("$x^-1$", "$x^(-1)$"),
        ('$"kg m"^-3$', '$"kg m"^(-3)$'),
        ("$x_-1$", "$x_(-1)$"),
        ("$10^-n$", "$10^(-n)$"),
        # The empty base does not stop a name after it being quoted.
        ("$^total$", '$""^"total"$'),
    ],
)
def test_a_name_typst_does_not_know_becomes_text(wrote: str, compiles: str) -> None:
    assert normalise(wrote) == compiles


@pytest.mark.parametrize(
    "maths",
    [
        "$sin x$",
        "$ln x$",
        "$sqrt(2)$",
        "$cos(4 x)$",
        '$"PQ"$',
        "$alpha + beta$",
        "$integral_0^1 f(x)$",
        "$dif x$",
        "$frac(a, b)$",
        "$x^2 - 5x + 6$",
        "$arccos theta$",
        "$lim_(n -> infinity) u_n$",
        "$RR$",
        "$u_(n+1) = p u_n + 70$",
        "$10^7$",
        "$a_1$",
    ],
)
def test_maths_typst_already_accepts_is_left_alone(maths: str) -> None:
    assert normalise(maths) == maths


def test_prose_outside_the_delimiters_is_never_touched() -> None:
    wrote = "The points P and Q lie on the curve. Find $PQ$ where dy^2 means nothing here."

    assert normalise(wrote) == (
        'The points P and Q lie on the curve. Find $"PQ"$ where dy^2 means nothing here.'
    )


def test_every_string_in_a_structure_is_normalised() -> None:
    paper = CanonicalPaper(
        title="Paper about $PQ$",
        questions=(
            CanonicalQuestion(
                number="1",
                stem="Find $dy/dx$.",
                parts=(CanonicalPart(label="a", text="Show $AB$ is $sqrt(2)$."),),
            ),
        ),
    )

    fixed = normalise_model(paper)

    assert fixed.title == 'Paper about $"PQ"$'
    assert fixed.questions[0].stem == "Find $dif y/dif x$."
    assert fixed.questions[0].parts[0].text == 'Show $"AB"$ is $sqrt(2)$.'
    # Nothing but the maths moves.
    assert fixed.questions[0].number == "1"


def test_a_code_block_is_verbatim() -> None:
    listing = "price = base$^-1$ # $PQ$"
    paper = CanonicalPaper(
        title="Gravitational fields",
        questions=(
            CanonicalQuestion(
                number="1",
                stem="Correct the line, given $F$ is in N kg$^-1$.",
                blocks=(CanonicalCodeBlock(language="python", text=listing),),
            ),
        ),
    )

    fixed = normalise_model(paper)
    block = fixed.questions[0].blocks[0]

    assert isinstance(block, CanonicalCodeBlock)
    assert block.text == listing
    assert fixed.questions[0].stem == 'Correct the line, given $F$ is in N kg$""^(-1)$.'
