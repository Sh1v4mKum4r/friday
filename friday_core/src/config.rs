use serde::Deserialize;
use std::path::PathBuf;

#[derive(Debug, Deserialize, Clone)]
pub struct ProvidersConfig {
    pub ollama_model: Option<String>,
    pub ollama_url: Option<String>,
    pub gemini_api_key: Option<String>,
    pub claude_api_key: Option<String>,
    pub openai_api_key: Option<String>,
}

impl Default for ProvidersConfig {
    fn default() -> Self {
        ProvidersConfig {
            ollama_model: Some("qwen2.5:7b".to_string()),
            ollama_url: Some("http://localhost:11434".to_string()),
            gemini_api_key: None,
            claude_api_key: None,
            openai_api_key: None,
        }
    }
}

#[derive(Debug, Deserialize, Clone)]
pub struct ServerConfig {
    pub port: Option<u16>,
    pub host: Option<String>,
}

impl Default for ServerConfig {
    fn default() -> Self {
        ServerConfig {
            port: Some(65535),
            host: Some("127.0.0.1".to_string()),
        }
    }
}

#[derive(Debug, Deserialize, Clone)]
pub struct BehaviorConfig {
    pub auto_escalate: Option<bool>,
    pub max_workers: Option<u32>,
}

impl Default for BehaviorConfig {
    fn default() -> Self {
        BehaviorConfig {
            auto_escalate: Some(true),
            max_workers: Some(4),
        }
    }
}

#[derive(Debug, Deserialize, Clone)]
pub struct DEConfig {
    #[serde(rename = "override")]
    pub override_de: Option<String>,
}

impl Default for DEConfig {
    fn default() -> Self {
        DEConfig {
            override_de: None,
        }
    }
}

#[derive(Debug, Deserialize, Clone)]
pub struct Config {
    #[serde(default)]
    pub providers: ProvidersConfig,
    #[serde(default)]
    pub server: ServerConfig,
    #[serde(default)]
    pub behavior: BehaviorConfig,
    #[serde(default)]
    pub de: DEConfig,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            providers: ProvidersConfig::default(),
            server: ServerConfig::default(),
            behavior: BehaviorConfig::default(),
            de: DEConfig::default(),
        }
    }
}

pub fn config_dir() -> PathBuf {
    dirs::config_dir()
        .unwrap_or_else(|| PathBuf::from("~/.config"))
        .join("friday")
}

pub fn load_config() -> Config {
    let config_path = config_dir().join("config.toml");

    if !config_path.exists() {
        eprintln!(
            "Warning: config not found at {}. Using defaults.",
            config_path.display()
        );
        return Config::default();
    }

    match std::fs::read_to_string(&config_path) {
        Ok(content) => match toml::from_str::<Config>(&content) {
            Ok(cfg) => cfg,
            Err(e) => {
                eprintln!("Warning: failed to parse config: {}. Using defaults.", e);
                Config::default()
            }
        },
        Err(e) => {
            eprintln!("Warning: failed to read config: {}. Using defaults.", e);
            Config::default()
        }
    }
}
