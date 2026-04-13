use crate::client::FridayClient;
use std::process::Command;

pub fn notify(message: &str) {
    let _ = Command::new("notify-send")
        .arg("Friday")
        .arg(message)
        .spawn();
}

pub async fn run_background(client: &FridayClient, task: String) {
    println!("[Background task started]");

    let host = client.host().to_string();
    let port = client.port();

    tokio::spawn(async move {
        let bg_client = FridayClient::new(host, port);
        match bg_client.chat(&task, None).await {
            Ok(resp) => {
                let result = resp.response;
                notify(&format!("Background task done: {}", &result.chars().take(100).collect::<String>()));
                println!("\n[Background Task Complete]\nFriday: {}", result);
            }
            Err(e) => {
                let err_msg = format!("Background task failed: {}", e);
                notify(&err_msg);
                println!("\n[Background Error] {}", err_msg);
            }
        }
    });
}

pub async fn run_parallel(client: &FridayClient, tasks: Vec<String>) {
    println!("[Running {} tasks in parallel...]", tasks.len());

    let host = client.host().to_string();
    let port = client.port();

    let handles: Vec<_> = tasks
        .into_iter()
        .enumerate()
        .map(|(i, task)| {
            let h = host.clone();
            let p = port;
            tokio::spawn(async move {
                let c = FridayClient::new(h, p);
                match c.chat(&task, None).await {
                    Ok(resp) => format!("[Task {}] {}", i + 1, resp.response),
                    Err(e) => format!("[Task {} ERROR] {}", i + 1, e),
                }
            })
        })
        .collect();

    for handle in handles {
        match handle.await {
            Ok(result) => println!("{}", result),
            Err(e) => println!("[Task panicked] {:?}", e),
        }
    }
}

pub async fn run_pipeline(client: &FridayClient, tasks: Vec<String>) {
    println!("[Running pipeline with {} steps...]", tasks.len());

    let mut context = String::new();

    for (i, step) in tasks.iter().enumerate() {
        let message = if context.is_empty() {
            step.clone()
        } else {
            format!("{}\n\nPrevious output:\n{}", step, context)
        };

        println!("[Pipeline step {}/{}]: {}", i + 1, tasks.len(), step);

        match client.chat(&message, None).await {
            Ok(resp) => {
                context = resp.response.clone();
                println!("  -> {}", resp.response);
            }
            Err(e) => {
                println!("[Pipeline step {} ERROR] {}", i + 1, e);
                break;
            }
        }
    }

    if !context.is_empty() {
        println!("\n[Pipeline Final Output]\n{}", context);
    }
}
