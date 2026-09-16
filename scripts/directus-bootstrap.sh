#!/usr/bin/env bash
# Create the Tutor and Student roles/policies and the agent service account in a running
# Directus. Idempotent: re-running reuses whatever already exists and creates nothing new.
#
#   scripts/directus-bootstrap.sh [--rotate-token]
#
# Roles, policies and permissions are not carried by schema snapshots, which is why they
# live here rather than in directus/schema/snapshot.yaml.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

rotate_token=false
if [ "${1:-}" = "--rotate-token" ]; then
  rotate_token=true
elif [ -n "${1:-}" ]; then
  echo "usage: $0 [--rotate-token]" >&2
  exit 2
fi

if [ ! -f .env ]; then
  echo "no .env found; copy .env.example to .env first" >&2
  exit 1
fi
# An already-exported SIDEREAL_DIRECTUS_URL wins over the one in .env.
url_override="${SIDEREAL_DIRECTUS_URL:-}"

set -a
# shellcheck disable=SC1091
. ./.env
set +a

directus_url="${url_override:-${SIDEREAL_DIRECTUS_URL:-http://localhost:8055}}"
admin_email="${ADMIN_EMAIL:?ADMIN_EMAIL must be set in .env}"
admin_password="${ADMIN_PASSWORD:?ADMIN_PASSWORD must be set in .env}"

role_name="Tutor"
student_role_name="Student"
agent_email="agent@sidereal.example.com"

app_collections=(
  students
  sessions
  documents
  questions
  homework
  feedback
  plans
  generation_jobs
  topics
  homework_questions
  document_topics
  question_topics
  homework_topics
)

for cmd in curl jq; do
  command -v "$cmd" >/dev/null || { echo "$cmd is required" >&2; exit 1; }
done

access_token=""

api() {
  # api <method> <path> [json-body]
  local method="$1" path="$2" body="${3:-}"
  local args=(-fsSg -X "$method" "$directus_url$path" -H "Content-Type: application/json")
  if [ -n "$access_token" ]; then
    args+=(-H "Authorization: Bearer $access_token")
  fi
  if [ -n "$body" ]; then
    args+=(--data "$body")
  fi
  curl "${args[@]}"
}

random_token() {
  if command -v openssl >/dev/null; then
    openssl rand -hex 24
  else
    python3 -c 'import secrets; print(secrets.token_hex(24))'
  fi
}

access_token="$(
  api POST /auth/login "$(jq -nc --arg e "$admin_email" --arg p "$admin_password" \
    '{email: $e, password: $p}')" | jq -r '.data.access_token'
)"
[ -n "$access_token" ] && [ "$access_token" != "null" ] || {
  echo "admin login failed" >&2
  exit 1
}

# --- entitlements -------------------------------------------------------------------------
# Custom permission rules (row filters, narrowed field lists, validation) are a licensed
# feature. Without them neither a student nor a tutor can be isolated to their own rows: the
# Student grants are skipped rather than widened, and the Tutor grants stay unfiltered so a
# tutor can still work.
custom_rules="$(
  api GET /license 2>/dev/null |
    jq -r '.data.entitlements.custom_permission_rules_enabled.default // false' || echo false
)"
if [ "$custom_rules" = "true" ]; then
  echo "license: custom permission rules are entitled"
else
  custom_rules=false
fi

# --- policies, roles, access ----------------------------------------------------------------
ensure_policy() {
  # ensure_policy <name> <icon> <description> <app-access> -> echoes the policy id
  local name="$1" icon="$2" description="$3" app_access="$4" id
  id="$(api GET "/policies?filter[name][_eq]=$name&fields=id&limit=1" | jq -r '.data[0].id // empty')"
  if [ -z "$id" ]; then
    id="$(
      api POST /policies "$(jq -nc --arg n "$name" --arg i "$icon" --arg d "$description" \
        --argjson a "$app_access" '{
          name: $n, icon: $i, description: $d,
          app_access: $a, admin_access: false, enforce_tfa: false
        }')" | jq -r '.data.id'
    )"
    echo "created policy $name ($id)" >&2
  else
    echo "policy $name exists ($id)" >&2
  fi
  printf '%s' "$id"
}

