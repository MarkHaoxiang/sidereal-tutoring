//! The typeset service. Configured by environment variable:
//!
//! | Variable | Default | Meaning |
//! | --- | --- | --- |
//! | `SIDEREAL_TYPESET_ADDR` | `127.0.0.1:50052` | listen address |
//!
//! It serves `GET /healthz`, `POST /compile` and `POST /template`. It reaches nothing else: no
//! Directus, no filesystem, no network.

use anyhow::{Context, Result};
use sidereal_common::{bind_addr_from_env, init_tracing};
use sidereal_typeset::router;
use tokio::net::TcpListener;

const ADDR_VAR: &str = "SIDEREAL_TYPESET_ADDR";
const DEFAULT_ADDR: &str = "127.0.0.1:50052";

#[tokio::main]
async fn main() -> Result<()> {
    init_tracing();

    let addr = bind_addr_from_env(ADDR_VAR, DEFAULT_ADDR)?;
    let listener = TcpListener::bind(addr)
        .await
        .with_context(|| format!("binding {addr}"))?;
    tracing::info!(%addr, "sidereal-typeset started");

    axum::serve(listener, router())
        .with_graceful_shutdown(shutdown_signal())
        .await
        .context("serving")?;
    tracing::info!("stopped");
    Ok(())
}

async fn shutdown_signal() {
    let interrupt = async {
        let _ = tokio::signal::ctrl_c().await;
    };

    #[cfg(unix)]
    let terminate = async {
        use tokio::signal::unix::{SignalKind, signal};
        match signal(SignalKind::terminate()) {
            Ok(mut stream) => {
                stream.recv().await;
            }
            Err(error) => {
                tracing::warn!(%error, "cannot listen for SIGTERM; SIGINT still stops the service");
                std::future::pending::<()>().await;
            }
        }
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        () = interrupt => {},
        () = terminate => {},
    }
    tracing::info!("shutting down");
}
