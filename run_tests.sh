#!/usr/bin/env bash
# Run both workspaces' test suites: the uv workspace (packages/) and the cargo workspace
# (crates/, services/). Exit code 5 (no tests collected) is tolerated for pytest so a freshly
# scaffolded package does not fail the run.
#
# SIDEREAL_SKIP_RUST=1 skips the cargo section. It exists for the CI `tests` job, which would
# otherwise duplicate the dedicated `rust` job's toolchain fetch and build on every push; a
# human should not normally set it, since it means Rust goes untested.
set -uo pipefail

status=0
for pkg in sidereal-core sidereal-ingest sidereal-generate sidereal-mcp sidereal-app; do
    echo "=== ${pkg} ==="
    uv run --package "${pkg}" pytest "packages/${pkg}/tests"
    code=$?
    if [[ ${code} -ne 0 && ${code} -ne 5 ]]; then
        status=1
    fi
done

if [[ "${SIDEREAL_SKIP_RUST:-}" == "1" ]]; then
    echo "=== cargo test --workspace: skipped (SIDEREAL_SKIP_RUST=1) ==="
else
    echo "=== cargo test --workspace ==="
    if ! command -v cargo >/dev/null 2>&1; then
        echo "cargo not found: the repo contains Rust code (crates/, services/), so this is an" >&2
        echo "error, not a skip. Install it via rustup: https://rustup.rs" >&2
        status=1
    else
        cargo test --workspace
        code=$?
        if [[ ${code} -ne 0 ]]; then
            status=1
        fi
    fi
fi

exit ${status}