ensure_role() {
  # ensure_role <name> <icon> <description> -> echoes the role id
  local name="$1" icon="$2" description="$3" id
  id="$(api GET "/roles?filter[name][_eq]=$name&fields=id&limit=1" | jq -r '.data[0].id // empty')"
  if [ -z "$id" ]; then
    id="$(
      api POST /roles "$(jq -nc --arg n "$name" --arg i "$icon" --arg d "$description" \
        '{name: $n, icon: $i, description: $d}')" | jq -r '.data.id'
    )"
    echo "created role $name ($id)" >&2
  else
    echo "role $name exists ($id)" >&2
  fi
  printf '%s' "$id"
}

ensure_access() {
  # ensure_access <role-id> <policy-id>. Directus 12 grants a role its policies through
  # `directus_access` rows; a role with no such row has no permissions at all.
  local role="$1" policy="$2" existing
  existing="$(
    api GET "/access?filter[role][_eq]=$role&filter[policy][_eq]=$policy&fields=id&limit=1" |
      jq -r '.data[0].id // empty'
  )"
  if [ -z "$existing" ]; then
    api POST /access "$(jq -nc --arg r "$role" --arg p "$policy" \
      '{role: $r, policy: $p, sort: 1}')" >/dev/null
    echo "attached policy to role"
  fi
}

policy_id="$(ensure_policy "$role_name" school \
  "Full access to the sidereal tutoring collections." true)"
role_id="$(ensure_role "$role_name" school \
  "Private tutors and the agents acting on their behalf.")"
ensure_access "$role_id" "$policy_id"

student_policy_id="$(ensure_policy "$student_role_name" face \
  "Read-only access to a student's own work, plus handing homework in." false)"
student_role_id="$(ensure_role "$student_role_name" face \
  "Students signing in to see their own work. API only; no admin app.")"
ensure_access "$student_role_id" "$student_policy_id"

# --- permissions -------------------------------------------------------------------------
# Every row this script intends to exist, as "<policy-id> <collection> <action>", checked
# again after the cache is dropped.
granted=()
# The permission rows this run has already taken, so a second row for the same collection and
# action does not overwrite the first.
claimed=()

