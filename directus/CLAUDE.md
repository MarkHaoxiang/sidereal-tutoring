# directus — invariants

- `schema/snapshot.yaml` is the source of truth for the schema. Change the schema by editing
  it and running `scripts/directus-schema-apply.sh`, or by editing in the admin app and
  immediately running `scripts/directus-schema-snapshot.sh`; an admin-app change that is not
  snapshotted is lost on the next apply.
- Commit the snapshot exactly as `directus schema snapshot` emits it. Hand-edits that Directus
  would normalise differently make the next round-trip a spurious diff.
- Snapshots carry collections, fields and relations only. Roles, policies, permissions and the
  agent service account live in `scripts/directus-bootstrap.sh` and are created by running it.
- A relation is only ever created or changed with its `meta` and `schema` together, and a
  `PATCH /relations/<collection>/<field>` must carry the whole relation — `collection`, `field`,
  `related_collection` and the full `schema`. A partial patch, `schema` alone included, answers
  `204` and drops the foreign key; the snapshot then loses that relation's `schema` block, which
  a fresh instance silently recreates as `on_delete: NO ACTION`. Delete and recreate an app
  relation with both halves to repair one; a system relation, which cannot be deleted, is
  repaired by the whole-body patch.
- A schema snapshot carries no system relation, so the `on_delete` of one is set by
  `scripts/directus-bootstrap.sh` and nowhere else. `directus_files.uploaded_by` and
  `.modified_by` ship as `NO ACTION`: deleting any user who has uploaded or edited a file fails
  on the foreign key until the bootstrap sets both to `SET NULL`.
- Status/kind values are the lowercase tokens from the domain vocabulary
  (`active`/`paused`/`archived`, `scheduled`/`completed`/`cancelled`,
  `transcript`/`web_page`/`question_bank`/`upload`/`scan`,
  `pending`/`processing`/`ready`/`failed`,
  `draft`/`assigned`/`submitted`/`marked`, `draft`/`sent`, `draft`/`active`/`completed`,
  `draft`/`reviewed`/`archived`, `homework`/`feedback`/`plan`/`paper_extract`,
  `queued`/`running`/`succeeded`/`failed`). The Python `StrEnum`s and the TypeScript unions
  mirror them exactly; changing one means changing all three.
- Every collection has a `uuid` primary key and the four audit fields
  (`date_created`, `date_updated`, `user_created`, `user_updated`).
- `homework` ↔ `questions` is m2m through `homework_questions`; nothing writes that junction's
  rows by hand except through the m2m alias fields.
- `feedback.homework` is the hand-in the feedback is about: a nullable m2o, `SET NULL`, with no
  reverse alias, so a homework's feedback is found by filtering `feedback` on it.
- Deleting a `students` row takes `sessions`, `homework`, `feedback` and `plans` with it, and
  `homework_questions` and `homework_topics` behind the homework. `documents` and
  `generation_jobs` are `SET NULL` and survive as library and history; so do the `questions`,
  `papers`, `document_pages` and topic junctions hanging off those documents. The student's
  `directus_users` row and every file they or their tutor uploaded survive too, and are the
  caller's to delete.
- `topics` is a free tree the tutor builds: no fixed subject list and no syllabus behind it.
  `parent` is a nullable self-m2o, `SET NULL` on delete, so deleting a topic promotes its
  children rather than losing them. Nothing enforces a depth or a root set.
- A topic junction is named `<owning collection>_topics`, carries `sort`, cascades on both
  sides, and exposes `topics` on the owning collection and the owner's plural name on `topics`.
  A new collection that wants topics gets its own junction; none is ever reused.
- A `scan` document's pages hang off the `document_pages` junction — `documents.pages` on one
  side, the `document_page` o2m on `directus_files` on the other, `sort` ordering them,
  `CASCADE` on both legs — and a page row is reachable exactly as far as the document it
  belongs to, which is also what the tutor file rule rides; `documents.file` stays the
  single-file upload. `documents.paper` is the paper a solutions scan answers: `SET NULL`, and
  the opposite direction from `papers.document`.
- `directus_files` carries six o2m alias fields — `homework_pdf`, `homework_submission_file`,
  `document_file`, `document_page`, `paper_rendered_pdf` and `paper_mark_scheme_pdf` — purely
  so a permission rule can filter a file by the row that references it. Without the alias field
  Directus stores such a rule and then fails every read with a Postgres error, so the aliases
  are load-bearing, not decoration. They are in the snapshot and `schema apply` creates them.
- A student reads a file only if it is their own homework's `pdf` or `submission_file`, or they
  uploaded it; the third arm is what lets them read back an upload not yet linked to a row.
  `/assets/<id>` honours the same rule, so the PDF is served by Directus, not by the app.
- `students.user` is unique and nullable, `SET NULL` on delete: a `directus_users` row links to
  at most one student, and removing the login leaves the student and their work intact.
- Everything the `Student` role can reach hangs off the one `students` row whose `user` is the
  caller. A student never sees `students.notes`, `sessions.notes`, `homework.generated_from`,
  `questions.answer`, `draft` homework, `draft` feedback, `draft` plans, `documents`,
  `generation_jobs`, or any `directus_users` row but their own.
- The Student policy is `app_access: false`: students reach the API and never the admin app.
- A student's only writes are `homework` update — fields `submission`, `submission_file`,
  `submission_transcription`, `submitted_at`, `status`, on rows still `assigned`, with `status`
  allowed to become `submitted` and nothing else — `directus_files` create for the hand-in
  itself, `directus_files` delete of their own uploads, and their own account. The row filter is
  what stops a second hand-in. `submission_transcription` and `marking` are in their read list
  and in no write list of theirs; `homework` is in their `feedback` read list.
