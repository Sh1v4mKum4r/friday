use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::process::Command;
use tokio::io::{stdin, stdout, AsyncBufReadExt, AsyncWriteExt, BufReader};

#[derive(Serialize)]
struct MessageRequest {
    message: String,
    agent_type: String,
}

#[derive(Deserialize, Debug)]
struct MessageResponse {
    response: String,
    agent_type: String,
}

async fn fetch_ai_response(client: &Client, message: &str, agent_type: &str) -> Result<String, reqwest::Error> {
    let req = MessageRequest {
        message: message.to_string(),
        agent_type: agent_type.to_string(),
    };

    let res = client
        .post("http://127.0.0.1:8000/chat")
        .json(&req)
        .send()
        .await?;

    let json_res: MessageResponse = res.json().await?;
    Ok(json_res.response)
}

fn notify_user(title: &str, message: &str) {
    let _ = Command::new("notify-send")
        .arg(title)
        .arg(message)
        .spawn();
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = Client::new();
    
    // Check if Python server is online
    match client.get("http://127.0.0.1:8000/health").send().await {
        Ok(res) if res.status().is_success() => {
            println!("Friday Core (Rust) is online. Python backend connected.");
        }
        _ => {
            println!("Warning: Python backend (http://127.0.0.1:8000) seems unreachable. Ensure uvicorn is running.");
        }
    }

    println!("Type your message. Use '/btw <task>' to run a background agent. Type 'exit' to quit.\n");

    let mut reader = BufReader::new(stdin());
    let mut input = String::new();

    loop {
        print!("You: ");
        stdout().flush().await?;
        input.clear();

        let bytes_read = reader.read_line(&mut input).await?;
        if bytes_read == 0 {
            break;
        }

        let trimmed = input.trim();
        if trimmed.eq_ignore_ascii_case("exit") || trimmed.eq_ignore_ascii_case("quit") {
            break;
        }
        if trimmed.is_empty() {
            continue;
        }

        // Handle /btw background task
        if trimmed.starts_with("/btw ") {
            let prompt = trimmed.trim_start_matches("/btw ").to_string();
            let client_clone = client.clone();
            
            println!("Friday: [Background task started: {}]", prompt);
            
            // Spawn background task
            tokio::spawn(async move {
                match fetch_ai_response(&client_clone, &prompt, "system").await {
                    Ok(response) => {
                        let short_resp = if response.len() > 100 {
                            format!("{}...", &response[..97])
                        } else {
                            response.clone()
                        };
                        notify_user("Friday (/btw)", &short_resp);
                        println!("\n\r[Background Task Complete]\nFriday (/btw): {}\nYou: ", response);
                    }
                    Err(e) => {
                        let err_msg = format!("Background task failed: {}", e);
                        notify_user("Friday Error", &err_msg);
                        println!("\n\r[Background Error]\n{}\nYou: ", err_msg);
                    }
                }
            });
            
            continue; // Continue immediately to the next input prompt
        }

        // Foreground synchronous interaction
        println!("Friday is thinking...");
        match fetch_ai_response(&client, trimmed, "system").await {
            Ok(resp) => println!("Friday: {}", resp),
            Err(e) => println!("Error connecting to Friday Backend: {}", e),
        }
    }

    Ok(())
}
