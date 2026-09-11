# directus

Backend and system of record: Postgres + Directus, local dev only.

## Run

From the repo root:

```sh
cp .env.example .env
docker compose up -d
```

Admin app: http://localhost:8055 — sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

## Schema

```sh
./scripts/directus-schema-apply.sh                 # schema/snapshot.yaml -> running instance
./scripts/directus-schema-snapshot.sh              # running instance -> schema/snapshot.yaml
./scripts/directus-schema-snapshot.sh /tmp/x.yaml  # ... or anywhere else
```

## Tutor role and agent token

```sh
./scripts/directus-bootstrap.sh                 # creates the role, policy, permissions, agent user
./scripts/directus-bootstrap.sh --rotate-token  # issue a fresh static token
```

It prints a `SIDEREAL_DIRECTUS_TOKEN=` line; copy the value into `.env`. Directus conceals an
existing static token, so a plain re-run cannot reprint it — rotate instead.

## Extensions

From `directus/extensions`:

```sh
npm install
npm run build      # each extension -> dist/
npm run dev        # rebuild on change; the container reloads via EXTENSIONS_AUTO_RELOAD
npm run typecheck
```
