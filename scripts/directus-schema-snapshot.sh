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

# The container writes inside its own /tmp, which the `node` user owns, rather than into the
# bind-mounted schema directory: that directory is mounted read-only, and on a CI runner it
# belongs to a uid the container cannot write as either way. The file is then streamed to the
# host over `cat`.
container_path="/tmp/sidereal-schema-snapshot.$$.yaml"
staging_host="$(mktemp)"
trap 'rm -f "$staging_host"' EXIT

docker compose exec -T directus \
  node /directus/cli.js schema snapshot --yes --format yaml "$container_path"
docker compose exec -T directus cat "$container_path" >"$staging_host"
docker compose exec -T directus rm -f "$container_path"

mkdir -p "$(dirname "$output")"
mv "$staging_host" "$output"
echo "wrote $output"
