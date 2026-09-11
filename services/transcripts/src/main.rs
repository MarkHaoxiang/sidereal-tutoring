//! The transcripts worker. Configured by environment variable:
//!
//! | Variable | Default | Meaning |
//! | --- | --- | --- |
//! | `SIDEREAL_TRANSCRIPTS_ADDR` | `127.0.0.1:50051` | listen address |
//! | `SIDEREAL_TRANSCRIPTS_POLL_SECS` | `30` | seconds between polls |
//! | `SIDEREAL_DIRECTUS_URL` | required | Directus root |
//! | `SIDEREAL_DIRECTUS_TOKEN` | required | Directus static token |
//!
//! It serves `GET /healthz` and reports the pending `transcript` documents it finds. It does
//! not transcribe: no transcription backend has been chosen, so no document changes status.

use anyhow::{Context, Result, bail};
use sidereal_common::{
    DIRECTUS_URL, bind_addr_from_env, directus_from_env, init_tracing, secs_from_env,
};
use sidereal_directus::Client;
use sidereal_transcripts::{poll_loop, router};
use tokio::net::TcpListener;
use tokio::sync::watch;

const ADDR_VAR: &str = "SIDEREAL_TRANSCRIPTS_ADDR";
const DEFAULT_ADDR: &str = "127.0.0.1:50051";
const POLL_VAR: &str = "SIDEREAL_TRANSCRIPTS_POLL_SECS";
const DEFAULT_POLL_SECS: u64 = 30;

#[tokio::main]
async fn main() -> Result<()> {
    init_tracing();

    let addr = bind_addr_from_env(ADDR_VAR, DEFAULT_ADDR)?;
    let period = secs_from_env(POLL_VAR, DEFAULT_POLL_SECS)?;
    if period.is_zero() {
        bail!("{POLL_VAR} must be at least 1");
    }
    let directus = directus_from_env()?;
    let client = Client::new(&directus.url, &directus.token)
        .with_context(|| format!("{DIRECTUS_URL} is not a usable Directus URL"))?;

    let listener = TcpListener::bind(addr)
        .await
        .with_context(|| format!("binding {addr}"))?;
    tracing::info!(
        %addr,
        poll_secs = period.as_secs(),
        directus = %directus.url,
        "sidereal-transcripts started"
    );

    // One flag both the server and the poll loop watch, so a signal stops the whole process
    // rather than leaving a loop polling a shutting-down service.
    let (shutdown, poll_rx) = watch::channel(false);
    let mut serve_rx = poll_rx.clone();
    let poller = tokio::spawn(poll_loop(client, period, poll_rx));
    let signals = tokio::spawn(async move {
        shutdown_signal().await;
        tracing::info!("shutting down");
        let _ = shutdown.send(true);
    });

    axum::serve(listener, router())
        .with_graceful_shutdown(async move {
            let _ = serve_rx.changed().await;
        })
        .await
        .context("serving")?;
    poller.await.context("the poll loop stopped abnormally")?;
    signals.abort();
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
}
