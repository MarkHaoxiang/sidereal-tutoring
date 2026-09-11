#!/usr/bin/env bash
# Create the Tutor role/policy and the agent service account in a running Directus.
# Idempotent: re-running reuses whatever already exists and creates nothing new.
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

# --- policy -----------------------------------------------------------------------------
policy_id="$(api GET "/policies?filter[name][_eq]=$role_name&fields=id&limit=1" | jq -r '.data[0].id // empty')"
if [ -z "$policy_id" ]; then
  policy_id="$(
    api POST /policies "$(jq -nc --arg n "$role_name" '{
      name: $n,
      icon: "school",
      description: "Full access to the sidereal tutoring collections.",
      app_access: true,
      admin_access: false,
      enforce_tfa: false
    }')" | jq -r '.data.id'
  )"
  echo "created policy $role_name ($policy_id)"
else
  echo "policy $role_name exists ($policy_id)"
fi

# --- role -------------------------------------------------------------------------------
role_id="$(api GET "/roles?filter[name][_eq]=$role_name&fields=id&limit=1" | jq -r '.data[0].id // empty')"
if [ -z "$role_id" ]; then
  role_id="$(
    api POST /roles "$(jq -nc --arg n "$role_name" '{
      name: $n,
      icon: "school",
      description: "Private tutors and the agents acting on their behalf."
    }')" | jq -r '.data.id'
  )"
  echo "created role $role_name ($role_id)"
else
  echo "role $role_name exists ($role_id)"
fi

# --- role <-> policy --------------------------------------------------------------------
access_id="$(
  api GET "/access?filter[role][_eq]=$role_id&filter[policy][_eq]=$policy_id&fields=id&limit=1" |
    jq -r '.data[0].id // empty'
)"
if [ -z "$access_id" ]; then
  api POST /access "$(jq -nc --arg r "$role_id" --arg p "$policy_id" \
    '{role: $r, policy: $p, sort: 1}')" >/dev/null
  echo "attached policy to role"
else
  echo "policy already attached to role"
fi

# --- permissions -------------------------------------------------------------------------
ensure_permission() {
  # ensure_permission <collection> <action> <fields-json> <rule-json>
  local collection="$1" action="$2" fields="$3" rule="$4"
  local existing
  existing="$(
    api GET "/permissions?filter[policy][_eq]=$policy_id&filter[collection][_eq]=$collection&filter[action][_eq]=$action&fields=id&limit=1" |
      jq -r '.data[0].id // empty'
  )"
  if [ -n "$existing" ]; then
    return 0
  fi
  api POST /permissions "$(jq -nc \
    --arg p "$policy_id" --arg c "$collection" --arg a "$action" \
    --argjson f "$fields" --argjson r "$rule" \
    '{policy: $p, collection: $c, action: $a, fields: $f, permissions: $r, validation: {}}')" >/dev/null
  echo "granted $action on $collection"
}

for collection in "${app_collections[@]}"; do
  for action in create read update delete; do
    ensure_permission "$collection" "$action" '["*"]' '{}'
  done
done

# Uploads referenced by documents.
ensure_permission directus_files read '["*"]' '{}'
ensure_permission directus_files create '["*"]' '{}'

# directus_users read is deliberately not granted here. Directus 12's core (unlicensed)
# entitlements reject any permission row that narrows `fields` or carries a `permissions`,
# `validation` or `presets` rule, so a self-scoped read of directus_users cannot be stored.
# `app_access: true` on the policy already supplies Directus's recommended app permissions
# at runtime, which is what makes /users/me work for the agent token.

# Directus 12 serves permissions from a system cache that new rows do not invalidate, so a
# freshly granted policy is ignored until the cache is dropped.
api POST "/utils/cache/clear?system" >/dev/null

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
