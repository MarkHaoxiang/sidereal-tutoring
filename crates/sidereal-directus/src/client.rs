use reqwest::{Method, RequestBuilder};
use serde::{Serialize, de::DeserializeOwned};
use url::Url;

use crate::{Error, Query};

#[derive(Debug, Clone)]
pub struct Client {
    http: reqwest::Client,
    base: Url,
    token: String,
}

impl Client {
    /// `base_url` is the Directus root (`http://localhost:8055`); `token` is sent as a bearer
    /// token on every request.
    pub fn new(base_url: &str, token: impl Into<String>) -> Result<Self, Error> {
        let base = Url::parse(base_url).map_err(|_| Error::BaseUrl {
            base_url: base_url.to_owned(),
        })?;
        if base.cannot_be_a_base() {
            return Err(Error::BaseUrl {
                base_url: base_url.to_owned(),
            });
        }
        let http = reqwest::Client::builder().build().map_err(Error::Client)?;
        Ok(Self {
            http,
            base,
            token: token.into(),
        })
    }

    pub async fn list_items<T: DeserializeOwned>(
        &self,
        collection: &str,
        query: &Query,
    ) -> Result<Vec<T>, Error> {
        let mut url = self.items_url(collection, None)?;
        let params = query.params();
        // Written here rather than through reqwest's `query` feature: the parameters are already
        // strings, and an empty query must leave the URL without a trailing `?`.
        if !params.is_empty() {
            url.query_pairs_mut().extend_pairs(params);
        }
        self.send(self.http.request(Method::GET, url)).await
    }

    pub async fn get_item<T: DeserializeOwned>(
        &self,
        collection: &str,
        id: &str,
    ) -> Result<T, Error> {
        let url = self.items_url(collection, Some(id))?;
        self.send(self.http.request(Method::GET, url)).await
    }

    pub async fn create_item<B: Serialize + ?Sized, T: DeserializeOwned>(
        &self,
        collection: &str,
        item: &B,
    ) -> Result<T, Error> {
        let url = self.items_url(collection, None)?;
        self.send(self.http.request(Method::POST, url).json(item))
            .await
    }

    pub async fn update_item<B: Serialize + ?Sized, T: DeserializeOwned>(
        &self,
        collection: &str,
        id: &str,
        changes: &B,
    ) -> Result<T, Error> {
        let url = self.items_url(collection, Some(id))?;
        self.send(self.http.request(Method::PATCH, url).json(changes))
            .await
    }

    /// Percent-encodes each segment, so a collection or id never escapes the path.
    fn items_url(&self, collection: &str, id: Option<&str>) -> Result<Url, Error> {
        let mut url = self.base.clone();
        {
            let mut segments = url.path_segments_mut().map_err(|()| Error::BaseUrl {
                base_url: self.base.to_string(),
            })?;
            segments.pop_if_empty().push("items").push(collection);
            if let Some(id) = id {
                segments.push(id);
            }
        }
        Ok(url)
    }

    async fn send<T: DeserializeOwned>(&self, request: RequestBuilder) -> Result<T, Error> {
        let response = request.bearer_auth(&self.token).send().await?;
        let status = response.status();
        let body = response.text().await?;
        if !status.is_success() {
            return Err(Error::Api {
                status,
                messages: directus_errors(&body),
            });
        }
        let envelope: Envelope<T> = serde_json::from_str(&body)?;
        Ok(envelope.data)
    }
}

#[derive(serde::Deserialize)]
struct Envelope<T> {
    data: T,
}

/// A body that is not Directus's error shape (a proxy's HTML, an empty 502) yields no messages
/// rather than masking the status with a decode error.
fn directus_errors(body: &str) -> Vec<String> {
    #[derive(serde::Deserialize)]
    struct Errors {
        errors: Vec<Item>,
    }
    #[derive(serde::Deserialize)]
    struct Item {
        message: String,
    }

    serde_json::from_str::<Errors>(body)
        .map(|errors| errors.errors.into_iter().map(|item| item.message).collect())
        .unwrap_or_default()
}
