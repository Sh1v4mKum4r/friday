use reqwest::Client;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize)]
pub struct ChatRequest {
    pub message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub force_provider: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct ChatResponse {
    pub response: String,
    #[serde(default)]
    pub provider: String,
}

#[derive(Debug, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    #[serde(default)]
    pub active_workers: u32,
    #[serde(default)]
    pub provider: String,
}

#[derive(Debug, Clone)]
pub struct FridayClient {
    base_url: String,
    host: String,
    port: u16,
    client: Client,
}

impl FridayClient {
    pub fn new(host: impl Into<String>, port: u16) -> Self {
        let host = host.into();
        let base_url = format!("http://{}:{}", host, port);
        FridayClient {
            base_url,
            host,
            port,
            client: Client::new(),
        }
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    pub fn port(&self) -> u16 {
        self.port
    }

    pub fn host(&self) -> &str {
        &self.host
    }

    pub async fn health(&self) -> Result<HealthResponse, reqwest::Error> {
        let url = format!("{}/health", self.base_url);
        let resp = self.client.get(&url).send().await?.json::<HealthResponse>().await?;
        Ok(resp)
    }

    pub async fn chat(
        &self,
        message: impl Into<String>,
        force_provider: Option<&str>,
    ) -> Result<ChatResponse, reqwest::Error> {
        let url = format!("{}/chat", self.base_url);
        let req = ChatRequest {
            message: message.into(),
            force_provider: force_provider.map(|s| s.to_string()),
        };
        let resp = self
            .client
            .post(&url)
            .json(&req)
            .send()
            .await?
            .json::<ChatResponse>()
            .await?;
        Ok(resp)
    }

    pub async fn reload_tools(&self) -> Result<serde_json::Value, reqwest::Error> {
        let url = format!("{}/reload", self.base_url);
        let resp = self
            .client
            .post(&url)
            .send()
            .await?
            .json::<serde_json::Value>()
            .await?;
        Ok(resp)
    }

    pub async fn get_context(&self) -> Result<String, reqwest::Error> {
        let url = format!("{}/context", self.base_url);
        let resp = self
            .client
            .get(&url)
            .send()
            .await?
            .json::<serde_json::Value>()
            .await?;
        Ok(resp.to_string())
    }
}
