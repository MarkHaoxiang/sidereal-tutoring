# sidereal-app frontend

## Install

```sh
npm install
cp .env.example .env
```

## Run

```sh
npm run dev
```

Proxies `/api` to `http://localhost:8000` (the FastAPI app); talks to Directus directly at `VITE_DIRECTUS_URL`.

## Build

```sh
npm run build
```

## Generate the API client

Regenerates `src/lib/api-schema.d.ts` from the FastAPI OpenAPI schema (requires the `sidereal-app` Python package):

```sh
npm run gen-api
```

## Check the Typst text helper

Asserts `src/lib/typstText.ts` against `packages/sidereal-core/tests/fixtures/typst_text.json`, the
vectors `sidereal_core.typst_text` answers:

```sh
npm run check:typst
```
