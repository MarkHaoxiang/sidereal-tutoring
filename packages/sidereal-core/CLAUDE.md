# sidereal-core

Bottom layer. Imports no other workspace package.

## Invariants

- No LLM calls, no scraping, no filesystem state. Directus and the typeset service are the only
  external services reached.
- Models are the shared vocabulary: Directus collections, pydantic models and the frontend's TS types
  carry the same field names and the same lowercase status tokens.
- One model per collection plus a `<Name>Draft` for creation. A `Draft` has no `id` and no audit
  fields; a record has both.
- `Draft.payload()` drops `None`: unset means "Directus decides", never "write null".
- Records are frozen and ignore unknown fields, so a Directus schema addition cannot break a read.
- m2o relations are the related row's `UUID`, not a nested object. Requesting `fields` that expand a
  relation would break validation.
- Every failure is a `DirectusClientError`: `DirectusUnavailableError` when Directus cannot be reached,
  `DirectusError` (status + Directus's `errors[]`) when it answers with one.
- Settings are a frozen dataclass over `os.environ`, read on call. No I/O at import.
- A student's login is a `directus_users` row in the `Student` role and `students.user` is the
  link. `logins.py` is the only place one is created, reset or deleted.
- A login is created by `create_related` on the student's own `user` field, never by `POST /users`:
  a tutor cannot read back a user they created alone, so one write both creates and links it.
- Nothing is written against a student without `visible_student` first reading them with the
  caller's own token. Directus checks a create against the payload alone and cannot reach through
  a relation, so this is the only thing keeping one tutor out of another's students.
- The caller is an admin when a policy behind them or their role grants `admin_access`, a student
  when a `students` row points at them, and a tutor otherwise. Admin wins over both.
- `admin_access` is on no row Directus 12 will show — not on a user, not on a role: `me()` reads it
  from `GET /policies/me/globals`, and it is False on every user read any other way.
- `check_email` and `check_password`, and the errors they raise, are shared by student logins and
  tutor accounts.
- A tutor is a `directus_users` row in the `Tutor` role, found by name. A tutor who still has
  students cannot be removed; reassigning them comes first.
- `admin_health` never raises: a service it cannot reach is `ok: false`, and every probe is capped
  at `PROBE_TIMEOUT`.
- A listing never asks per row: ids are gathered and looked up with one `_in` query, and counts come
  from Directus's own aggregate.
- A scan's pages are `document_pages` rows carrying a `sort`; `documents.file` stays the single
  uploaded file, and a scan does not set it.
- Files are Directus's own collection, not `/items`: the row comes from `/files/{id}` and the bytes
  from `/assets/{id}`. `download_file` names the bytes with the row's `filename_download`, never
  with a name parsed out of a response header.
- Users and roles are Directus's own collections too: `/users` and `/roles`, never `/items`.
- Uploading is multipart on `/files`; `upload_file` is the only place the workspace posts bytes.
- Every typeset failure is a `TypesetClientError`: `TypesetUnavailableError` when the service cannot
  be reached, `TypesetError` (status + the compiler's `diagnostics`) when it refuses the source. A
  source that will not compile is never a 500 and never an empty PDF.
- The house template lives in the typeset service, never here: `wrap_homework` asks for it.
- The canonical structures mirror `services/typeset/src/document.rs` — same field names, same
  nesting, unknown fields forbidden on both sides. A name that drifts is a 422 on the first
  render, never a dropped value.
- Parts nest one level because `CanonicalSubPart` is its own model, and no canonical schema refers
  to itself: strict structured output refuses a circular `$def`.
- Optional canonical fields carry defaults, so a structure a tutor edited by hand still reads.
- Every renderer extent is a module constant here and is checked at construction: answer lines,
  height, options, grid, table, figure width, and a section's `choose`.
- A node carries `answer` or the deprecated `answer_lines`, never both.
- `CanonicalBlock` is a plain union, never `Field(discriminator=...)`: a discriminated union is
  `oneOf` in JSON schema and a strict tool schema takes only `anyOf`. Each block's `type` literal
  is what picks the member.
- A canonical model validates one node. Whether a `passage_ref` id is in the paper and whether a
  `figure`'s asset was sent are the service's checks, and stay there.
- `render` sends the structure and never Typst: the markup is the service's to write. A figure's
  bytes go as `assets=`, base64 on the wire, under the name the block asked for; over
  `MAX_ASSET_BYTES` or `MAX_ASSETS_BYTES` is refused here rather than as a 413 there.
- `FakeDirectus.admin` decides what `/users/me` says about the caller's policies; it serves
  `/server/info`, `/license` and `aggregate[count]` the way Directus does.
- `FakeTypeset` compiles nothing. Source — or a rendered document — carrying `FAIL_MARKER` is its
  422; everything else is `FAKE_PDF` or `FAKE_SVG` pages.
