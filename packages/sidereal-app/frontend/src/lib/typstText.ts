// Typst flattened to one line of readable text, for every list and preview that shows a stem or
// a question. `sidereal_core.typst_text` is the same function in Python, and
// packages/sidereal-core/tests/fixtures/typst_text.json is the contract both answer.

const SYMBOLS: Record<string, string> = {
  times: "×",
  dot: "·",
  div: "÷",
  "plus.minus": "±",
  pi: "π",
  alpha: "α",
  beta: "β",
  gamma: "γ",
  delta: "δ",
  Delta: "Δ",
  theta: "θ",
  lambda: "λ",
  mu: "μ",
  rho: "ρ",
  sigma: "σ",
  Sigma: "Σ",
  phi: "φ",
  omega: "ω",
  Omega: "Ω",
  degree: "°",
  infinity: "∞",
  integral: "∫",
  sum: "Σ",
  approx: "≈",
  prop: "∝",
  arrow: "→",
};

const OPERATORS: Record<string, string> = {
  "<=": "≤",
  ">=": "≥",
  "!=": "≠",
  "->": "→",
};

// The symbols that count as letters when deciding whether a space between two atoms survives.
const LETTER_SYMBOLS = new Set("παβγδΔθλμρσΣφωΩ");

// A symbol that is set tight against whatever precedes it: `$30 degree$` is an angle, "30°".
const TIGHT = new Set("°");

function table(from: string, to: string): Record<string, string> {
  const map: Record<string, string> = {};
  [...from].forEach((character, index) => {
    map[character] = [...to][index] ?? character;
  });
  return map;
}

