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
- `students.user` is unique and nullable, `SET NULL` on delete: a `directus_users` row links to
  at most one student, and removing the login leaves the student and their work intact.
- Everything the `Student` role can reach hangs off the one `students` row whose `user` is the
  caller. A student never sees `students.notes`, `sessions.notes`, `homework.generated_from`,
  `questions.answer`, `draft` homework, `draft` feedback, `draft` plans, `documents`,
  `generation_jobs`, or any `directus_users` row but their own.
- The Student policy is `app_access: false`: students reach the API and never the admin app.
- A student's only write is `homework` update — fields `submission`, `submitted_at`, `status`,
  on rows still `assigned`, with `status` allowed to become `submitted` and nothing else. The
  row filter is what stops a second hand-in.
- Row filters, narrowed `fields` and `validation` on a `directus_permissions` row are the
  licensed `custom_permission_rules_enabled` entitlement (`GET /license`, `.default`). Core
  Directus rejects such a row unless it matches one of Directus's own recommended app
  permissions, so the Tutor policy grants unfiltered CRUD on the app collections. Unentitled,
  `scripts/directus-bootstrap.sh` still creates the `Student` role and policy, warns, and skips
  every filtered grant: without a license there is no student isolation, so students get
  nothing rather than everything.
- `app_access: true` does not supply a readable `directus_roles` or `directus_users` in
  Directus 12; a tutor's grants on both are explicit.
- A permission row's `fields` list also gates writes: a payload key missing from the list is
  rejected outright, not dropped. `validation` is checked against the payload alone, so a key
  the payload omits passes.
- A client-supplied filter on a field the caller cannot read is refused, so any field callers
  filter on must be in their read list — which is why `students.user` is in the student's.
- `LICENSE_KEY` reaches Directus from the invoking shell only (`~/.config/sidereal-tutoring/env`,
  mode 600). It is never in `.env`, `.env.example` or CI, and CI runs unlicensed.
- An activation binds the key to the project id (minted on first bootstrap) and `PUBLIC_URL`,
  and there are five. With the key loaded, stop with `docker compose down`, never `down -v`:
  a wiped database mints a new project id and burns a slot, and an exhausted key fails to boot
  with `403 Activation Limit Exceeded`. Wipe licensed only after `DELETE /license`; otherwise
  run the wipe-and-reapply cycle with `LICENSE_KEY` unset.
- New permission rows are served from a system cache that their creation does not invalidate,
  so anything that writes permissions must finish with `POST /utils/cache/clear?system`.
- The runtime image ships no `npm`/`npx`; invoke the CLI as `node /directus/cli.js`.
- The compose stack is local dev only. Every credential in `.env.example` is a placeholder.
- Extensions build to `dist/` and are loaded from the bind mount; `dist/` and `node_modules/`
  are never committed. Build before bringing the stack up: an unbuilt extension makes the
  loader throw a module-not-found on every CLI invocation.
- The schema directory is mounted read-only, so nothing in the container may write to it; the
  snapshot script has the CLI write inside the container and streams the file out.
