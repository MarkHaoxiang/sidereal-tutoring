use serde::Deserialize;
use serde_json::json;
use sidereal_directus::{Client, Error, Query};
use uuid::Uuid;

pub const COLLECTION: &str = "documents";

const KIND: &str = "transcript";
const STATUS: &str = "pending";
/// One page per tick; the loop is a report, not a queue drain.
const BATCH: i64 = 50;

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
pub struct PendingTranscript {
    pub id: Uuid,
    pub title: Option<String>,
    pub source_url: Option<String>,
}

/// The oldest pending `transcript` documents.
pub async fn pending_transcripts(client: &Client) -> Result<Vec<PendingTranscript>, Error> {
    let query = Query::new()
        .filter(json!({"kind": {"_eq": KIND}, "status": {"_eq": STATUS}}))
        .fields(["id", "title", "source_url"])
        .sort(["date_created"])
        .limit(BATCH);
    client.list_items(COLLECTION, &query).await
}
