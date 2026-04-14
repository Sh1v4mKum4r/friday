use std::path::PathBuf;
use tokio::net::UnixListener;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use crate::client::FridayClient;

pub fn socket_path() -> PathBuf {
    // Use XDG_RUNTIME_DIR if available, fallback to /tmp
    let runtime_dir = std::env::var("XDG_RUNTIME_DIR")
        .unwrap_or_else(|_| "/tmp".to_string());
    PathBuf::from(runtime_dir).join("friday.sock")
}

pub async fn start_socket_listener(host: String, port: u16) -> Result<(), Box<dyn std::error::Error>> {
    let path = socket_path();

    // Remove stale socket
    let _ = std::fs::remove_file(&path);

    let listener = UnixListener::bind(&path)?;
    println!("Friday daemon listening on {}", path.display());

    loop {
        match listener.accept().await {
            Ok((stream, _)) => {
                let h = host.clone();
                tokio::spawn(async move {
                    handle_connection(stream, &h, port).await;
                });
            }
            Err(e) => eprintln!("Socket accept error: {}", e),
        }
    }
}

async fn handle_connection(stream: tokio::net::UnixStream, host: &str, port: u16) {
    let (reader, mut writer) = stream.into_split();
    let mut buf_reader = BufReader::new(reader);
    let mut line = String::new();

    if buf_reader.read_line(&mut line).await.is_err() {
        return;
    }

    let prompt = line.trim().to_string();
    if prompt.is_empty() {
        return;
    }

    let client = FridayClient::new(host, port);

    eprintln!("[socket] Forwarding prompt to backend: {}", &prompt);

    match client.chat(&prompt, None).await {
        Ok(resp) => {
            eprintln!("[socket] Got response ({} chars) from {}", resp.response.len(), resp.provider);
            // Send notification
            let _ = std::process::Command::new("notify-send")
                .arg("Friday")
                .arg(&resp.response)
                .spawn();

            // Write response back to socket
            let _ = writer.write_all(resp.response.as_bytes()).await;
            let _ = writer.write_all(b"\n").await;
            let _ = writer.flush().await;
        }
        Err(e) => {
            let err = format!("Error: {}", e);
            eprintln!("[socket] Error: {}", &err);
            let _ = std::process::Command::new("notify-send")
                .arg("Friday Error")
                .arg(&err)
                .spawn();
            let _ = writer.write_all(err.as_bytes()).await;
            let _ = writer.write_all(b"\n").await;
            let _ = writer.flush().await;
        }
    }
}

// Cleanup on shutdown
pub fn cleanup_socket() {
    let _ = std::fs::remove_file(socket_path());
}
