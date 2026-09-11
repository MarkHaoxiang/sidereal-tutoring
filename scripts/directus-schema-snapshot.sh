#!/usr/bin/env bash
# Snapshot the running Directus instance's schema. Writes directus/schema/snapshot.yaml
# unless another output path is given.
#
#   scripts/directus-schema-snapshot.sh [output-path]
set -euo pipefail

invocation_dir="$PWD"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

output="${1:-$repo_root/directus/schema/snapshot.yaml}"
case "$output" in
  /*) ;;
  *) output="$invocation_dir/$output" ;;
esac

cd "$repo_root"

# The container can only write to the bind-mounted schema directory, so the snapshot lands
# there first and is moved to the requested destination afterwards.
staging_name=".snapshot.staging.yaml"

docker compose exec -T directus \
  node /directus/cli.js schema snapshot --yes --format yaml "/directus/schema/$staging_name"

mkdir -p "$(dirname "$output")"
mv "directus/schema/$staging_name" "$output"
echo "wrote $output"
