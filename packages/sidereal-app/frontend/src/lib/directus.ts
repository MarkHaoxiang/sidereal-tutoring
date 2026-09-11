import { authentication, createDirectus, rest } from "@directus/sdk";

import { authStorage } from "@/lib/auth-storage";
import type { Schema } from "@/lib/schema";

const url = import.meta.env["VITE_DIRECTUS_URL"]?.trim() || "http://localhost:8055";

export const directus = createDirectus<Schema>(url)
  .with(rest())
  .with(authentication("json", { storage: authStorage }));