ensure_permission() {
  # ensure_permission <policy-id> <collection> <action> <fields-json> <rule-json> \
  #                   [validation-json] [presets-json]
  local policy="$1" collection="$2" action="$3" fields="$4" rule="$5"
  local validation="${6:-null}" presets="${7:-null}"
  local desired existing current rows
  desired="$(jq -nc --argjson f "$fields" --argjson r "$rule" \
    --argjson v "$validation" --argjson s "$presets" \
    '{fields: $f, permissions: $r, validation: $v, presets: $s}')"
  granted+=("$policy $collection $action")

  # A policy may hold several rows for one collection and action — Directus evaluates each on
  # its own, so a narrow field list on one is not widened by another. The row is therefore
  # matched by its filter first, and only then by whatever row this run has not yet taken.
  rows="$(
    api GET "/permissions?filter[policy][_eq]=$policy&filter[collection][_eq]=$collection&filter[action][_eq]=$action&fields=id,fields,permissions,validation,presets&limit=-1&sort=id"
  )"
  existing="$(
    jq -c --argjson r "$rule" --args '
      def n: if . == null then {} else . end;
      def free: [.data[] | . as $row
        | select(($ARGS.positional | index($row.id | tostring)) == null)];
      ((free | map(select((.permissions | n) == ($r | n))))[0] // (free)[0] // empty)
    ' <<<"$rows" -- "${claimed[@]+"${claimed[@]}"}"
  )"
  [ -z "$existing" ] || claimed+=("$(jq -r '.id' <<<"$existing")")
  if [ -z "$existing" ]; then
    api POST /permissions "$(jq -nc --arg p "$policy" --arg c "$collection" --arg a "$action" \
      --argjson d "$desired" '$d + {policy: $p, collection: $c, action: $a}')" >/dev/null
    echo "granted $action on $collection"
    return 0
  fi
  # Directus stores an omitted rule as null and an empty one as {}; normalise before
  # comparing so a re-run does not rewrite rows it already agrees with.
  current="$(jq -c 'def n: if . == null then {} else . end;
    {fields: (.fields // []), permissions: (.permissions | n),
     validation: (.validation | n), presets: (.presets | n)}' <<<"$existing")"
  desired="$(jq -c 'def n: if . == null then {} else . end;
    {fields: (.fields // []), permissions: (.permissions | n),
     validation: (.validation | n), presets: (.presets | n)}' <<<"$desired")"
  if [ "$current" != "$desired" ]; then
    api PATCH "/permissions/$(jq -r '.id' <<<"$existing")" "$desired" >/dev/null
    echo "updated $action on $collection"
  fi
}

skipped_filtered=false
ensure_filtered_permission() {
  # As ensure_permission, but only on a licensed instance: these rows carry a row filter, a
  # narrowed field list or a validation rule, none of which core Directus will store.
  if [ "$custom_rules" != true ]; then
    skipped_filtered=true
    return 0
  fi
  ensure_permission "$@"
}

# Directus resolves `$CURRENT_USER` inside a filter at request time; it is not a shell
# variable, and reaches the rules below through jq so it is never expanded here.
# shellcheck disable=SC2016
current_user='$CURRENT_USER'

# --- Tutor permissions ----------------------------------------------------------------------
# A tutor reaches the students whose `tutor` is them, and everything that hangs off those
# students. Directus resolves `$CURRENT_USER` at request time.
own_students="$(jq -nc --arg u "$current_user" '{tutor: {_eq: $u}}')"
via_tutor="$(jq -nc --arg u "$current_user" '{student: {tutor: {_eq: $u}}}')"
# `generation_jobs.student` is nullable, so a job with no student is reachable only through
# whoever created it.
via_tutor_or_own="$(jq -nc --arg u "$current_user" \
  '{_or: [{student: {tutor: {_eq: $u}}}, {user_created: {_eq: $u}}]}')"
# One agency, one library: a `documents` or `questions` row with no student behind it is shared
# with every tutor, and only its author may change it.
documents_read="$(jq -nc --arg u "$current_user" \
  '{_or: [{student: {tutor: {_eq: $u}}}, {student: {_null: true}}]}')"
documents_write="$(jq -nc --arg u "$current_user" '{_or: [
  {student: {tutor: {_eq: $u}}},
  {_and: [{student: {_null: true}}, {user_created: {_eq: $u}}]}
]}')"
# A question hangs off a document, off homework through the junction, or off neither. Every arm
# that tests a document's student for null is guarded with `_nnull` on the document itself: a
# question with no document left-joins to a null student and would otherwise match them all.
library_question='{"_and": [{"document": {"_nnull": true}}, {"document": {"student": {"_null": true}}}]}'
loose_question='{"_and": [{"document": {"_null": true}}, {"homework": {"_null": true}}]}'
questions_read="$(jq -nc --arg u "$current_user" \
  --argjson l "$library_question" --argjson o "$loose_question" '{_or: [
  {document: {student: {tutor: {_eq: $u}}}},
  {homework: {homework: {student: {tutor: {_eq: $u}}}}},
  $l,
  $o
]}')"
questions_write="$(jq -nc --arg u "$current_user" \
  --argjson l "$library_question" --argjson o "$loose_question" '{_or: [
  {document: {student: {tutor: {_eq: $u}}}},
  {homework: {homework: {student: {tutor: {_eq: $u}}}}},
  {_and: [$l, {user_created: {_eq: $u}}]},
  {_and: [$o, {user_created: {_eq: $u}}]}
]}')"
via_tutor_homework="$(jq -nc --arg u "$current_user" '{homework: {student: {tutor: {_eq: $u}}}}')"

