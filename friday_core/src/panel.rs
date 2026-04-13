use crate::de::DesktopEnvironment;
use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct PanelStatus {
    pub online: bool,
    pub active_workers: u32,
    pub provider: String,
}

impl Default for PanelStatus {
    fn default() -> Self {
        PanelStatus {
            online: false,
            active_workers: 0,
            provider: "none".to_string(),
        }
    }
}

/// Generate JSON output for a Waybar custom module.
/// Waybar expects: { "text": "...", "tooltip": "...", "class": "..." }
pub fn waybar_json(status: &PanelStatus) -> String {
    let icon = if status.online { "" } else { "" };
    let class = if status.online { "online" } else { "offline" };
    let tooltip = format!(
        "Friday AI\nStatus: {}\nProvider: {}\nWorkers: {}",
        if status.online { "online" } else { "offline" },
        status.provider,
        status.active_workers
    );

    serde_json::json!({
        "text": format!("{} Friday", icon),
        "tooltip": tooltip,
        "class": class,
        "alt": if status.online { "online" } else { "offline" }
    })
    .to_string()
}

/// Start the panel widget for the given DE (stub for now).
pub fn start_panel(_de: &DesktopEnvironment) {
    // TODO: launch DE-specific panel widget
    // For Waybar: write JSON to stdout in a loop
    // For Cosmic: use libcosmic panel applet
    println!("[Panel] Panel widget not yet implemented for this DE.");
}
