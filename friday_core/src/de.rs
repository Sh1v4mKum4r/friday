use std::process::Command;

#[derive(Debug, Clone, PartialEq)]
pub enum DesktopEnvironment {
    Cosmic,
    Hyprland,
    Unknown(String),
}

pub fn detect_de(config_override: &str) -> DesktopEnvironment {
    // 1. Check config override first
    if !config_override.is_empty() {
        return parse_de_string(config_override);
    }

    // 2. Check $XDG_CURRENT_DESKTOP
    if let Ok(val) = std::env::var("XDG_CURRENT_DESKTOP") {
        if !val.is_empty() {
            return parse_de_string(&val);
        }
    }

    // 3. pgrep fallback
    if pgrep_running("hyprland") {
        return DesktopEnvironment::Hyprland;
    }

    if pgrep_running("cosmic-session") || pgrep_running("cosmic-comp") {
        return DesktopEnvironment::Cosmic;
    }

    DesktopEnvironment::Unknown("unknown".to_string())
}

fn parse_de_string(s: &str) -> DesktopEnvironment {
    match s.to_lowercase().as_str() {
        "hyprland" => DesktopEnvironment::Hyprland,
        "cosmic" => DesktopEnvironment::Cosmic,
        other => DesktopEnvironment::Unknown(other.to_string()),
    }
}

fn pgrep_running(process: &str) -> bool {
    Command::new("pgrep")
        .arg("-x")
        .arg(process)
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

pub fn de_display_name(de: &DesktopEnvironment) -> &str {
    match de {
        DesktopEnvironment::Cosmic => "COSMIC",
        DesktopEnvironment::Hyprland => "Hyprland",
        DesktopEnvironment::Unknown(s) => s.as_str(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detect_override_hyprland() {
        let de = detect_de("hyprland");
        assert_eq!(de, DesktopEnvironment::Hyprland);
    }

    #[test]
    fn test_detect_override_cosmic() {
        let de = detect_de("cosmic");
        assert_eq!(de, DesktopEnvironment::Cosmic);
    }

    #[test]
    fn test_display_names() {
        assert_eq!(de_display_name(&DesktopEnvironment::Cosmic), "COSMIC");
        assert_eq!(de_display_name(&DesktopEnvironment::Hyprland), "Hyprland");
    }
}
