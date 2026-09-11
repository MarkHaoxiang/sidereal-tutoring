# sidereal-common — invariants

## Invariants

- **A variable set to the empty string is unset.** Every reader here goes through one `env`.
- **A missing optional variable falls back; a missing required one is `ConfigError::Missing`.**
  Nothing here panics or exits — the caller decides.
- **Errors name the variable and the offending value**, since the operator only sees the log line.
- **`init_tracing` is idempotent** and installs exactly one subscriber, filtered by `RUST_LOG`.
- **The parsing is tested through pure functions taking the value**, never by setting process
  environment variables: `std::env::set_var` is unsafe in edition 2024 and `unsafe_code` is
  forbidden workspace-wide.
- No domain types, no I/O, no Directus client here.
