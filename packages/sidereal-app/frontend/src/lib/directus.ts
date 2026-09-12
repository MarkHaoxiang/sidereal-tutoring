import { authentication, createDirectus, rest } from "@directus/sdk";

import { authStorage } from "@/lib/auth-storage";
import type { Schema } from "@/lib/schema";

export const directusUrl = import.meta.env["VITE_DIRECTUS_URL"]?.trim() || "http://localhost:8055";

export const directus = createDirectus<Schema>(directusUrl)
  .with(rest())
  .with(authentication("json", { storage: authStorage }));