- `topics` is the one collection a student reads unfiltered: it is a shared vocabulary, not
  anyone's data. The junctions are still scoped to their own homework, and `document_topics`
  is not granted at all because a student reaches no `documents` row.
- Row filters, narrowed `fields` and `validation` on a `directus_permissions` row are the
  licensed `custom_permission_rules_enabled` entitlement (`GET /license`, `.default`). Core
  Directus rejects such a row unless it matches one of Directus's own recommended app
  permissions. Unentitled, `scripts/directus-bootstrap.sh` still creates both roles and
  policies and warns twice: the `Student` grants are skipped entirely (a student sees nothing
  rather than everything), and the `Tutor` grants are made unfiltered, so on an unlicensed
  instance every tutor reads and writes every other tutor's work.
- A tutor reaches the `students` rows whose `tutor` is them and everything hanging off those
  rows. `students` create presets `tutor` to the caller and validates it; update validates it
  too, so a student cannot be handed to another tutor. A `students` row with a null `tutor` —
  the example student included — is reachable by an admin only.
- A `documents` or `questions` row with no student behind it is the agency library: every tutor
  reads it and its file and topic tags, and only its creator may change or delete it. A rule
  arm that tests a related row's student for null is guarded — `_null` across an m2o also
  matches rows with no relation at all, and across an o2m alias it needs `_some` in an arm of
  its own, since `_some` under a shared `_or` matches everything.
- `papers` is the canonical form of an exam paper from any source. `structure` is one JSON
  column holding the whole `Paper` that `services/typeset/src/document.rs` defines, and
  `mark_scheme` the whole `MarkScheme`, so a review edit is one write and rendering one read.
  Field names and nesting mirror that file exactly; the typeset service refuses anything else.
- A `papers` row reaches its student through `document` alone. A tutor reads it when the
  document's student is theirs, when the document has no student, or when the paper has no
  document; only its creator may change or delete it. Both `document` arms carry the `_nnull`
  guard the questions rules need, and the no-document arm is separate.
- `papers.document`, `papers.rendered_pdf` and `papers.mark_scheme_pdf` are all `SET NULL`:
  deleting the source document or either PDF leaves the structure, which is the source of truth.
- `questions` carries the paper-lifted fields `paper`, `number`, `marks`, `parts`,
  `answer_lines` and `mark_scheme`; `parts` and `mark_scheme` are the same canonical shapes.
- A student reaches no `papers` row and no file behind one. There is no Student grant on the
  collection at all.
- Presets are applied before validation, so a create that omits a preset field passes the
  validation on it.
- Directus ignores a permission row's `permissions` on create and checks `validation` against
  the payload alone, where a relation is a bare id. No create rule can therefore reach through
  a relation, and a tutor can create a `sessions`, `documents`, `homework`, `feedback`,
  `plans`, `generation_jobs`, `questions` or junction row pointing at another tutor's student.
  **The app and MCP layers enforce that; Directus cannot.**
- `directus_users` carries a `student` o2m alias, from `students.user`, purely so a permission
  rule can filter a user by the student that links to them. Without it Directus stores such a
  rule and silently drops that arm, leaving every tutor reading every student login; the
  bootstrap refuses to grant when the alias is absent.
- A tutor creating a `directus_users` row gets `204` and an empty body: the new login matches
  no read rule until a student links to it, and it cannot be found afterwards either. A
  readable id comes from a nested create on a student's own `user` field.
- A tutor reads a file through `uploaded_by`, their own students' homework aliases, or the
  `document_file`, `document_page`, `paper_rendered_pdf` and `paper_mark_scheme_pdf` aliases.
  Each of those four needs `_some` in an `_or` arm of its own — `_some` under a shared `_or`
  matches everything — and a paper's or a page's arm rides the m2o to `document`, so one null
  test covers both the student-less document and the paper that has none. Writing is not
  widened by the library.
- A `questions` row unlinked from both its document and its homework is reachable by its
  creator alone.
- `directus_roles` has no `admin_access` in Directus 12 — it lives on the policy — and a tutor
  reads only `id` and `name` of a role. `GET /policies/me/globals` is the admin probe: it
  answers `{app_access, admin_access, enforce_tfa}` for the caller, whoever they are.
- `app_access: true` does not supply a readable `directus_roles` or `directus_users` in
  Directus 12; a tutor's grants on both are explicit.
- `POST /auth/login` answers every refusal with `401 INVALID_CREDENTIALS` / "Invalid user
  credentials.": a `suspended`, `inactive` or `archived` user, a wrong password and an unknown
  address are indistinguishable from the response. Telling a suspended user so means reading
  their `status` server-side, never the login error.
- The admin app authenticates by the `directus_session_token` cookie alone, which only
  `POST /auth/login` with `mode: "session"` issues. A json-mode token buys nothing there:
  `?access_token=` on an `/admin` route is ignored, and `POST /auth/refresh` with
  `mode: "session"` refuses a refresh token in the payload. The app's own session cannot be
  handed to it without a second login.
- A policy may hold more than one permission row for the same collection and action, and
  Directus evaluates each row on its own: one row's field list never widens another's. Both
  policies carry a self-service `directus_users` update row — `{id: {_eq: "$CURRENT_USER"}}`
  over `first_name`, `last_name`, `email`, `password`, `avatar`, `appearance` — beside, on the
  Tutor policy, the row for their students' logins. `role`, `status` and `token` are in no row,
  so nobody edits their own standing.
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
