import createClient from "openapi-fetch";

import type { paths } from "@/lib/api-schema";

export const api = createClient<paths>({ baseUrl: "/api" });
