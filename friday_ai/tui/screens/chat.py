"""Main chat screen — messages, input, overlays."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Label, Static

from friday_ai.tui.widgets.input_bar import InputBar
from friday_ai.tui.widgets.message import MessageWidget
from friday_ai.tui.widgets.mode_bar import ModeBar
from friday_ai.tui.widgets.sidebar import Sidebar
from friday_ai.tui.widgets.telemetry import TelemetryPanel

FRIDAY_LOGO = """\
 ███████╗ ██████╗  ██╗ ██████╗   █████╗  ██╗   ██╗
 ██╔════╝ ██╔══██╗ ██║ ██╔══██╗ ██╔══██╗ ╚██╗ ██╔╝
 █████╗   ██████╔╝ ██║ ██║  ██║ ███████║  ╚████╔╝
 ██╔══╝   ██╔══██╗ ██║ ██║  ██║ ██╔══██║   ╚██╔╝
 ██║      ██║  ██║ ██║ ██████╔╝ ██║  ██║    ██║
 ╚═╝      ╚═╝  ╚═╝ ╚═╝ ╚═════╝  ╚═╝  ╚═╝    ╚═╝\
"""


class WelcomeBanner(Static):
    """Centered welcome content shown when chat is empty."""

    def render(self) -> str:
        return (
            f"{FRIDAY_LOGO}\n\n"
            "          What can I help with?\n\n"
            "    Type a message below to get started.\n"
            "    Use Ctrl+B for history, Ctrl+T for telemetry.\n"
        )


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
        yield TelemetryPanel(classes="hidden")
        with Vertical(id="chat-body"):
            yield VerticalScroll(id="messages")
            yield ModeBar()
            yield InputBar()

    def on_mount(self) -> None:
        """Show welcome banner in the empty messages area."""
        messages = self.query_one("#messages", VerticalScroll)
        messages.mount(WelcomeBanner(id="welcome-banner"))

    def add_message(
        self,
        content: str,
        role: str = "user",
        provider: str = "",
        latency: float = 0.0,
    ) -> MessageWidget:
        """Add a message to the chat area."""
        # Remove welcome banner on first message
        try:
            banner = self.query_one("#welcome-banner", WelcomeBanner)
            banner.remove()
        except Exception:
            pass

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
