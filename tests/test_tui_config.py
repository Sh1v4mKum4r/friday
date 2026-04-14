"""Tests for TUI configuration."""

import tempfile
from pathlib import Path

from friday_ai.tui.config import TUIConfig, load_tui_config, save_tui_config


class TestTUIConfig:
    def test_default_values(self):
        config = TUIConfig()
        assert config.theme == "obsidian"
        assert config.render_mode == "live_stream"
        assert config.typewriter_speed == 40
        assert config.settings_mode == "simple"
        assert config.show_timestamps is True
        assert config.show_provider_tags is True
        assert config.show_latency is True
        assert config.message_spacing == "normal"
        assert config.code_theme == "monokai"
        assert config.sidebar_width == 30
        assert config.telemetry_width == 30
        assert config.telemetry_refresh == 30
        assert config.ascii_logo is True
        assert config.clock_in_header is True

    def test_default_keybinds(self):
        config = TUIConfig()
        assert config.keybinds["toggle_sidebar"] == "ctrl+b"
        assert config.keybinds["toggle_telemetry"] == "ctrl+t"
        assert config.keybinds["open_settings"] == "ctrl+s"
        assert config.keybinds["new_conversation"] == "ctrl+n"
        assert config.keybinds["search_conversations"] == "ctrl+p"
        assert config.keybinds["cycle_theme"] == "ctrl+shift+t"
        assert config.keybinds["toggle_render_mode"] == "ctrl+r"
        assert config.keybinds["copy_code"] == "y"
        assert config.keybinds["send_message"] == "enter"
        assert config.keybinds["newline"] == "shift+enter"

    def test_load_from_toml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(
                "[tui]\n"
                'theme = "neural"\n'
                'render_mode = "typewriter"\n'
                "typewriter_speed = 60\n"
                'message_spacing = "compact"\n'
                "\n"
                "[tui.keybinds]\n"
                'toggle_sidebar = "ctrl+l"\n'
            )
            f.flush()
            config = load_tui_config(Path(f.name))
            assert config.theme == "neural"
            assert config.render_mode == "typewriter"
            assert config.typewriter_speed == 60
            assert config.message_spacing == "compact"
            assert config.keybinds["toggle_sidebar"] == "ctrl+l"
            # Non-overridden keybinds keep defaults
            assert config.keybinds["toggle_telemetry"] == "ctrl+t"

    def test_load_missing_file_returns_defaults(self):
        config = load_tui_config(Path("/nonexistent/config.toml"))
        assert config.theme == "obsidian"

    def test_save_and_reload(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("[server]\nport = 65535\n")
            f.flush()
            path = Path(f.name)

        config = TUIConfig(theme="prism", typewriter_speed=80)
        save_tui_config(config, path)

        reloaded = load_tui_config(path)
        assert reloaded.theme == "prism"
        assert reloaded.typewriter_speed == 80
        # Existing sections preserved
        content = path.read_text()
        assert "port = 65535" in content

    def test_valid_themes(self):
        config = TUIConfig()
        assert config.theme in ("obsidian", "neural", "prism", "techno")

    def test_valid_render_modes(self):
        config = TUIConfig()
        assert config.render_mode in ("live_stream", "typewriter")

    def test_valid_message_spacing(self):
        config = TUIConfig()
        assert config.message_spacing in ("compact", "normal", "relaxed")
