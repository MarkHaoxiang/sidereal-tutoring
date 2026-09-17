"""Maths a model wrote, corrected to what the Typst compiler accepts.

Typst stops evaluating at the first unknown variable, so a paper with four such faults
costs four compile-and-repair rounds. These are the faults a model makes over and over,
and every one of them has a single right answer, so they are fixed here rather than paid
for at the gateway.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

# Everything Typst already knows inside `$...$`. A name outside this set is the model's own
# — a point pair, a label, a subscript word — and Typst reads it as an undefined variable.
# An intermediate name keeps these as the lists they are: a `frozenset(...split())` call
# gets rewritten into one name per line, and 200 of those read as noise, not as data.
_FUNCTIONS = """
sin cos tan sec csc cot sinh cosh tanh coth sech csch
arcsin arccos arctan arcsec arccsc arccot asin acos atan
ln log lg exp lim liminf limsup max min sup inf
det dim ker gcd lcm mod deg arg hom sgn tr rank
sqrt root abs norm frac binom vec mat cases
dif diff partial nabla grad div curl laplace
sum prod integral union sect
floor ceil round lr mid class limits scripts stretch cancel
hat bar tilde dot ddot dddot acute grave breve caron circle
overline underline overbrace underbrace attach
upright italic bold serif sans cal frak mono bb display inline script sscript
text op accent
"""
_SYMBOLS = """
alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu
nu xi omicron pi varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega
Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Iota Kappa Lambda Mu Nu Xi Omicron Pi Rho
Sigma Tau Upsilon Phi Chi Psi Omega
infinity infty oo emptyset nothing forall exists nexists
times div plus minus dots cdot ldots cdots vdots ddots
arrow arrows mapsto to gets implies iff
leq geq neq approx equiv prop propto sim similar cong
in notin subset supset subseteq supseteq
and or not xor
degree angle perp parallel prec succ
RR NN ZZ QQ CC
"""
FUNCTIONS = frozenset(_FUNCTIONS.split())
SYMBOLS = frozenset(_SYMBOLS.split())
KNOWN = FUNCTIONS | SYMBOLS
# The blocks the renderer sets verbatim: a `$` in a listing delimits nothing.
VERBATIM = frozenset({"passage", "code"})

# `$...$`, the only place any of this applies. An escaped dollar opens nothing.
_MATH = re.compile(r"(?<!\\)\$(.*?)(?<!\\)\$", re.DOTALL)
# A quoted run is already text: Typst asks no questions of it, and neither do we.
_QUOTED = re.compile(r'"[^"]*"')
# A span opening on `^` or `_` — `kg$^-1$` — has no base to attach the script to.
_LEADING_SCRIPT = re.compile(r"^(\s*)([_^])")
# A script takes one atom, so `10^-2` raises the sign alone and leaves the 2 on the line.
_SIGNED_SCRIPT = re.compile(r"([_^])\s*([+-])\s*([0-9]+(?:\.[0-9]+)?|[A-Za-z][A-Za-z0-9]*)")
# `dx`, `d x` — a differential, not the product of `d` and `x`.
_DIFFERENTIAL = re.compile(r"\bd[ ]?([xyztθ])\b")
# An identifier Typst would look up: letters then letters or digits, unquoted, not a field
# access and not a call. `_` may precede it — `x_total` is a subscript, and a fault.
_IDENTIFIER = re.compile(r'(?<![\\".A-Za-z0-9])([A-Za-z][A-Za-z0-9]*)(?![A-Za-z0-9.(])')


def normalise(text: str) -> str:
    """One field's maths, left alone outside `$...$`."""
    return _MATH.sub(lambda match: f"${_span(match.group(1))}$", text)


def normalise_model[M: BaseModel](model: M) -> M:
    """Every string in a structure, normalised. Nothing else about it changes."""
    return type(model).model_validate(_walk(model.model_dump(mode="json")))


def _span(maths: str) -> str:
    """The empty base goes in first: it is a quoted run the names pass then skips."""
    maths = _LEADING_SCRIPT.sub(r'\1""\2', maths)
    out: list[str] = []
    cursor = 0
    for quoted in _QUOTED.finditer(maths):
        out.append(_names(maths[cursor : quoted.start()]))
        out.append(quoted.group(0))
        cursor = quoted.end()
    out.append(_names(maths[cursor:]))
    return "".join(out)


def _names(maths: str) -> str:
    """Differentials first: `dx` is one name, and quoting it would keep it one."""
    grouped = _SIGNED_SCRIPT.sub(r"\1(\2\3)", maths)
    return _IDENTIFIER.sub(_quoted, _DIFFERENTIAL.sub(r"dif \1", grouped))


def _quoted(match: re.Match[str]) -> str:
    name = match.group(1)
    if len(name) < 2 or name in KNOWN:
        return name
    return f'"{name}"'


def _walk(value: Any) -> Any:
    match value:
        case str():
            return normalise(value)
        case dict() if value.get("type") in VERBATIM:
            return {key: item if key == "text" else _walk(item) for key, item in value.items()}
        case dict():
            return {key: _walk(item) for key, item in value.items()}
        case list():
            return [_walk(item) for item in value]
        case _:
            return value
