import type { AuthenticationData, AuthenticationStorage } from "@directus/sdk";

const STORAGE_KEY = "sidereal-auth";

function parse(raw: string | null): AuthenticationData | null {
  if (!raw) {
    return null;
  }
  try {
    const value: unknown = JSON.parse(raw);
    if (typeof value !== "object" || value === null) {
      return null;
    }
    const data = value as Record<string, unknown>;
    if (typeof data["access_token"] !== "string") {
      return null;
    }
    return {
      access_token: data["access_token"],
      refresh_token: typeof data["refresh_token"] === "string" ? data["refresh_token"] : null,
      expires: typeof data["expires"] === "number" ? data["expires"] : null,
      expires_at: typeof data["expires_at"] === "number" ? data["expires_at"] : null,
    };
  } catch {
    return null;
  }
}

// The SDK's session lives here so a reload keeps the tutor signed in. localStorage is
// best-effort: a blocked or full store leaves the in-memory copy, which behaves
// exactly as the SDK's own memory storage did.
function createAuthStorage(): AuthenticationStorage {
  let memory: AuthenticationData | null = null;
  try {
    memory = parse(localStorage.getItem(STORAGE_KEY));
  } catch {
    memory = null;
  }

  return {
    get: () => memory,
    set: (value: AuthenticationData | null) => {
      memory = value;
      try {
        if (value?.access_token) {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
        } else {
          localStorage.removeItem(STORAGE_KEY);
        }
      } catch {
        // In-memory only for this tab.
      }
    },
  };
}

export const authStorage = createAuthStorage();