ensure_scoped() {
  # ensure_scoped <collection> <read-filter> [<write-filter>]. Read, update and delete carry a
  # filter; create cannot. Directus ignores `permissions` on create outright and checks
  # `validation` against the payload alone, where `student` is a bare id, so no create rule can
  # reach through the relation to the student's tutor. The app enforces that; see
  # directus/CLAUDE.md.
  local collection="$1" rule="$2" write="${3:-$2}" action
  ensure_permission "$policy_id" "$collection" read '["*"]' "$rule"
  for action in update delete; do
    ensure_permission "$policy_id" "$collection" "$action" '["*"]' "$write"
  done
  ensure_permission "$policy_id" "$collection" create '["*"]' '{}'
}

tutor_unscoped=false
if [ "$custom_rules" = true ]; then
  # The reverse filter from a user back to their student needs the `directus_users.student`
  # o2m alias. Without it Directus stores the rule and silently drops that arm, which leaves
  # every tutor reading every student login there is, so refuse to grant rather than leak.
  if ! api GET /fields/directus_users/student >/dev/null 2>&1; then
    echo "directus_users.student is missing; run scripts/directus-schema-apply.sh first" >&2
    exit 1
  fi

  # Presets are applied before validation, so a create that omits `tutor` is stamped with the
  # caller and then passes. The same validation on update is what stops a tutor handing a
  # student to another tutor; a payload without `tutor` passes it untouched.
  ensure_permission "$policy_id" students create '["*"]' '{}' "$own_students" \
    "$(jq -nc --arg u "$current_user" '{tutor: $u}')"
  ensure_permission "$policy_id" students read '["*"]' "$own_students"
  ensure_permission "$policy_id" students update '["*"]' "$own_students" "$own_students"
  ensure_permission "$policy_id" students delete '["*"]' "$own_students"

  ensure_scoped sessions "$via_tutor"
  ensure_scoped homework "$via_tutor"
  ensure_scoped feedback "$via_tutor"
  ensure_scoped plans "$via_tutor"
  ensure_scoped documents "$documents_read" "$documents_write"
  ensure_scoped generation_jobs "$via_tutor_or_own"
  ensure_scoped questions "$questions_read" "$questions_write"
  ensure_scoped homework_questions "$via_tutor_homework"
  ensure_scoped homework_topics "$via_tutor_homework"
  # A topic junction is reachable exactly as far as the row it tags.
  ensure_scoped document_topics \
    "$(jq -nc --argjson d "$documents_read" '{document: $d}')" \
    "$(jq -nc --argjson d "$documents_write" '{document: $d}')"
  ensure_scoped question_topics \
    "$(jq -nc --argjson q "$questions_read" '{question: $q}')" \
    "$(jq -nc --argjson q "$questions_write" '{question: $q}')"

  # The topic tree is the practice's shared vocabulary, not any one tutor's data.
  for action in create read update delete; do
    ensure_permission "$policy_id" topics "$action" '["*"]' '{}'
  done

  # Files: their own uploads, plus whatever hangs off their students' homework or documents
  # through the three o2m aliases on `directus_files`. The create preset is what makes the
  # first arm true, and delete is needed or deleting the material that owns a file orphans it
  # in storage. Writing is not widened by the library: a tutor reads another tutor's library
  # file and changes neither it nor the document behind it.
  # The `document_file` arms use `_some` and stay separate. Under one `_or` — or without
  # `_some` at all — the null test matches a file with no document at all, which is every file.
  tutor_files_write="$(jq -nc --arg u "$current_user" '{_or: [
    {uploaded_by: {_eq: $u}},
    {homework_pdf: {student: {tutor: {_eq: $u}}}},
    {homework_submission_file: {student: {tutor: {_eq: $u}}}}
  ]}')"
  tutor_files_read="$(jq -nc --arg u "$current_user" --argjson w "$tutor_files_write" '{_or: [
    $w._or[],
    {document_file: {_some: {student: {tutor: {_eq: $u}}}}},
    {document_file: {_some: {student: {_null: true}}}}
  ]}')"
  ensure_permission "$policy_id" directus_files read '["*"]' "$tutor_files_read"
  for action in update delete; do
    ensure_permission "$policy_id" directus_files "$action" '["*"]' "$tutor_files_write"
  done
  ensure_permission "$policy_id" directus_files create '["*"]' '{}' null \
    "$(jq -nc --arg u "$current_user" '{uploaded_by: $u}')"
