use crate::de::DesktopEnvironment;
use std::process::{Command, Stdio};

/// Launch a dmenu-style prompt and return the user's input, if any.
pub fn launch_prompt(de: &DesktopEnvironment) -> Option<String> {
    match de {
        DesktopEnvironment::Hyprland => {
            try_rofi().or_else(|| try_wofi())
        }
        DesktopEnvironment::Cosmic => {
            // COSMIC doesn't have a native dmenu equivalent yet; fall back to rofi
            try_rofi().or_else(|| try_wofi())
        }
        DesktopEnvironment::Unknown(_) => {
            try_rofi().or_else(|| try_wofi())
        }
    }
}

fn try_rofi() -> Option<String> {
    let output = Command::new("rofi")
        .args(["-dmenu", "-p", "Friday: ", "-theme-str", "window {width: 600px;}"])
        .stdin(Stdio::null())
        .output()
        .ok()?;

    if output.status.success() {
        let text = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if text.is_empty() { None } else { Some(text) }
    } else {
        None
    }
}

fn try_wofi() -> Option<String> {
    let output = Command::new("wofi")
        .args(["--dmenu", "--prompt", "Friday: "])
        .stdin(Stdio::null())
        .output()
        .ok()?;

    if output.status.success() {
        let text = String::from_utf8_lossy(&output.stdout).trim().to_string();
        if text.is_empty() { None } else { Some(text) }
    } else {
        None
    }
}
