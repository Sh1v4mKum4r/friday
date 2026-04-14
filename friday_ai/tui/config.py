"""TUI-specific configuration."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

VALID_THEMES = ("obsidian", "neural", "prism", "techno")
VALID_RENDER_MODES = ("live_stream", "typewriter")
VALID_SPACING = ("compact", "normal", "relaxed")

DEFAULT_KEYBINDS: dict[str, str] = {
    "toggle_sidebar": "ctrl+b",
    "toggle_telemetry": "ctrl+t",
    "open_settings": "ctrl+s",
    "new_conversation": "ctrl+n",
    "search_conversations": "ctrl+p",
    "cycle_theme": "ctrl+shift+t",
    "toggle_render_mode": "ctrl+r",
    "copy_code": "y",
    "send_message": "enter",
    "newline": "shift+enter",
}


@dataclass
class TUIConfig:
    """Configuration for the Friday TUI."""

    theme: str = "obsidian"
    render_mode: str = "live_stream"
    typewriter_speed: int = 40
    settings_mode: str = "simple"
    show_timestamps: bool = True
    show_provider_tags: bool = True
    show_latency: bool = True
    message_spacing: str = "normal"
    code_theme: str = "monokai"
    sidebar_width: int = 30
    telemetry_width: int = 30
    telemetry_refresh: int = 30
    ascii_logo: bool = True
    clock_in_header: bool = True
    keybinds: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_KEYBINDS))


def load_tui_config(config_path: Path) -> TUIConfig:
    """Load TUI config from [tui] section of a TOML file."""
    config = TUIConfig()

    if not config_path.exists():
        return config

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    tui_data: dict[str, Any] = data.get("tui", {})
    keybinds_data: dict[str, str] = tui_data.pop("keybinds", {})

    for key, value in tui_data.items():
        if hasattr(config, key):
            setattr(config, key, value)

    config.keybinds.update(keybinds_data)

    return config


def save_tui_config(config: TUIConfig, config_path: Path) -> None:
    """Save TUI config to [tui] section of a TOML file, preserving other sections."""
    existing_content = ""
    if config_path.exists():
        existing_content = config_path.read_text()

    # Remove existing [tui] and [tui.keybinds] sections
    lines = existing_content.splitlines()
    filtered: list[str] = []
    in_tui_section = False
    for line in lines:
        stripped = line.strip()
        if stripped in ("[tui]", "[tui.keybinds]"):
            in_tui_section = True
            continue
        if in_tui_section and stripped.startswith("[") and stripped not in ("[tui]", "[tui.keybinds]"):
            in_tui_section = False
        if not in_tui_section:
            filtered.append(line)

    # Build new [tui] section
    tui_lines = ["\n[tui]"]
    for key in (
        "theme", "render_mode", "typewriter_speed", "settings_mode",
        "show_timestamps", "show_provider_tags", "show_latency",
        "message_spacing", "code_theme", "sidebar_width", "telemetry_width",
        "telemetry_refresh", "ascii_logo", "clock_in_header",
    ):
        value = getattr(config, key)
        if isinstance(value, bool):
            tui_lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, int):
            tui_lines.append(f"{key} = {value}")
        else:
            tui_lines.append(f'{key} = "{value}"')

    tui_lines.append("\n[tui.keybinds]")
    for key, value in config.keybinds.items():
        tui_lines.append(f'{key} = "{value}"')

    output = "\n".join(filtered).rstrip() + "\n" + "\n".join(tui_lines) + "\n"
    config_path.write_text(output)