else
  for collection in "${app_collections[@]}"; do
    for action in create read update delete; do
      ensure_permission "$policy_id" "$collection" "$action" '["*"]' '{}'
    done
  done
  for action in create read update delete; do
    ensure_permission "$policy_id" directus_files "$action" '["*"]' '{}'
  done
  tutor_unscoped=true
fi

# Student logins, managed from the tutor's student page. The row filter keeps a tutor to the
# Student-role users linked to their own students, plus themselves for /users/me; `role` is
# missing from the update field list so a tutor cannot lift a student login into another role,
# and the create rule is a payload validation because Directus ignores `permissions` on
# create. A field absent from the create list is rejected outright rather than dropped, so
# `provider` — which Directus itself puts in a new user's payload — has to be listed. A login
# created on its own is not linked to a student yet and so is not readable by its creator:
# POST /users answers with an empty body, and the way to a readable id is a nested create on
# the student's own `user` field.
tutor_student_users="$(jq -nc --arg r "$student_role_id" --arg u "$current_user" \
  '{_and: [{role: {_eq: $r}}, {student: {tutor: {_eq: $u}}}]}')"
tutor_user_scope="$(jq -nc --argjson s "$tutor_student_users" --arg u "$current_user" \
  '{_or: [{id: {_eq: $u}}, $s]}')"
ensure_filtered_permission "$policy_id" directus_users create \
  '["email","password","first_name","last_name","role","status","provider"]' '{}' \
  "$(jq -nc --arg r "$student_role_id" '{role: {_eq: $r}}')"
ensure_filtered_permission "$policy_id" directus_users read \
  '["id","email","first_name","last_name","role","status","avatar","appearance"]' \
  "$tutor_user_scope"
ensure_filtered_permission "$policy_id" directus_users update \
  '["email","password","first_name","last_name","status"]' "$tutor_student_users"
ensure_filtered_permission "$policy_id" directus_users delete '["*"]' "$tutor_student_users"

# The account a signed-in user edits on their own profile page. It is a second row on the same
# collection and action as the grant above: Directus evaluates permission rows one at a time,
# so this narrow field list stands on its own and neither row widens the other. `role`,
# `status` and `token` are in neither, so nobody edits their own standing.
account_self="$(jq -nc --arg u "$current_user" '{id: {_eq: $u}}')"
account_fields='["first_name","last_name","email","password","avatar","appearance"]'
ensure_filtered_permission "$policy_id" directus_users update "$account_fields" "$account_self"
ensure_filtered_permission "$student_policy_id" directus_users update \
  "$account_fields" "$account_self"
# `app_access: true` does not carry a readable `directus_roles` in Directus 12, and creating a
# student login means resolving the Student role by name first.
ensure_filtered_permission "$policy_id" directus_roles read '["id","name"]' '{}'

# --- Student permissions ----------------------------------------------------------------------
# Everything a student can see is reached from their own `students` row, which is the row
# whose `user` is them. Field lists are explicit: `students.notes`, `sessions.notes` and
# `homework.generated_from` are the tutor's, and never appear here.
own_student="$(jq -nc --arg u "$current_user" '{user: {_eq: $u}}')"
via_student="$(jq -nc --arg u "$current_user" '{student: {user: {_eq: $u}}}')"

# `user` is readable because Directus refuses a client filter on a field the caller cannot
# read, and finding the caller's own row means filtering on it. It is their own id.
ensure_filtered_permission "$student_policy_id" students read \
  '["id","name","level","subjects","status","user"]' "$own_student"

