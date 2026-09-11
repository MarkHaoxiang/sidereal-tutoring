#![allow(clippy::unwrap_used, clippy::panic)]

use serde::{Deserialize, Serialize};
use serde_json::json;
use sidereal_directus::{Client, Error, Query};
use wiremock::matchers::{body_json, header, method, path, query_param};
use wiremock::{Mock, MockServer, ResponseTemplate};

#[derive(Debug, Deserialize, PartialEq, Eq)]
struct Document {
    id: String,
    title: String,
}

#[derive(Serialize)]
struct NewDocument {
    title: &'static str,
    kind: &'static str,
}

async fn client(server: &MockServer) -> Client {
    Client::new(&server.uri(), "test-token").unwrap()
}

#[tokio::test]
async fn list_items_sends_the_query_and_unwraps_the_envelope() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/items/documents"))
        .and(header("authorization", "Bearer test-token"))
        .and(query_param(
            "filter",
            r#"{"status":{"_eq":"pending"}}"#.to_owned(),
        ))
        .and(query_param("limit", "25"))
        .and(query_param("fields", "id,title"))
        .and(query_param("sort", "-date_created"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "data": [{"id": "d1", "title": "Lesson 1"}]
        })))
        .mount(&server)
        .await;

    let query = Query::new()
        .filter(json!({"status": {"_eq": "pending"}}))
        .limit(25)
        .fields(["id", "title"])
        .sort(["-date_created"]);
    let documents: Vec<Document> = client(&server)
        .await
        .list_items("documents", &query)
        .await
        .unwrap();

    assert_eq!(
        documents,
        vec![Document {
            id: "d1".to_owned(),
            title: "Lesson 1".to_owned()
        }]
    );
}

#[tokio::test]
async fn an_empty_query_sends_no_parameters() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/items/students"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({"data": []})))
        .mount(&server)
        .await;

    let students: Vec<Document> = client(&server)
        .await
        .list_items("students", &Query::new())
        .await
        .unwrap();
    assert!(students.is_empty());

    let requests = server.received_requests().await.unwrap();
    assert_eq!(requests[0].url.query(), None);
}

#[tokio::test]
async fn get_item_addresses_the_item_by_id() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/items/documents/d1"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "data": {"id": "d1", "title": "Lesson 1"}
        })))
        .mount(&server)
        .await;

    let document: Document = client(&server)
        .await
        .get_item("documents", "d1")
        .await
        .unwrap();
    assert_eq!(document.title, "Lesson 1");
}

#[tokio::test]
async fn create_item_posts_the_body() {
    let server = MockServer::start().await;
    Mock::given(method("POST"))
        .and(path("/items/documents"))
        .and(body_json(
            json!({"title": "Lesson 2", "kind": "transcript"}),
        ))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "data": {"id": "d2", "title": "Lesson 2"}
        })))
        .mount(&server)
        .await;

    let created: Document = client(&server)
        .await
        .create_item(
            "documents",
            &NewDocument {
                title: "Lesson 2",
                kind: "transcript",
            },
        )
        .await
        .unwrap();
    assert_eq!(created.id, "d2");
}

#[tokio::test]
async fn update_item_patches_the_item() {
    let server = MockServer::start().await;
    Mock::given(method("PATCH"))
        .and(path("/items/documents/d1"))
        .and(body_json(json!({"status": "ready"})))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({
            "data": {"id": "d1", "title": "Lesson 1"}
        })))
        .mount(&server)
        .await;

    let updated: Document = client(&server)
        .await
        .update_item("documents", "d1", &json!({"status": "ready"}))
        .await
        .unwrap();
    assert_eq!(updated.id, "d1");
}

#[tokio::test]
async fn a_failure_carries_the_status_and_the_directus_messages() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/items/documents"))
        .respond_with(ResponseTemplate::new(403).set_body_json(json!({
            "errors": [
                {"message": "You don't have permission to access this.", "extensions": {"code": "FORBIDDEN"}},
                {"message": "Second problem."}
            ]
        })))
        .mount(&server)
        .await;

    let error = client(&server)
        .await
        .list_items::<Document>("documents", &Query::new())
        .await
        .unwrap_err();

    assert_eq!(error.status().map(|status| status.as_u16()), Some(403));
    let Error::Api { messages, .. } = &error else {
        panic!("expected an API error, got {error:?}");
    };
    assert_eq!(
        messages,
        &[
            "You don't have permission to access this.",
            "Second problem."
        ]
    );
    assert!(
        error
            .to_string()
            .contains("You don't have permission to access this.; Second problem.")
    );
}

#[tokio::test]
async fn a_failure_with_no_directus_error_body_still_carries_the_status() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/items/documents"))
        .respond_with(ResponseTemplate::new(502).set_body_string("<html>bad gateway</html>"))
        .mount(&server)
        .await;

    let error = client(&server)
        .await
        .list_items::<Document>("documents", &Query::new())
        .await
        .unwrap_err();

    assert_eq!(error.status().map(|status| status.as_u16()), Some(502));
    assert!(error.to_string().contains("502"));
    assert!(error.to_string().contains("no message"));
}

#[tokio::test]
async fn a_body_that_is_not_the_expected_shape_is_a_decode_error() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/items/documents/d1"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({"data": {"id": "d1"}})))
        .mount(&server)
        .await;

    let error = client(&server)
        .await
        .get_item::<Document>("documents", "d1")
        .await
        .unwrap_err();
    assert!(matches!(error, Error::Decode(_)), "got {error:?}");
}

#[test]
fn a_base_url_that_cannot_hold_a_path_is_rejected() {
    let error = Client::new("mailto:tutor@example.com", "t").unwrap_err();
    assert!(matches!(error, Error::BaseUrl { .. }), "got {error:?}");
    assert!(matches!(
        Client::new("not a url", "t").unwrap_err(),
        Error::BaseUrl { .. }
    ));
}

#[tokio::test]
async fn a_base_url_with_a_path_prefix_keeps_it() {
    let server = MockServer::start().await;
    Mock::given(method("GET"))
        .and(path("/directus/items/students"))
        .respond_with(ResponseTemplate::new(200).set_body_json(json!({"data": []})))
        .mount(&server)
        .await;

    let client = Client::new(&format!("{}/directus/", server.uri()), "t").unwrap();
    let students: Vec<Document> = client.list_items("students", &Query::new()).await.unwrap();
    assert!(students.is_empty());
}
