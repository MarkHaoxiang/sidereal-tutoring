use std::time::Duration;

use sidereal_directus::Client;
use tokio::sync::watch;
use tokio::time::{MissedTickBehavior, interval};

use crate::documents::pending_transcripts;

/// Polls until `shutdown` carries `true` (or its sender is dropped). A tick missed because
/// Directus was slow is delayed, never fired back-to-back.
pub async fn poll_loop(client: Client, period: Duration, mut shutdown: watch::Receiver<bool>) {
    // `interval` panics on a zero period; `main` rejects one, and this keeps the library total.
    let mut ticker = interval(period.max(Duration::from_millis(1)));
    ticker.set_missed_tick_behavior(MissedTickBehavior::Delay);
    loop {
        tokio::select! {
            _ = ticker.tick() => poll_once(&client).await,
            _ = shutdown.changed() => break,
        }
    }
    tracing::debug!("poll loop stopped");
}

/// Reports what is waiting and returns. It does not transcribe, and it never writes: no
/// document's status changes until there is a transcription backend to change it for.
pub async fn poll_once(client: &Client) {
    match pending_transcripts(client).await {
        Ok(pending) if pending.is_empty() => {
            tracing::debug!("no pending transcript documents");
        }
        Ok(pending) => {
            tracing::info!(
                count = pending.len(),
                "pending transcript documents found; no transcription backend is wired, so they \
                 stay pending"
            );
            for document in &pending {
                tracing::info!(
                    id = %document.id,
                    title = document.title.as_deref().unwrap_or(""),
                    source_url = document.source_url.as_deref().unwrap_or(""),
                    "pending transcript document"
                );
            }
        }
        Err(error) => {
            tracing::warn!(
                error = %chain(&error),
                "listing pending transcript documents failed; retrying on the next tick"
            );
        }
    }
}

/// `Display` on one error shows only its own message, and the reason a poll failed is always in
/// the source chain (connection refused, DNS, a Directus status).
fn chain(error: &dyn std::error::Error) -> String {
    let mut message = error.to_string();
    let mut source = error.source();
    while let Some(cause) = source {
        message.push_str(": ");
        message.push_str(&cause.to_string());
        source = cause.source();
    }
    message
}
