import { ApiError, apiError } from "@/lib/api";

export interface Diagnostic {
  message: string;
  line: number | null;
  column: number | null;
  severity: string;
}

/** A refused Typst source. `diagnostics` is what the compiler said, line and column included. */
export class TypstError extends ApiError {
  readonly diagnostics: Diagnostic[];

  constructor(error: ApiError, diagnostics: Diagnostic[]) {
    super(error.message, error.code, error.status);
    this.name = "TypstError";
    this.diagnostics = diagnostics;
  }
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : undefined;
}

function asDiagnostic(value: unknown): Diagnostic | null {
  const row = asRecord(value);
  const message = row?.["message"];
  if (typeof message !== "string") {
    return null;
  }
  const line = row?.["line"];
  const column = row?.["column"];
  const severity = row?.["severity"];
  return {
    message,
    line: typeof line === "number" ? line : null,
    column: typeof column === "number" ? column : null,
    severity: typeof severity === "string" ? severity : "error",
  };
}

export function readDiagnostics(body: unknown): Diagnostic[] {
  const rows = asRecord(asRecord(body)?.["detail"])?.["diagnostics"];
  if (!Array.isArray(rows)) {
    return [];
  }
  return rows.flatMap((row) => {
    const diagnostic = asDiagnostic(row);
    return diagnostic ? [diagnostic] : [];
  });
}

/** One line for a tutor: what the compiler said, or whatever else refused the render. */
export function typstProblem(error: unknown): string {
  if (error instanceof TypstError && error.diagnostics.length > 0) {
    return error.diagnostics
      .map((diagnostic) => {
        const place = diagnosticPlace(diagnostic);
        return place ? `${place}: ${diagnostic.message}` : diagnostic.message;
      })
      .join("; ");
  }
  return apiError(error);
}

/** "Line 12, column 4" — the place a diagnostic points at, or nothing when it points nowhere. */
export function diagnosticPlace(diagnostic: Diagnostic): string | null {
  if (diagnostic.line === null) {
    return null;
  }
  const line = `Line ${String(diagnostic.line)}`;
  return diagnostic.column === null ? line : `${line}, column ${String(diagnostic.column)}`;
}

function isFigure(node: unknown, named: ReadonlySet<string>): boolean {
  const row = asRecord(node);
  const asset = row?.["asset"];
  return row?.["type"] === "figure" && typeof asset === "string" && named.has(asset);
}

/**
 * The document without the `figure` blocks naming any of `assets`, at whatever depth they
 * sit. A figure whose image cannot be read is left out rather than sent as a name with no
 * bytes, which the renderer refuses for the whole question.
 */
export function withoutFigures<T>(value: T, assets: readonly string[]): T {
  const named = new Set(assets);
  const walk = (node: unknown): unknown => {
    if (Array.isArray(node)) {
      return node.filter((item) => !isFigure(item, named)).map(walk);
    }
    const row = asRecord(node);
    if (row === undefined) {
      return node;
    }
    return Object.fromEntries(Object.entries(row).map(([key, item]) => [key, walk(item)]));
  };
  return walk(value) as T;
}

/** Every `figure` block's asset name in a canonical document, in the order they are met. */
export function figureAssets(value: unknown): string[] {
  const found: string[] = [];
  const walk = (node: unknown): void => {
    if (Array.isArray(node)) {
      node.forEach(walk);
      return;
    }
    const row = asRecord(node);
    if (row === undefined) {
      return;
    }
    if (row["type"] === "figure" && typeof row["asset"] === "string") {
      found.push(row["asset"]);
    }
    Object.values(row).forEach(walk);
  };
  walk(value);
  return [...new Set(found)];
}