ensure_filtered_permission "$student_policy_id" sessions read \
  '["id","scheduled_at","duration_minutes","status","student"]' "$via_student"

ensure_filtered_permission "$student_policy_id" homework read \
  '["id","title","content","format","pdf","compile_error","due_on","status","submission","submission_file","submitted_at","date_created","date_updated","student","questions","topics"]' \
  "$(jq -nc --argjson s "$via_student" \
    '{_and: [$s, {status: {_in: ["assigned", "submitted", "marked"]}}]}')"

# Handing homework in. The row filter is what stops a second hand-in: once the row is
# `submitted` it no longer matches and the update is forbidden. The validation is checked
# against the payload alone, so saving a draft answer with no `status` passes and any
# `status` other than `submitted` fails.
ensure_filtered_permission "$student_policy_id" homework update \
  '["submission","submission_file","submitted_at","status"]' \
  "$(jq -nc --argjson s "$via_student" \
    '{_and: [$s, {status: {_in: ["assigned"]}}]}')" \
  '{"status": {"_eq": "submitted"}}'

# The junction and the questions behind it are reachable only along the relation chain back
# to the student's own homework. `questions.answer` is withheld: it is the mark scheme.
ensure_filtered_permission "$student_policy_id" homework_questions read \
  '["id","homework","question","sort"]' \
  "$(jq -nc --argjson s "$via_student" '{homework: $s}')"
ensure_filtered_permission "$student_policy_id" questions read \
  '["id","text","subject","topic","difficulty","topics"]' \
  "$(jq -nc --arg u "$current_user" '{homework: {homework: {student: {user: {_eq: $u}}}}}')"

# Topics are a shared vocabulary, not anyone's private data, so the read is unfiltered. The
# junctions are not: each is scoped back to the student's own homework, `document_topics`
# being absent because a student reaches no `documents` row to begin with.
ensure_filtered_permission "$student_policy_id" topics read \
  '["id","name","parent","description","sort"]' '{}'
ensure_filtered_permission "$student_policy_id" homework_topics read \
  '["id","homework","topic","sort"]' \
  "$(jq -nc --argjson s "$via_student" '{homework: $s}')"
ensure_filtered_permission "$student_policy_id" question_topics read \
  '["id","question","topic","sort"]' \
  "$(jq -nc --arg u "$current_user" \
    '{question: {homework: {homework: {student: {user: {_eq: $u}}}}}}')"

# Files. `homework.pdf` and `homework.submission_file` carry a reverse o2m alias on
# directus_files (`homework_pdf`, `homework_submission_file`, both in the schema snapshot);
# without those alias fields a rule filtering back through the relation is stored happily and
# then fails every read with a database error, so the aliases are what make this rule work.
# A file the student uploaded but has not linked yet is covered by the third arm.
ensure_filtered_permission "$student_policy_id" directus_files read \
  '["id","title","type","filesize","filename_download","uploaded_on"]' \
  "$(jq -nc --argjson s "$via_student" --arg u "$current_user" '{_or: [
    {homework_pdf: $s},
    {homework_submission_file: $s},
    {uploaded_by: {_eq: $u}}
  ]}')"

# Handing in a file. Directus builds an upload's payload itself, so the field list cannot be
# narrowed; the preset is what ties the row to its uploader, which the read rule then uses.
ensure_filtered_permission "$student_policy_id" directus_files create \
  '["*"]' '{}' null "$(jq -nc --arg u "$current_user" '{uploaded_by: $u}')"

# Taking an attachment back off a hand-in. Without the delete the file outlives the link and
# is orphaned in storage; the preset above is what makes `uploaded_by` true of their own.
ensure_filtered_permission "$student_policy_id" directus_files delete \
  '["*"]' "$(jq -nc --arg u "$current_user" '{uploaded_by: {_eq: $u}}')"

