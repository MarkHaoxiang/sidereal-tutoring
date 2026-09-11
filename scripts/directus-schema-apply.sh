#!/usr/bin/env bash
# Apply directus/schema/snapshot.yaml to the running Directus container.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

docker compose exec -T directus node /directus/cli.js schema apply --yes /directus/schema/snapshot.yaml
