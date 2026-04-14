"""Main chat screen — messages, input, overlays."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import Screen

from friday_ai.tui.widgets.input_bar import InputBar
from friday_ai.tui.widgets.message import MessageWidget
from friday_ai.tui.widgets.mode_bar import ModeBar
from friday_ai.tui.widgets.sidebar import Sidebar
from friday_ai.tui.widgets.telemetry import TelemetryPanel


class ChatScreen(Screen):
    """The main chat interface."""

    BINDINGS = [
        ("ctrl+b", "toggle_sidebar", "Sidebar"),
        ("ctrl+t", "toggle_telemetry", "Telemetry"),
        ("ctrl+1", "mode_chat", "Chat"),
        ("ctrl+2", "mode_command", "Command"),
        ("ctrl+3", "mode_search", "Search"),
        ("i", "focus_input", "Input"),
    ]

    def compose(self) -> ComposeResult:
        yield Sidebar(classes="hidden")
        yield VerticalScroll(id="messages")
        yield ModeBar()
        yield InputBar()
        yield TelemetryPanel(classes="hidden")

    def add_message(
        self,
        content: str,
        role: str = "user",
        provider: str = "",
        latency: float = 0.0,
    ) -> MessageWidget:
        timestamp = datetime.now().strftime("%H:%M")
        msg = MessageWidget(
            content=content,
            role=role,
            provider=provider,
            latency=latency,
            timestamp=timestamp,
        )
        messages = self.query_one("#messages", VerticalScroll)
        messages.mount(msg)
        msg.scroll_visible()
        return msg

    def action_toggle_sidebar(self) -> None:
        sidebar = self.query_one(Sidebar)
        sidebar.toggle_class("hidden")
        if self.app.size.width < 80 and not sidebar.has_class("hidden"):
            self.query_one(TelemetryPanel).add_class("hidden")

    def action_toggle_telemetry(self) -> None:
        panel = self.query_one(TelemetryPanel)
        panel.toggle_class("hidden")
        if self.app.size.width < 80 and not panel.has_class("hidden"):
            self.query_one(Sidebar).add_class("hidden")

    def action_mode_chat(self) -> None:
        self.query_one(ModeBar).set_mode("chat")
        self.query_one(InputBar).set_mode("chat")

    def action_mode_command(self) -> None:
        self.query_one(ModeBar).set_mode("command")
        self.query_one(InputBar).set_mode("command")

    def action_mode_search(self) -> None:
        self.query_one(ModeBar).set_mode("search")
        self.query_one(InputBar).set_mode("search")

    def action_focus_input(self) -> None:
        try:
            from textual.widgets import Input
            self.query_one("#chat-input", Input).focus()
        except Exception:
            pass
