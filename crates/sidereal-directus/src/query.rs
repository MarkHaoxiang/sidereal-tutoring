use serde_json::Value;

/// The subset of Directus's query parameters this client sends.
#[derive(Debug, Clone, Default)]
pub struct Query {
    filter: Option<Value>,
    limit: Option<i64>,
    fields: Vec<String>,
    sort: Vec<String>,
}

impl Query {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// A Directus filter object, e.g. `json!({"status": {"_eq": "pending"}})`.
    #[must_use]
    pub fn filter(mut self, filter: Value) -> Self {
        self.filter = Some(filter);
        self
    }

    /// `-1` is Directus's "no limit".
    #[must_use]
    pub fn limit(mut self, limit: i64) -> Self {
        self.limit = Some(limit);
        self
    }

    #[must_use]
    pub fn fields<I, S>(mut self, fields: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.fields = fields.into_iter().map(Into::into).collect();
        self
    }

    /// Field names, each optionally prefixed with `-` for descending.
    #[must_use]
    pub fn sort<I, S>(mut self, sort: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        self.sort = sort.into_iter().map(Into::into).collect();
        self
    }

    pub(crate) fn params(&self) -> Vec<(&'static str, String)> {
        let mut params = Vec::new();
        if let Some(filter) = &self.filter {
            params.push(("filter", filter.to_string()));
        }
        if let Some(limit) = self.limit {
            params.push(("limit", limit.to_string()));
        }
        if !self.fields.is_empty() {
            params.push(("fields", self.fields.join(",")));
        }
        if !self.sort.is_empty() {
            params.push(("sort", self.sort.join(",")));
        }
        params
    }
}

#[cfg(test)]
mod tests {
    #![allow(clippy::unwrap_used, clippy::panic)]

    use super::Query;
    use serde_json::json;

    #[test]
    fn an_empty_query_has_no_parameters() {
        assert!(Query::new().params().is_empty());
    }

    #[test]
    fn parameters_are_directus_spellings() {
        let params = Query::new()
            .filter(json!({"kind": {"_eq": "transcript"}}))
            .limit(-1)
            .fields(["id", "title"])
            .sort(["status", "-date_created"])
            .params();

        assert_eq!(
            params,
            vec![
                ("filter", r#"{"kind":{"_eq":"transcript"}}"#.to_owned()),
                ("limit", "-1".to_owned()),
                ("fields", "id,title".to_owned()),
                ("sort", "status,-date_created".to_owned()),
            ]
        );
    }
}
