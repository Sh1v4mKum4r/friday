"""Friday TUI — main Textual application."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from textual.app import App
from textual.reactive import reactive

from friday_ai.tui.client import FridayTUIClient
from friday_ai.tui.config import TUIConfig, load_tui_config, save_tui_config, VALID_THEMES
from friday_ai.tui.screens.chat import ChatScreen
from friday_ai.tui.screens.settings import SettingsScreen
from friday_ai.tui.screens.welcome import WelcomeScreen
from friday_ai.tui.widgets.input_bar import InputBar

THEME_DIR = Path(__file__).parent / "themes"


class FridayApp(App):
    """Friday AI Terminal Interface."""

    TITLE = "Friday"
    SUB_TITLE = "AI Assistant"

    BINDINGS = [
        ("ctrl+s", "open_settings", "Settings"),
        ("ctrl+n", "new_conversation", "New Chat"),
        ("ctrl+shift+t", "cycle_theme", "Theme"),
        ("ctrl+r", "toggle_render_mode", "Render"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 65535,
        theme: str | None = None,
        no_connect: bool = False,
        session: str | None = None,
        **kwargs,
    ) -> None:
        self._tui_config = self._load_config()
        initial_theme = theme or self._tui_config.theme
        css_path = THEME_DIR / f"{initial_theme}.tcss"
        if not css_path.exists():
            css_path = THEME_DIR / "obsidian.tcss"
            initial_theme = "obsidian"

        super().__init__(css_path=css_path, **kwargs)

        # _friday_theme tracks our custom theme name independently of Textual's
        # built-in theme system (which uses self.theme / self.current_theme).
        self._friday_theme: str = initial_theme
        self._host = host
        self._port = port
        self._no_connect = no_connect
        self._session_file = session
        self._client: FridayTUIClient | None = None
        self._messages: list[dict[str, Any]] = []
        self._render_mode = self._tui_config.render_mode

    def _load_config(self) -> TUIConfig:
        config_path = Path.home() / ".config" / "friday" / "config.toml"
        return load_tui_config(config_path)

    async def on_mount(self) -> None:
        if not self._no_connect:
            self._client = FridayTUIClient(host=self._host, port=self._port)
            health = await self._client.health()
            if health and self._session_file:
                await self._client.session_load()

        self.push_screen(ChatScreen())

    async def on_unmount(self) -> None:
        if self._client:
            await self._client.close()

    # --- Actions ---

    def action_open_settings(self) -> None:
        self.push_screen(SettingsScreen(config=self._tui_config))

    def action_new_conversation(self) -> None:
        self._messages.clear()
        if isinstance(self.screen, ChatScreen):
            try:
                from textual.containers import VerticalScroll
                messages = self.screen.query_one("#messages", VerticalScroll)
                messages.remove_children()
            except Exception:
                pass

    def action_cycle_theme(self) -> None:
        themes = list(VALID_THEMES)
        idx = themes.index(self._friday_theme) if self._friday_theme in themes else 0
        self._friday_theme = themes[(idx + 1) % len(themes)]

    def action_toggle_render_mode(self) -> None:
        self._render_mode = "typewriter" if self._render_mode == "live_stream" else "live_stream"
        self.notify(f"Render: {self._render_mode.replace('_', ' ').title()}")

    # --- Message Handling ---

    async def on_input_bar_submitted(self, event: InputBar.Submitted) -> None:
        if not isinstance(self.screen, ChatScreen):
            return

        chat_screen = self.screen
        value = event.value
        mode = event.mode

        if mode == "chat":
            await self._handle_chat(chat_screen, value)
        elif mode == "command":
            await self._handle_command(chat_screen, value)
        elif mode == "search":
            await self._handle_search(chat_screen, value)

    async def _handle_chat(self, screen: ChatScreen, message: str) -> None:
        screen.add_message(message, role="user")
        screen.query_one(InputBar).set_thinking(True)

        if not self._client:
            screen.add_message("Not connected to Friday backend.", role="assistant", provider="error")
            screen.query_one(InputBar).set_thinking(False)
            return

        if self._render_mode == "live_stream":
            msg_widget = screen.add_message("", role="assistant", provider="...")
            try:
                async for chunk in self._client.chat_stream(message):
                    if chunk.get("error"):
                        msg_widget.content = f"Error: {chunk['error']}"
                        break
                    if not chunk.get("done"):
                        msg_widget.append_token(chunk.get("token", ""))
                    else:
                        msg_widget.provider = chunk.get("provider", "unknown")
                        msg_widget.latency = chunk.get("latency", 0.0)
                        self._update_telemetry(chunk.get("provider", ""), chunk.get("latency", 0.0))
            except Exception as e:
                msg_widget.content = f"Stream error: {e}"
        else:
            result = await self._client.chat(message)
            if result:
                response = result.get("response", "No response")
                provider = result.get("provider", "unknown")
                msg_widget = screen.add_message("", role="assistant", provider=provider)
                speed = self._tui_config.typewriter_speed
                for char in response:
                    msg_widget.append_token(char)
                    await asyncio.sleep(1.0 / speed)
            else:
                screen.add_message("Failed to get response.", role="assistant", provider="error")

        screen.query_one(InputBar).set_thinking(False)

    async def _handle_command(self, screen: ChatScreen, value: str) -> None:
        if value.startswith("!"):
            shell_cmd = value[1:].strip()
            screen.add_message(f"! {shell_cmd}", role="user")
            if self._client:
                result = await self._client.chat(f"Run this shell command: {shell_cmd}")
                if result:
                    screen.add_message(result.get("response", ""), role="assistant", provider=result.get("provider", ""))
        elif value.startswith("/"):
            parts = value[1:].split(maxsplit=1)
            cmd = parts[0] if parts else ""
            await self._run_friday_command(screen, cmd, parts[1] if len(parts) > 1 else "")
        else:
            screen.add_message(value, role="user")
            screen.add_message("Use ! for shell commands or / for Friday commands.", role="assistant", provider="system")

    async def _run_friday_command(self, screen: ChatScreen, cmd: str, args: str) -> None:
        screen.add_message(f"/{cmd} {args}".strip(), role="user")

        if not self._client:
            screen.add_message("Not connected.", role="assistant", provider="error")
            return

        handlers = {
            "reload": lambda: self._client.reload(),
            "health": lambda: self._client.health(),
            "memory": lambda: self._client.memory_list(),
            "forget": lambda: self._client.memory_forget(args),
            "clear": lambda: self._client.memory_clear(),
            "save": lambda: self._client.session_save(),
            "load": lambda: self._client.session_load(),
            "mcp": lambda: self._client.mcp_status(),
            "reconnect": lambda: self._client.mcp_reconnect(),
            "context": lambda: self._client.context(),
        }

        handler = handlers.get(cmd)
        if handler:
            result = await handler()
            screen.add_message(
                f"```json\n{json.dumps(result, indent=2)}\n```" if result else "Command failed.",
                role="assistant",
                provider="system",
            )
        else:
            screen.add_message(f"Unknown command: /{cmd}", role="assistant", provider="system")

    async def _handle_search(self, screen: ChatScreen, query: str) -> None:
        screen.add_message(f"Searching: {query}", role="user")
        if self._client:
            result = await self._client.memory_list()
            if result:
                entries = result.get("entries", [])
                matches = [e for e in entries if query.lower() in e.lower()]
                if matches:
                    screen.add_message("\n".join(f"- {m}" for m in matches), role="assistant", provider="search")
                else:
                    screen.add_message("No matches found.", role="assistant", provider="search")

    def _update_telemetry(self, provider: str, latency: float) -> None:
        if isinstance(self.screen, ChatScreen):
            try:
                from friday_ai.tui.widgets.telemetry import TelemetryPanel
                panel = self.screen.query_one(TelemetryPanel)
                panel.update_last_response(provider, "", latency)
            except Exception:
                pass

    # --- Settings Callbacks ---

    def on_settings_screen_settings_saved(self, event: SettingsScreen.SettingsSaved) -> None:
        self._tui_config = event.config
        config_path = Path.home() / ".config" / "friday" / "config.toml"
        save_tui_config(self._tui_config, config_path)

        if self._tui_config.theme != self._friday_theme:
            self._friday_theme = self._tui_config.theme

        self._render_mode = self._tui_config.render_mode

        if self._client:
            asyncio.create_task(self._client.reload())

    # --- Welcome Screen Callback ---

    def on_welcome_screen_action_selected(self, event: WelcomeScreen.ActionSelected) -> None:
        self.pop_screen()
        chat = ChatScreen()
        self.push_screen(chat)
        self.call_after_refresh(lambda: asyncio.create_task(self._handle_chat(chat, event.prompt)))
