#![allow(clippy::unwrap_used, clippy::panic)]

use sidereal_transcripts::router;
use tokio::net::TcpListener;

#[tokio::test]
async fn healthz_answers_ok() {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    let server = tokio::spawn(async move {
        axum::serve(listener, router()).await.unwrap();
    });

    let response = reqwest::get(format!("http://{addr}/healthz"))
        .await
        .unwrap();
    assert_eq!(response.status().as_u16(), 200);
    assert_eq!(response.text().await.unwrap(), "ok");

    let missing = reqwest::get(format!("http://{addr}/")).await.unwrap();
    assert_eq!(missing.status().as_u16(), 404);

    server.abort();
}
