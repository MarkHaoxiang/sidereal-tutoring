use tracing_subscriber::EnvFilter;

/// Installs the process-wide subscriber, filtered by `RUST_LOG` and defaulting to `info`.
/// Idempotent: a second call is a no-op, so a test that calls it cannot fail a later one.
pub fn init_tracing() {
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
    let _ = tracing_subscriber::fmt().with_env_filter(filter).try_init();
}
