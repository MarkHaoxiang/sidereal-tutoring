use axum::{Router, http::StatusCode, routing::get};

pub fn router() -> Router {
    Router::new().route("/healthz", get(healthz))
}

/// Liveness only: it says the process is up and serving, not that Directus is reachable.
async fn healthz() -> (StatusCode, &'static str) {
    (StatusCode::OK, "ok")
}