ensure_filtered_permission "$student_policy_id" feedback read \
  '["id","content","status","date_created","student"]' \
  "$(jq -nc --argjson s "$via_student" '{_and: [$s, {status: {_eq: "sent"}}]}')"

ensure_filtered_permission "$student_policy_id" plans read \
  '["id","title","content","period_start","period_end","status","date_created","student"]' \
  "$(jq -nc --argjson s "$via_student" \
    '{_and: [$s, {status: {_in: ["active", "completed"]}}]}')"

# `app_access: false` supplies no permissions of its own, so /users/me needs this row.
ensure_filtered_permission "$student_policy_id" directus_users read \
  '["id","email","first_name","last_name","role","avatar","appearance"]' "$account_self"

if [ "$tutor_unscoped" = true ]; then
  cat >&2 <<'WARNING'

  WARNING: tutor isolation is UNAVAILABLE on this Directus. Scoping a tutor to their own
  students needs row filters, which are a licensed feature, so every Tutor grant was made
  unfiltered: each tutor reads and writes every other tutor's students, sessions, material
  and generated work. The grants are made anyway because a tutor with none cannot use the
  app at all. Do not put more than one tutor on an unlicensed instance.

WARNING
fi

if [ "$skipped_filtered" = true ]; then
  cat >&2 <<'WARNING'

  WARNING: this Directus is not entitled to custom permission rules, so every grant that
  needs a row filter, a narrowed field list or a validation rule was SKIPPED. The Student
  role and policy exist but carry no permissions: a student login can sign in and see
  nothing. Student data isolation is unavailable without a license, and the grants are
  skipped rather than widened because an unfiltered read would show every student every
  other student's work. Tutors likewise cannot manage student logins here.

WARNING
fi

# Directus 12 serves permissions from a system cache that new rows do not invalidate, so a
# freshly granted policy is ignored until the cache is dropped.
api POST "/utils/cache/clear?system" >/dev/null

# Directus quietly drops parts of a permission row it will not store, so every intended grant
# is read back rather than assumed.
missing=0
for entry in "${granted[@]}"; do
  read -r g_policy g_collection g_action <<<"$entry"
  if [ "$(
    api GET "/permissions?filter[policy][_eq]=$g_policy&filter[collection][_eq]=$g_collection&filter[action][_eq]=$g_action&aggregate[count]=id" |
      jq -r '.data[0].count.id'
  )" = "0" ]; then
    echo "MISSING: $g_action on $g_collection was not stored" >&2
    missing=$((missing + 1))
  fi
done
[ "$missing" -eq 0 ] || { echo "$missing permission(s) failed to persist" >&2; exit 1; }

# --- service account -----------------------------------------------------------------------
agent_id="$(api GET "/users?filter[email][_eq]=$agent_email&fields=id&limit=1" | jq -r '.data[0].id // empty')"
if [ -z "$agent_id" ]; then
  token="$(random_token)"
  agent_id="$(
    api POST /users "$(jq -nc \
      --arg e "$agent_email" --arg r "$role_id" --arg t "$token" '{
        email: $e,
        first_name: "Sidereal",
        last_name: "Agent",
        role: $r,
        status: "active",
        token: $t,
        provider: "default"
      }')" | jq -r '.data.id'
  )"
  echo "created service account $agent_email ($agent_id)"
elif [ "$rotate_token" = true ]; then
  token="$(random_token)"
  api PATCH "/users/$agent_id" "$(jq -nc --arg t "$token" --arg r "$role_id" \
    '{token: $t, role: $r}')" >/dev/null
  echo "rotated token for $agent_email ($agent_id)"
else
  token="$(api GET "/users/$agent_id?fields=token" | jq -r '.data.token // empty')"
  echo "service account $agent_email exists ($agent_id)"
fi

echo
if [ -n "${token:-}" ] && [ "$token" != "**********" ]; then
  echo "SIDEREAL_DIRECTUS_TOKEN=$token"
else
  echo "The existing static token is concealed by Directus and cannot be read back."
  echo "Re-run with --rotate-token to issue a new one."
fi
