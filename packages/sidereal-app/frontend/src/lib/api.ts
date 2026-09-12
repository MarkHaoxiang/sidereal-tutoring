import createClient from "openapi-fetch";

import type { components, paths } from "@/lib/api-schema";
import { directus } from "@/lib/directus";

// No baseUrl: the generated paths already carry the `/api` prefix, and a relative
// path is what Vite's dev proxy and the deployed origin both serve.
export const api = createClient<paths>();

// The FastAPI app validates the caller's Directus access token; the refresh token
// never leaves the SDK.
api.use({
  async onRequest({ request }) {
    const token = await directus.getToken();
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    return request;
  },
});

export class ApiError extends Error {
  readonly code: string | undefined;
  readonly status: number;

  constructor(message: string, code: string | undefined, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function readString(source: Record<string, unknown>, key: string): string | undefined {
  const value = source[key];
  return typeof value === "string" && value.trim() ? value : undefined;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : undefined;
}

/** The sentence to show a tutor for a failed call, whoever rejected it. */
export function apiError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  const body = asRecord(error);
  if (body) {
    // The FastAPI app answers {detail: {code, message}}; its handlers that write the
    // body themselves answer {code, message}.
    const detail = asRecord(body["detail"]);
    const fromDetail = detail && readString(detail, "message");
    if (fromDetail) {
      return fromDetail;
    }
    // The Directus SDK rejects with an Error carrying the collection's own errors.
    const errors = body["errors"];
    if (Array.isArray(errors)) {
      const first = asRecord(errors[0]);
      const firstMessage = first && readString(first, "message");
      if (firstMessage) {
        return firstMessage;
      }
    }
    // A thrown Error's own `message` is developer text ("Failed to fetch"), never a
    // sentence for a tutor; only a body's `message` field is.
    if (!(error instanceof Error)) {
      const fromBody = readString(body, "message");
      if (fromBody) {
        return fromBody;
      }
    }
  }
  return "Something went wrong. Please try again.";
}

function errorCode(error: unknown): string | undefined {
  const body = asRecord(error);
  if (!body) {
    return undefined;
  }
  const detail = asRecord(body["detail"]);
  return (detail && readString(detail, "code")) ?? readString(body, "code");
}

/** Turns an openapi-fetch result into the payload, or throws a reportable ApiError. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data === undefined) {
    throw new ApiError(apiError(result.error), errorCode(result.error), result.response.status);
  }
  return result.data;
}

/** A 204 carries no body, which `unwrap` would read as a failure; the status decides. */
export function expectNoContent(result: { error?: unknown; response: Response }): void {
  if (!result.response.ok) {
    throw new ApiError(apiError(result.error), errorCode(result.error), result.response.status);
  }
}

/** Who the signed-in user is to this app, and which of the two views they get. */
export type Me = components["schemas"]["Identity"];
export type CallerRole = components["schemas"]["CallerRole"];

export async function getMe(): Promise<Me> {
  return unwrap(await api.GET("/api/me"));
}

/** The request and response shapes of POST /api/documents, straight from the contract. */
export type DocumentSource = components["schemas"]["DocumentSourceRequest"];
export type CreateDocumentBody = components["schemas"]["DocumentRequest"];
export type ApiDocument = components["schemas"]["Document"];

export async function createDocument(body: CreateDocumentBody): Promise<ApiDocument> {
  return unwrap(await api.POST("/api/documents", { body }));
}

export async function processDocument(id: string): Promise<ApiDocument> {
  return unwrap(
    await api.POST("/api/documents/{document_id}/process", {
      params: { path: { document_id: id } },
    })
  );
}
