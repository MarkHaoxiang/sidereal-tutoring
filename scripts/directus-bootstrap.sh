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
  homework_questions
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
# feature. Without them the Student role cannot be isolated to its own rows at all, so the
# filtered grants are skipped rather than widened.
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

ensure_permission() {
  # ensure_permission <policy-id> <collection> <action> <fields-json> <rule-json> \
  #                   [validation-json] [presets-json]
  local policy="$1" collection="$2" action="$3" fields="$4" rule="$5"
  local validation="${6:-null}" presets="${7:-null}"
  local desired existing current
  desired="$(jq -nc --argjson f "$fields" --argjson r "$rule" \
    --argjson v "$validation" --argjson s "$presets" \
    '{fields: $f, permissions: $r, validation: $v, presets: $s}')"
  granted+=("$policy $collection $action")

  existing="$(
    api GET "/permissions?filter[policy][_eq]=$policy&filter[collection][_eq]=$collection&filter[action][_eq]=$action&fields=id,fields,permissions,validation,presets&limit=1" |
      jq -c '.data[0] // empty'
  )"
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
for collection in "${app_collections[@]}"; do
  for action in create read update delete; do
    ensure_permission "$policy_id" "$collection" "$action" '["*"]' '{}'
  done
done

# Uploads referenced by documents. Delete is needed too: without it, deleting the material
# that owns a file leaves the file orphaned in storage.
for action in create read update delete; do
  ensure_permission "$policy_id" directus_files "$action" '["*"]' '{}'
done

# Student logins, managed from the tutor's student page. The row filter keeps a tutor to
# users in the Student role (plus themselves, for /users/me); `role` is missing from the
# update field list so a tutor cannot lift a student login into another role, and the create
# rule is a payload validation because Directus ignores `permissions` on create. A field
# absent from the create list is rejected outright rather than dropped, so `provider` — which
# Directus itself puts in a new user's payload — has to be listed.
tutor_user_scope="$(jq -nc --arg r "$student_role_name" --arg u "$current_user" \
  '{_or: [{role: {name: {_eq: $r}}}, {id: {_eq: $u}}]}')"
ensure_filtered_permission "$policy_id" directus_users create \
  '["email","password","first_name","last_name","role","status","provider"]' '{}' \
  "$(jq -nc --arg r "$student_role_id" '{role: {_eq: $r}}')"
ensure_filtered_permission "$policy_id" directus_users read \
  '["id","email","first_name","last_name","role","status"]' "$tutor_user_scope"
ensure_filtered_permission "$policy_id" directus_users update \
  '["email","password","first_name","last_name","status"]' \
  "$(jq -nc --arg r "$student_role_name" '{role: {name: {_eq: $r}}}')"
ensure_filtered_permission "$policy_id" directus_users delete \
  '["*"]' "$(jq -nc --arg r "$student_role_name" '{role: {name: {_eq: $r}}}')"
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
  '["id","title","content","due_on","status","submission","submitted_at","date_created","date_updated","student","questions"]' \
  "$(jq -nc --argjson s "$via_student" \
    '{_and: [$s, {status: {_in: ["assigned", "submitted", "marked"]}}]}')"

# Handing homework in. The row filter is what stops a second hand-in: once the row is
# `submitted` it no longer matches and the update is forbidden. The validation is checked
# against the payload alone, so saving a draft answer with no `status` passes and any
# `status` other than `submitted` fails.
ensure_filtered_permission "$student_policy_id" homework update \
  '["submission","submitted_at","status"]' \
  "$(jq -nc --argjson s "$via_student" \
    '{_and: [$s, {status: {_in: ["assigned"]}}]}')" \
  '{"status": {"_eq": "submitted"}}'

# The junction and the questions behind it are reachable only along the relation chain back
# to the student's own homework. `questions.answer` is withheld: it is the mark scheme.
ensure_filtered_permission "$student_policy_id" homework_questions read \
  '["id","homework","question","sort"]' \
  "$(jq -nc --argjson s "$via_student" '{homework: $s}')"
ensure_filtered_permission "$student_policy_id" questions read \
  '["id","text","subject","topic","difficulty"]' \
  "$(jq -nc --arg u "$current_user" '{homework: {homework: {student: {user: {_eq: $u}}}}}')"

ensure_filtered_permission "$student_policy_id" feedback read \
  '["id","content","status","date_created","student"]' \
  "$(jq -nc --argjson s "$via_student" '{_and: [$s, {status: {_eq: "sent"}}]}')"

ensure_filtered_permission "$student_policy_id" plans read \
  '["id","title","content","period_start","period_end","status","date_created","student"]' \
  "$(jq -nc --argjson s "$via_student" \
    '{_and: [$s, {status: {_in: ["active", "completed"]}}]}')"

# `app_access: false` supplies no permissions of its own, so /users/me needs this row.
ensure_filtered_permission "$student_policy_id" directus_users read \
  '["id","email","first_name","last_name","role"]' \
  "$(jq -nc --arg u "$current_user" '{id: {_eq: $u}}')"

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
