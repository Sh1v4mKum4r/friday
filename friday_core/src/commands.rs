#[derive(Debug, PartialEq)]
pub enum Command {
    Chat(String),
    Background(String),
    Parallel(Vec<String>),
    Pipeline(Vec<String>),
    ForceProvider { provider: String, message: String },
    Search(String),
    MemoryList,
    MemoryForget(String),
    MemoryClear,
    Context,
    Reload,
    SessionResume,
    SessionNew,
    SessionList,
    Quit,
}

pub fn parse_input(input: &str) -> Command {
    let trimmed = input.trim();

    if trimmed.eq_ignore_ascii_case("exit") || trimmed.eq_ignore_ascii_case("quit") {
        return Command::Quit;
    }

    if let Some(rest) = trimmed.strip_prefix("/btw ") {
        return Command::Background(rest.trim().to_string());
    }

    if let Some(rest) = trimmed.strip_prefix("/parallel ") {
        let tasks: Vec<String> = rest
            .split("&&")
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect();
        return Command::Parallel(tasks);
    }

    if let Some(rest) = trimmed.strip_prefix("/pipe ") {
        let steps: Vec<String> = rest
            .split('|')
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect();
        return Command::Pipeline(steps);
    }

    if let Some(rest) = trimmed.strip_prefix("/search ") {
        return Command::Search(rest.trim().to_string());
    }

    // Force provider commands
    if let Some(rest) = trimmed.strip_prefix("/ollama ") {
        return Command::ForceProvider {
            provider: "ollama".to_string(),
            message: rest.trim().to_string(),
        };
    }

    if let Some(rest) = trimmed.strip_prefix("/gemini ") {
        return Command::ForceProvider {
            provider: "gemini".to_string(),
            message: rest.trim().to_string(),
        };
    }

    if let Some(rest) = trimmed.strip_prefix("/claude ") {
        return Command::ForceProvider {
            provider: "claude".to_string(),
            message: rest.trim().to_string(),
        };
    }

    if let Some(rest) = trimmed.strip_prefix("/openai ") {
        return Command::ForceProvider {
            provider: "openai".to_string(),
            message: rest.trim().to_string(),
        };
    }

    // Memory commands
    if trimmed.eq_ignore_ascii_case("/memory list") || trimmed.eq_ignore_ascii_case("/memory") {
        return Command::MemoryList;
    }

    if let Some(rest) = trimmed.strip_prefix("/memory forget ") {
        return Command::MemoryForget(rest.trim().to_string());
    }

    if trimmed.eq_ignore_ascii_case("/memory clear") {
        return Command::MemoryClear;
    }

    if trimmed.eq_ignore_ascii_case("/context") {
        return Command::Context;
    }

    if trimmed.eq_ignore_ascii_case("/reload") {
        return Command::Reload;
    }

    // Session commands
    if trimmed.eq_ignore_ascii_case("/session resume") {
        return Command::SessionResume;
    }

    if trimmed.eq_ignore_ascii_case("/session new") {
        return Command::SessionNew;
    }

    if trimmed.eq_ignore_ascii_case("/session list") || trimmed.eq_ignore_ascii_case("/session") {
        return Command::SessionList;
    }

    Command::Chat(trimmed.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_quit() {
        assert_eq!(parse_input("exit"), Command::Quit);
        assert_eq!(parse_input("quit"), Command::Quit);
        assert_eq!(parse_input("EXIT"), Command::Quit);
    }

    #[test]
    fn test_parse_background() {
        assert_eq!(
            parse_input("/btw summarize this"),
            Command::Background("summarize this".to_string())
        );
    }

    #[test]
    fn test_parse_parallel() {
        assert_eq!(
            parse_input("/parallel task1 && task2 && task3"),
            Command::Parallel(vec![
                "task1".to_string(),
                "task2".to_string(),
                "task3".to_string()
            ])
        );
    }

    #[test]
    fn test_parse_pipeline() {
        assert_eq!(
            parse_input("/pipe step1 | step2 | step3"),
            Command::Pipeline(vec![
                "step1".to_string(),
                "step2".to_string(),
                "step3".to_string()
            ])
        );
    }

    #[test]
    fn test_parse_force_provider() {
        assert_eq!(
            parse_input("/ollama hello there"),
            Command::ForceProvider {
                provider: "ollama".to_string(),
                message: "hello there".to_string()
            }
        );
    }

    #[test]
    fn test_parse_chat() {
        assert_eq!(
            parse_input("hello friday"),
            Command::Chat("hello friday".to_string())
        );
    }
}
