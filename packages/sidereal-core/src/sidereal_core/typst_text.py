"""Typst flattened to one line of readable text.

`tests/fixtures/typst_text.json` is the contract with the frontend's `lib/typstText.ts`: both
implementations answer the same vectors.
"""

# The tables below are the characters RUF001 calls confusable; naming them is the point.
# ruff: noqa: RUF001

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

_SYMBOLS: dict[str, str] = {
    "times": "×",
    "dot": "·",
    "div": "÷",
    "plus.minus": "±",
    "pi": "π",
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "Delta": "Δ",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "rho": "ρ",
    "sigma": "σ",
    "Sigma": "Σ",
    "phi": "φ",
    "omega": "ω",
    "Omega": "Ω",
    "degree": "°",
    "infinity": "∞",
    "integral": "∫",
    "sum": "Σ",
    "approx": "≈",
    "prop": "∝",
    "arrow": "→",
}

_OPERATORS: dict[str, str] = {
    "<=": "≤",
    ">=": "≥",
    "!=": "≠",
    "->": "→",
}

# The symbols that count as letters when deciding whether a space between two atoms survives.
_LETTER_SYMBOLS = frozenset("παβγδΔθλμρσΣφωΩ")

# A symbol that is set tight against whatever precedes it: `$30 degree$` is an angle, "30°".
_TIGHT = frozenset("°")

_SUPERSCRIPTS: dict[str, str] = dict(
    zip(
        "0123456789+-=()ni",
        "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ",
        strict=True,
    )
)

_SUBSCRIPTS: dict[str, str] = dict(
    zip(
        "0123456789+-=()aeoxhklmnpst",
        "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜ",
        strict=True,
    )
)

_SCRIPT_CHARS = frozenset(_SUPERSCRIPTS.values()) | frozenset(_SUBSCRIPTS.values())

_NAME = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z][A-Za-z0-9]*)*")
_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")

_Kind = Literal["quoted", "name", "number", "group", "space", "other"]


@dataclass(frozen=True)
class _Token:
    kind: _Kind
    text: str


@dataclass(frozen=True)
class _Atom:
    text: str
    space: bool = False
    quoted: bool = False


def plain_text(source: str) -> str:
    """Only the inside of a `$...$` span is rewritten; an unclosed `$` stays as it is."""
    out: list[str] = []
    index = 0
    while index < len(source):
        char = source[index]
        if char == "$":
            close = source.find("$", index + 1)
            if close != -1:
                out.append(_inline(source[index + 1 : close]))
                index = close + 1
                continue
        out.append(char)
        index += 1
    return "".join(out)


def _inline(body: str) -> str:
    return _render(_atoms(body))


def _closing_paren(body: str, start: int) -> int:
    depth = 0
    index = start
    while index < len(body):
        char = body[index]
        if char == '"':
            close = body.find('"', index + 1)
            index = len(body) if close == -1 else close + 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def _tokens(body: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char.isspace():
            start = index
            while index < len(body) and body[index].isspace():
                index += 1
            tokens.append(_Token("space", body[start:index]))
        elif char == '"':
            close = body.find('"', index + 1)
            if close == -1:
                tokens.append(_Token("other", char))
                index += 1
            else:
                tokens.append(_Token("quoted", body[index + 1 : close]))
                index = close + 1
        elif (name := _NAME.match(body, index)) is not None:
            text = name.group()
            if "." in text and text not in _SYMBOLS:
                text = text.split(".", 1)[0]
            tokens.append(_Token("name", text))
            index += len(text)
        elif (number := _NUMBER.match(body, index)) is not None:
            tokens.append(_Token("number", number.group()))
            index += len(number.group())
        elif char == "(" and (close := _closing_paren(body, index)) != -1:
            tokens.append(_Token("group", body[index + 1 : close]))
            index = close + 1
        elif body[index : index + 2] in _OPERATORS:
            tokens.append(_Token("other", body[index : index + 2]))
            index += 2
        else:
            tokens.append(_Token("other", char))
            index += 1
    return tokens


def _arguments(body: str) -> list[str]:
    if not body.strip():
        return []
    arguments: list[str] = []
    depth = 0
    start = 0
    index = 0
    while index < len(body):
        char = body[index]
        if char == '"':
            close = body.find('"', index + 1)
            index = len(body) if close == -1 else close + 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            arguments.append(body[start:index].strip())
            start = index + 1
        index += 1
    arguments.append(body[start:].strip())
    return arguments


def _script(token: _Token) -> str:
    if token.kind == "group":
        return _inline(token.text)
    if token.kind == "name":
        return _SYMBOLS.get(token.text, token.text)
    return token.text


def _atom(token: _Token) -> _Atom:
    if token.kind == "quoted":
        return _Atom(token.text, quoted=True)
    if token.kind == "name":
        return _Atom(_SYMBOLS.get(token.text, token.text))
    if token.kind == "group":
        return _Atom(f"({_inline(token.text)})")
    if token.kind == "other":
        return _Atom(_OPERATORS.get(token.text, token.text))
    return _Atom(token.text)


def _atoms(body: str) -> list[_Atom]:
    tokens = _tokens(body)
    atoms: list[_Atom] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        after = tokens[index + 1] if index + 1 < len(tokens) else None
        arguments = _arguments(after.text) if after is not None and after.kind == "group" else []
        if token.kind == "space":
            atoms.append(_Atom(token.text, space=True))
            index += 1
        elif token.kind == "name" and token.text == "frac" and len(arguments) == 2:
            atoms.append(_Atom(f"{_inline(arguments[0])}/{_inline(arguments[1])}"))
            index += 2
        elif token.kind == "name" and token.text == "sqrt" and len(arguments) == 1:
            inner = _atoms(arguments[0])
            body_text = _render(inner)
            whole = body_text if len(inner) == 1 else f"({body_text})"
            atoms.append(_Atom(f"√{whole}"))
            index += 2
        elif token.kind == "name" and token.text == "dif":
            atoms.append(_Atom("d"))
            index += 2 if after is not None and after.kind == "space" else 1
        elif token.kind == "other" and token.text in ("^", "_") and after is not None:
            table = _SUPERSCRIPTS if token.text == "^" else _SUBSCRIPTS
            raised = _script(after) if after.kind != "space" else ""
            if raised and all(char in table for char in raised):
                atoms.append(_Atom("".join(table[char] for char in raised)))
                index += 2
            else:
                atoms.append(_Atom(token.text))
                index += 1
        else:
            atoms.append(_atom(token))
            index += 1
    return atoms


def _letterish(atom: _Atom) -> bool:
    single = len(atom.text) == 1
    return atom.quoted or (
        single and ((atom.text.isascii() and atom.text.isalpha()) or atom.text in _LETTER_SYMBOLS)
    )


def _ends_letter(atom: _Atom) -> bool:
    return _letterish(atom) or (atom.text != "" and atom.text[-1] in _SCRIPT_CHARS)


def _starts_letter(atom: _Atom) -> bool:
    return _letterish(atom) or (atom.text != "" and atom.text[0] in _SCRIPT_CHARS)


def _render(atoms: list[_Atom]) -> str:
    out: list[str] = []
    for index, atom in enumerate(atoms):
        if not atom.space:
            out.append(atom.text)
            continue
        before = atoms[index - 1] if index > 0 else None
        after = atoms[index + 1] if index + 1 < len(atoms) else None
        joined = after is not None and (
            (after.text in _TIGHT and not after.quoted)
            or (before is not None and _ends_letter(before) and _starts_letter(after))
        )
        if not joined:
            out.append(" ")
    return "".join(out)
