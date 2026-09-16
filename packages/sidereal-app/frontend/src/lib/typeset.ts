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