const SUPERSCRIPTS = table("0123456789+-=()ni", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ");
const SUBSCRIPTS = table("0123456789+-=()aeoxhklmnpst", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₕₖₗₘₙₚₛₜ");
const SCRIPT_CHARS = new Set([...Object.values(SUPERSCRIPTS), ...Object.values(SUBSCRIPTS)]);

const NAME = /^[A-Za-z][A-Za-z0-9]*(?:\.[A-Za-z][A-Za-z0-9]*)*/;
const NUMBER = /^[0-9]+(?:\.[0-9]+)?/;

type Kind = "quoted" | "name" | "number" | "group" | "space" | "other";

interface Token {
  kind: Kind;
  text: string;
}

interface Atom {
  text: string;
  space?: boolean;
  quoted?: boolean;
}

function closingParen(body: string, start: number): number {
  let depth = 0;
  let index = start;
  while (index < body.length) {
    const character = body[index];
    if (character === '"') {
      const close = body.indexOf('"', index + 1);
      index = close === -1 ? body.length : close + 1;
      continue;
    }
    if (character === "(") {
      depth += 1;
    } else if (character === ")") {
      depth -= 1;
      if (depth === 0) {
        return index;
      }
    }
    index += 1;
  }
  return -1;
}

function tokens(body: string): Token[] {
  const out: Token[] = [];
  let index = 0;
  while (index < body.length) {
    const character = body[index] ?? "";
    if (/\s/.test(character)) {
      const start = index;
      while (index < body.length && /\s/.test(body[index] ?? "")) {
        index += 1;
      }
      out.push({ kind: "space", text: body.slice(start, index) });
      continue;
    }
    if (character === '"') {
      const close = body.indexOf('"', index + 1);
      if (close === -1) {
        out.push({ kind: "other", text: character });
        index += 1;
      } else {
        out.push({ kind: "quoted", text: body.slice(index + 1, close) });
        index = close + 1;
      }
      continue;
    }
    const name = NAME.exec(body.slice(index))?.[0];
    if (name !== undefined) {
      const text = name.includes(".") && !(name in SYMBOLS) ? (name.split(".")[0] ?? name) : name;
      out.push({ kind: "name", text });
      index += text.length;
      continue;
    }
    const number = NUMBER.exec(body.slice(index))?.[0];
    if (number !== undefined) {
      out.push({ kind: "number", text: number });
      index += number.length;
      continue;
    }
    const close = character === "(" ? closingParen(body, index) : -1;
    if (close !== -1) {
      out.push({ kind: "group", text: body.slice(index + 1, close) });
      index = close + 1;
      continue;
    }
    const pair = body.slice(index, index + 2);
    if (pair in OPERATORS) {
      out.push({ kind: "other", text: pair });
      index += 2;
      continue;
    }
    out.push({ kind: "other", text: character });
    index += 1;
  }
  return out;
}

function functionArguments(body: string): string[] {
  if (body.trim() === "") {
    return [];
  }
  const parts: string[] = [];
  let depth = 0;
  let start = 0;
  let index = 0;
  while (index < body.length) {
    const character = body[index];
    if (character === '"') {
      const close = body.indexOf('"', index + 1);
      index = close === -1 ? body.length : close + 1;
      continue;
    }
    if (character === "(") {
      depth += 1;
    } else if (character === ")") {
      depth -= 1;
    } else if (character === "," && depth === 0) {
      parts.push(body.slice(start, index).trim());
      start = index + 1;
    }
    index += 1;
  }
  parts.push(body.slice(start).trim());
  return parts;
}

function scriptText(token: Token): string {
  if (token.kind === "group") {
    return inline(token.text);
  }
  if (token.kind === "name") {
    return SYMBOLS[token.text] ?? token.text;
  }
  return token.text;
}

function atomOf(token: Token): Atom {
  if (token.kind === "quoted") {
    return { text: token.text, quoted: true };
  }
  if (token.kind === "name") {
    return { text: SYMBOLS[token.text] ?? token.text };
  }
  if (token.kind === "group") {
    return { text: `(${inline(token.text)})` };
  }
  if (token.kind === "other") {
    return { text: OPERATORS[token.text] ?? token.text };
  }
  return { text: token.text };
}

function atoms(body: string): Atom[] {
  const rows = tokens(body);
  const out: Atom[] = [];
  let index = 0;
  while (index < rows.length) {
    const token = rows[index];
    if (token === undefined) {
      break;
    }
    const after = rows[index + 1];
    const parts = after?.kind === "group" ? functionArguments(after.text) : [];

    if (token.kind === "space") {
      out.push({ text: token.text, space: true });
      index += 1;
    } else if (token.kind === "name" && token.text === "frac" && parts.length === 2) {
      out.push({ text: `${inline(parts[0] ?? "")}/${inline(parts[1] ?? "")}` });
      index += 2;
    } else if (token.kind === "name" && token.text === "sqrt" && parts.length === 1) {
      const inner = atoms(parts[0] ?? "");
      const body_ = render(inner);
      out.push({ text: `√${inner.length === 1 ? body_ : `(${body_})`}` });
      index += 2;
    } else if (token.kind === "name" && token.text === "dif") {
      out.push({ text: "d" });
      index += after?.kind === "space" ? 2 : 1;
    } else if (token.kind === "other" && (token.text === "^" || token.text === "_") && after !== undefined) {
      const raised = after.kind === "space" ? "" : scriptText(after);
      const map = token.text === "^" ? SUPERSCRIPTS : SUBSCRIPTS;
      if (raised !== "" && [...raised].every((character) => character in map)) {
        out.push({ text: [...raised].map((character) => map[character] ?? character).join("") });
        index += 2;
      } else {
        out.push({ text: token.text });
        index += 1;
      }
    } else {
      out.push(atomOf(token));
      index += 1;
    }
  }
  return out;
}

function letterish(atom: Atom): boolean {
  const single = [...atom.text].length === 1;
  return Boolean(atom.quoted) || (single && (/^[A-Za-z]$/.test(atom.text) || LETTER_SYMBOLS.has(atom.text)));
}

function endsLetter(atom: Atom): boolean {
  const last = [...atom.text].pop();
  return letterish(atom) || (last !== undefined && SCRIPT_CHARS.has(last));
}

function startsLetter(atom: Atom): boolean {
  const first = [...atom.text][0];
  return letterish(atom) || (first !== undefined && SCRIPT_CHARS.has(first));
}

function render(rows: Atom[]): string {
  let out = "";
  rows.forEach((atom, index) => {
    if (!atom.space) {
      out += atom.text;
      return;
    }
    const before = index > 0 ? rows[index - 1] : undefined;
    const after = rows[index + 1];
    const joined =
      after !== undefined &&
      ((TIGHT.has(after.text) && !after.quoted) ||
        (before !== undefined && endsLetter(before) && startsLetter(after)));
    if (!joined) {
      out += " ";
    }
  });
  return out;
}

function inline(body: string): string {
  return render(atoms(body));
}

/**
 * Only the inside of a `$…$` span is rewritten; an unclosed `$` stays as it is.
 * `$A B$` is `AB`, `$""^4_2 "He"$` is `⁴₂He`, `frac(a, b)` is `a/b`.
 */
export function plainText(source: string | null | undefined): string {
  if (!source) {
    return "";
  }
  let out = "";
  let index = 0;
  while (index < source.length) {
    if (source[index] === "$") {
      const close = source.indexOf("$", index + 1);
      if (close !== -1) {
        out += inline(source.slice(index + 1, close));
        index = close + 1;
        continue;
      }
    }
    out += source[index] ?? "";
    index += 1;
  }
  return out;
}

/** The same, as a single line short enough for a row: whitespace collapsed, then clipped. */
export function plainTextPreview(source: string | null | undefined, limit = 120): string {
  const line = plainText(source).replace(/\s+/g, " ").trim();
  return line.length > limit ? `${line.slice(0, limit).trimEnd()}…` : line;
}
