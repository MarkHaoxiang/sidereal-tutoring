# sidereal-directus

Async client for Directus's items API.

```rust,ignore
use serde::Deserialize;
use serde_json::json;
use sidereal_directus::{Client, Query};

#[derive(Deserialize)]
struct Student {
    id: String,
    name: String,
}

let client = Client::new("http://localhost:8055", token)?;

let query = Query::new()
    .filter(json!({"status": {"_eq": "active"}}))
    .fields(["id", "name"])
    .sort(["name"])
    .limit(50);
let students: Vec<Student> = client.list_items("students", &query).await?;

let student: Student = client.get_item("students", "…").await?;
let created: Student = client.create_item("students", &json!({"name": "…"})).await?;
let updated: Student = client.update_item("students", &student.id, &json!({"status": "paused"})).await?;
```

On a non-2xx response the call returns `Error::Api`; `Error::status()` gives the HTTP status and the
variant's `messages` are Directus's `errors[].message`.

```sh
cargo test -p sidereal-directus
```
