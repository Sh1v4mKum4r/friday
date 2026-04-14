"""btop-style settings overlay with Simple and Advanced modes."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Label

from friday_ai.tui.config import TUIConfig, VALID_THEMES, VALID_RENDER_MODES, VALID_SPACING


class SettingsField(Label):
    """A single settings field — label + value."""

    def __init__(
        self,
        key: str,
        label: str,
        value: str | int | bool,
        field_type: str = "enum",
        options: tuple = (),
        **kwargs,
    ) -> None:
        self.key = key
        self.field_label = label
        self.field_value = value
        self.field_type = field_type
        self.options = options
        display = self._format_display()
        super().__init__(display, classes="settings-field", **kwargs)

    def _format_display(self) -> str:
        if self.field_type == "toggle":
            indicator = "> ON" if self.field_value else "  OFF"
            return f"  {self.field_label:<24} {indicator}"
        elif self.field_type == "enum":
            return f"  {self.field_label:<24} < {self.field_value} >"
        elif self.field_type == "number":
            return f"  {self.field_label:<24}   {self.field_value}"
        elif self.field_type == "readonly":
            return f"  {self.field_label:<24}   {self.field_value}"
        return f"  {self.field_label:<24}   {self.field_value}"

    def cycle_value(self, direction: int = 1) -> None:
        if self.field_type == "toggle":
            self.field_value = not self.field_value
        elif self.field_type == "enum" and self.options:
            idx = list(self.options).index(self.field_value) if self.field_value in self.options else 0
            idx = (idx + direction) % len(self.options)
            self.field_value = self.options[idx]
        elif self.field_type == "number":
            self.field_value = max(1, self.field_value + direction)
        self.update(self._format_display())


class SettingsScreen(Screen):
    """Full-screen settings overlay."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("up,k", "move_up", "Up"),
        ("down,j", "move_down", "Down"),
        ("left,h", "cycle_left", "Left"),
        ("right,l", "cycle_right", "Right"),
        ("enter", "toggle_field", "Toggle"),
        ("a", "toggle_mode", "Advanced"),
        ("s", "save", "Save"),
        ("tab", "next_tab", "Tab"),
        ("shift+tab", "prev_tab", "Tab"),
    ]

    settings_mode: reactive[str] = reactive("simple")

    class SettingsSaved(Message):
        def __init__(self, config: TUIConfig) -> None:
            super().__init__()
            self.config = config

    def __init__(self, config: TUIConfig | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._config = config or TUIConfig()
        self._selected_idx = 0
        self._active_tab = 0
        self._modified = False

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-screen"):
            with Horizontal(id="settings-header"):
                yield Label("FRIDAY SETTINGS", classes="settings-label")
                mode_label = "[a] Advanced" if self.settings_mode == "simple" else "[a] Simple"
                yield Label(mode_label, id="mode-toggle-label", classes="settings-value")
            if self.settings_mode == "advanced":
                yield self._compose_tabs()
            yield VerticalScroll(id="settings-fields")
            with Horizontal(id="settings-footer"):
                yield Label("  j/k Navigate  h/l Change  Enter Toggle  s Save  Esc Close", classes="telemetry-label")
                modified = " [modified]" if self._modified else ""
                yield Label(f"  [Save] [Discard]{modified}", id="save-status", classes="settings-value")

    def _compose_tabs(self) -> Horizontal:
        tabs = ["GENERAL", "PROVIDER", "MCP", "TOOLS", "MEMORY", "IDENTITY", "APPEARANCE", "KEYBINDS"]
        container = Horizontal(id="settings-tabs")
        for i, tab in enumerate(tabs):
            cls = "settings-tab-active" if i == self._active_tab else "settings-tab-inactive"
            container.compose_add_child(Label(f" {tab} ", classes=cls, id=f"tab-{i}"))
        return container

    def on_mount(self) -> None:
        self._rebuild_fields()

    def _rebuild_fields(self) -> None:
        try:
            container = self.query_one("#settings-fields", VerticalScroll)
            container.remove_children()

            if self.settings_mode == "simple":
                fields = self._simple_fields()
            else:
                fields = self._advanced_fields()

            for i, field in enumerate(fields):
                if i == self._selected_idx:
                    field.add_class("-selected")
                container.mount(field)
        except Exception:
            pass

    def _simple_fields(self) -> list[SettingsField]:
        return [
            SettingsField("theme", "Theme", self._config.theme, "enum", VALID_THEMES),
            SettingsField("render_mode", "Render Mode", self._config.render_mode, "enum", VALID_RENDER_MODES),
            SettingsField("show_timestamps", "Show Timestamps", self._config.show_timestamps, "toggle"),
            SettingsField("show_provider_tags", "Show Provider Tags", self._config.show_provider_tags, "toggle"),
            SettingsField("show_latency", "Show Latency", self._config.show_latency, "toggle"),
            SettingsField("message_spacing", "Message Spacing", self._config.message_spacing, "enum", VALID_SPACING),
            SettingsField("ascii_logo", "ASCII Logo", self._config.ascii_logo, "toggle"),
            SettingsField("clock_in_header", "Clock in Header", self._config.clock_in_header, "toggle"),
            SettingsField("typewriter_speed", "Typewriter Speed", self._config.typewriter_speed, "number"),
            SettingsField("sidebar_width", "Sidebar Width", self._config.sidebar_width, "number"),
            SettingsField("telemetry_width", "Telemetry Width", self._config.telemetry_width, "number"),
            SettingsField("telemetry_refresh", "Telemetry Refresh (s)", self._config.telemetry_refresh, "number"),
        ]

    def _advanced_fields(self) -> list[SettingsField]:
        tab_builders = [
            self._general_fields, self._provider_fields, self._mcp_fields,
            self._tools_fields, self._memory_fields, self._identity_fields,
            self._appearance_fields, self._keybinds_fields,
        ]
        if self._active_tab < len(tab_builders):
            return tab_builders[self._active_tab]()
        return []

    def _general_fields(self) -> list[SettingsField]:
        return [
            SettingsField("render_mode", "Render Mode", self._config.render_mode, "enum", VALID_RENDER_MODES),
            SettingsField("typewriter_speed", "Typewriter Speed", self._config.typewriter_speed, "number"),
            SettingsField("telemetry_refresh", "Telemetry Refresh (s)", self._config.telemetry_refresh, "number"),
        ]

    def _provider_fields(self) -> list[SettingsField]:
        return [SettingsField("provider_note", "Configure via config.toml", "", "readonly")]

    def _mcp_fields(self) -> list[SettingsField]:
        return [SettingsField("mcp_note", "MCP servers configured externally", "", "readonly")]

    def _tools_fields(self) -> list[SettingsField]:
        return [SettingsField("tools_note", "Tools auto-discovered from plugins", "", "readonly")]

    def _memory_fields(self) -> list[SettingsField]:
        return [SettingsField("memory_note", "Use /memory commands in chat", "", "readonly")]

    def _identity_fields(self) -> list[SettingsField]:
        return [
            SettingsField("soul", "SOUL.md", "~/.config/friday/SOUL.md", "readonly"),
            SettingsField("user", "USER.md", "~/.config/friday/USER.md", "readonly"),
            SettingsField("agents", "AGENTS.md", "~/.config/friday/AGENTS.md", "readonly"),
            SettingsField("bootstrap", "BOOTSTRAP.md", "~/.config/friday/BOOTSTRAP.md", "readonly"),
        ]

    def _appearance_fields(self) -> list[SettingsField]:
        return [
            SettingsField("theme", "Theme", self._config.theme, "enum", VALID_THEMES),
            SettingsField("show_timestamps", "Show Timestamps", self._config.show_timestamps, "toggle"),
            SettingsField("show_provider_tags", "Provider Tags", self._config.show_provider_tags, "toggle"),
            SettingsField("show_latency", "Show Latency", self._config.show_latency, "toggle"),
            SettingsField("message_spacing", "Message Spacing", self._config.message_spacing, "enum", VALID_SPACING),
            SettingsField("ascii_logo", "ASCII Logo", self._config.ascii_logo, "toggle"),
            SettingsField("clock_in_header", "Clock in Header", self._config.clock_in_header, "toggle"),
            SettingsField("sidebar_width", "Sidebar Width", self._config.sidebar_width, "number"),
            SettingsField("telemetry_width", "Telemetry Width", self._config.telemetry_width, "number"),
        ]

    def _keybinds_fields(self) -> list[SettingsField]:
        return [
            SettingsField(k, k.replace("_", " ").title(), v, "readonly")
            for k, v in self._config.keybinds.items()
        ]

    def _get_fields(self) -> list[SettingsField]:
        try:
            return list(self.query(".settings-field").results(SettingsField))
        except Exception:
            return []

    def action_move_up(self) -> None:
        fields = self._get_fields()
        if fields and self._selected_idx > 0:
            fields[self._selected_idx].remove_class("-selected")
            self._selected_idx -= 1
            fields[self._selected_idx].add_class("-selected")
            fields[self._selected_idx].scroll_visible()

    def action_move_down(self) -> None:
        fields = self._get_fields()
        if fields and self._selected_idx < len(fields) - 1:
            fields[self._selected_idx].remove_class("-selected")
            self._selected_idx += 1
            fields[self._selected_idx].add_class("-selected")
            fields[self._selected_idx].scroll_visible()

    def action_cycle_right(self) -> None:
        fields = self._get_fields()
        if fields and self._selected_idx < len(fields):
            fields[self._selected_idx].cycle_value(1)
            self._mark_modified()

    def action_cycle_left(self) -> None:
        fields = self._get_fields()
        if fields and self._selected_idx < len(fields):
            fields[self._selected_idx].cycle_value(-1)
            self._mark_modified()

    def action_toggle_field(self) -> None:
        fields = self._get_fields()
        if fields and self._selected_idx < len(fields):
            field = fields[self._selected_idx]
            if field.field_type == "toggle":
                field.cycle_value()
                self._mark_modified()

    def toggle_advanced(self) -> None:
        self.settings_mode = "advanced" if self.settings_mode == "simple" else "simple"
        self._selected_idx = 0
        self._active_tab = 0

    def action_toggle_mode(self) -> None:
        self.toggle_advanced()
        self._rebuild_all()

    def action_next_tab(self) -> None:
        if self.settings_mode == "advanced":
            self._active_tab = (self._active_tab + 1) % 8
            self._selected_idx = 0
            self._rebuild_all()

    def action_prev_tab(self) -> None:
        if self.settings_mode == "advanced":
            self._active_tab = (self._active_tab - 1) % 8
            self._selected_idx = 0
            self._rebuild_all()

    def action_save(self) -> None:
        fields = self._get_fields()
        for field in fields:
            if hasattr(self._config, field.key):
                setattr(self._config, field.key, field.field_value)
        self._modified = False
        self.post_message(self.SettingsSaved(self._config))
        self.dismiss()

    def _mark_modified(self) -> None:
        self._modified = True
        try:
            label = self.query_one("#save-status", Label)
            label.update("  [Save] [Discard] [modified]")
        except Exception:
            pass

    def _rebuild_all(self) -> None:
        self.remove_children()
        for child in self.compose():
            self.mount(child)
        self._rebuild_fields()
