mod client;
mod commands;
mod config;
mod de;
mod launcher;
mod panel;
mod task_manager;

use clap::Parser;
use client::FridayClient;
use commands::{parse_input, Command};
use config::load_config;
use de::detect_de;
use tokio::io::{stdin, stdout, AsyncBufReadExt, AsyncWriteExt, BufReader};

#[derive(Parser, Debug)]
#[command(name = "friday", about = "Friday AI — Rust CLI frontend")]
struct Args {
    /// Run as background daemon
    #[arg(long, default_value_t = false)]
    daemon: bool,

    /// CLI-only mode (no panel/launcher)
    #[arg(long, default_value_t = false)]
    cli_only: bool,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args = Args::parse();
    let cfg = load_config();

    let host = cfg.server.host.as_deref().unwrap_or("127.0.0.1");
    let port = cfg.server.port.unwrap_or(65535);

    let de_override = cfg.de.override_de.as_deref().unwrap_or("");
    let de = detect_de(de_override);

    let client = FridayClient::new(host, port);

    // Health check on startup
    match client.health().await {
        Ok(h) => {
            println!(
                "Friday online — provider: {}, workers: {}",
                h.provider, h.active_workers
            );
        }
        Err(_) => {
            eprintln!(
                "Warning: Python backend at {}:{} unreachable. Some features may not work.",
                host, port
            );
        }
    }

    if args.daemon {
        println!("[Daemon mode] Friday running as daemon. DE: {}", de::de_display_name(&de));
        // In daemon mode, just keep alive (future: IPC socket, panel updates, etc.)
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(30)).await;
        }
    }

    println!(
        "Friday AI — DE: {} | Backend: {}:{} | Type 'exit' or 'quit' to quit.",
        de::de_display_name(&de),
        host,
        port
    );
    println!("Commands: /btw <task>  /parallel t1 && t2  /pipe s1 | s2  /ollama /gemini /claude /openai  /memory list|forget|clear  /context  /reload  /session resume|new|list");
    println!();

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
        if trimmed.is_empty() {
            continue;
        }

        let cmd = parse_input(trimmed);

        match cmd {
            Command::Quit => {
                println!("Goodbye.");
                break;
            }

            Command::Chat(msg) => {
                println!("Friday is thinking...");
                match client.chat(&msg, None).await {
                    Ok(resp) => println!("Friday [{}]: {}", resp.provider, resp.response),
                    Err(e) => eprintln!("Error: {}", e),
                }
            }

            Command::Background(task) => {
                task_manager::run_background(&client, task).await;
            }

            Command::Parallel(tasks) => {
                task_manager::run_parallel(&client, tasks).await;
            }

            Command::Pipeline(steps) => {
                task_manager::run_pipeline(&client, steps).await;
            }

            Command::ForceProvider { provider, message } => {
                println!("Friday is thinking... [forced: {}]", provider);
                match client.chat(&message, Some(&provider)).await {
                    Ok(resp) => println!("Friday [{}]: {}", resp.provider, resp.response),
                    Err(e) => eprintln!("Error: {}", e),
                }
            }

            Command::Search(query) => {
                // Search is routed as a chat with context hint
                let msg = format!("[search] {}", query);
                println!("Friday is searching...");
                match client.chat(&msg, None).await {
                    Ok(resp) => println!("Friday [{}]: {}", resp.provider, resp.response),
                    Err(e) => eprintln!("Error: {}", e),
                }
            }

            Command::MemoryList => {
                println!("[Memory] Listing memories...");
                match client.get_context().await {
                    Ok(ctx) => println!("{}", ctx),
                    Err(e) => eprintln!("Error fetching memory: {}", e),
                }
            }

            Command::MemoryForget(key) => {
                println!("[Memory] Forgetting: {} (not yet implemented in backend)", key);
            }

            Command::MemoryClear => {
                println!("[Memory] Clear all memories (not yet implemented in backend)");
            }

            Command::Context => {
                println!("[Context] Fetching context...");
                match client.get_context().await {
                    Ok(ctx) => println!("{}", ctx),
                    Err(e) => eprintln!("Error fetching context: {}", e),
                }
            }

            Command::Reload => {
                println!("[Reload] Reloading tools...");
                match client.reload_tools().await {
                    Ok(val) => println!("Reload result: {}", val),
                    Err(e) => eprintln!("Error reloading tools: {}", e),
                }
            }

            Command::SessionResume => {
                println!("[Session] Resume session (not yet implemented)");
            }

            Command::SessionNew => {
                println!("[Session] New session (not yet implemented)");
            }

            Command::SessionList => {
                println!("[Session] Session list (not yet implemented)");
            }
        }

        println!();
    }

    Ok(())
}
