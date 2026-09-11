# directus — invariants

- `schema/snapshot.yaml` is the source of truth for the schema. Change the schema by editing
  it and running `scripts/directus-schema-apply.sh`, or by editing in the admin app and
  immediately running `scripts/directus-schema-snapshot.sh`; an admin-app change that is not
  snapshotted is lost on the next apply.
- Commit the snapshot exactly as `directus schema snapshot` emits it. Hand-edits that Directus
  would normalise differently make the next round-trip a spurious diff.
- Snapshots carry collections, fields and relations only. Roles, policies, permissions and the
  agent service account live in `scripts/directus-bootstrap.sh` and are created by running it.
- Status/kind values are the lowercase tokens from the domain vocabulary
  (`active`/`paused`/`archived`, `scheduled`/`completed`/`cancelled`,
  `transcript`/`web_page`/`question_bank`/`upload`, `pending`/`processing`/`ready`/`failed`,
  `draft`/`assigned`/`submitted`/`marked`, `draft`/`sent`, `draft`/`active`/`completed`,
  `homework`/`feedback`/`plan`, `queued`/`running`/`succeeded`/`failed`). The Python `StrEnum`s
  and the TypeScript unions mirror them exactly; changing one means changing all three.
- Every collection has a `uuid` primary key and the four audit fields
  (`date_created`, `date_updated`, `user_created`, `user_updated`).
- `homework` ↔ `questions` is m2m through `homework_questions`; nothing writes that junction's
  rows by hand except through the m2m alias fields.
- Directus 12's core (unlicensed) entitlements reject any `directus_permissions` row that
  narrows `fields` below `["*"]` or carries a `permissions`, `validation` or `presets` rule,
  unless it matches one of Directus's own recommended app permissions. Per-tutor row scoping
  therefore cannot live in Directus permissions; enforce it in the app layer or buy the
  entitlement. `scripts/directus-bootstrap.sh` grants unfiltered CRUD for that reason.
- New permission rows are served from a system cache that their creation does not invalidate,
  so anything that writes permissions must finish with `POST /utils/cache/clear?system`.
- The runtime image ships no `npm`/`npx`; invoke the CLI as `node /directus/cli.js`.
- The compose stack is local dev only. Every credential in `.env.example` is a placeholder.
- Extensions build to `dist/` and are loaded from the bind mount; `dist/` and `node_modules/`
  are never committed.
