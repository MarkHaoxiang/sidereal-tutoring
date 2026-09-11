#![allow(clippy::unwrap_used, clippy::panic)]

use std::time::Duration;

use serde_json::json;
use sidereal_directus::Client;
use sidereal_transcripts::{pending_transcripts, poll_loop, poll_once};
use tokio::sync::watch;
use uuid::Uuid;
use wiremock::matchers::{method, path, query_param};
use wiremock::{Mock, MockServer, ResponseTemplate};

const ID: &str = "3f2504e0-4f89-41d3-9a0c-0305e82c3301";

async fn stub_with_one_pending() -> MockServer {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/items/documents"))
        .and(query_param(
            "filter",
            r#"{"kind":{"_eq":"transcript"},"status":{"_eq":"pending"}}"#.to_owned(),
        ))
        .and(query_param("sort", "date_created"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "data": [{"id": ID, "title": "Session recording", "source_url": null}]
        })))
        .mount(&server)
        .await;
    server
}

#[tokio::test]
async fn pending_transcripts_filters_on_kind_and_status() {
    let server = stub_with_one_pending().await;
    let client = Client::new(&server.uri(), "token").unwrap();

    let pending = pending_transcripts(&client).await.unwrap();
    assert_eq!(pending.len(), 1);
    assert_eq!(pending[0].id, Uuid::parse_str(ID).unwrap());
    assert_eq!(pending[0].title.as_deref(), Some("Session recording"));
    assert_eq!(pending[0].source_url, None);
}

#[tokio::test]
async fn a_poll_never_writes() {
    let server = stub_with_one_pending().await;
    let client = Client::new(&server.uri(), "token").unwrap();

    poll_once(&client).await;

    let requests = server.received_requests().await.unwrap();
    let methods: Vec<String> = requests
        .iter()
        .map(|request| request.method.to_string())
        .collect();
    assert!(
        methods.iter().all(|verb| verb == "GET"),
        "the poll issued a non-GET request: {methods:?}"
    );
}

#[tokio::test]
async fn an_unreachable_directus_does_not_stop_the_poll() {
    // Reserved and never routable, so the call fails rather than hanging on a real host.
    let client = Client::new("http://127.0.0.1:1", "token").unwrap();
    poll_once(&client).await;
}

#[tokio::test]
async fn the_loop_stops_on_the_shutdown_flag() {
    let server = stub_with_one_pending().await;
    let client = Client::new(&server.uri(), "token").unwrap();
    let (shutdown, rx) = watch::channel(false);

    let loop_handle = tokio::spawn(poll_loop(client, Duration::from_millis(20), rx));
    tokio::time::sleep(Duration::from_millis(60)).await;
    shutdown.send(true).unwrap();

    tokio::time::timeout(Duration::from_secs(5), loop_handle)
        .await
        .expect("the poll loop did not stop")
        .unwrap();
    assert!(!server.received_requests().await.unwrap().is_empty());
}
