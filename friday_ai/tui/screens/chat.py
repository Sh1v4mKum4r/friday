"""Main chat screen — messages, input, overlays."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Center, ItemGrid, Vertical, VerticalScroll
from textual.screen import Screen
from textual.message import Message
from textual.widgets import Footer, Label, Static

from friday_ai.tui.widgets.input_bar import InputBar
from friday_ai.tui.widgets.message import MessageWidget
from friday_ai.tui.widgets.mode_bar import ModeBar
from friday_ai.tui.widgets.sidebar import Sidebar
from friday_ai.tui.widgets.telemetry import TelemetryPanel

FRIDAY_LOGO = """\
███████╗██████╗ ██╗██████╗  █████╗ ██╗   ██╗
██╔════╝██╔══██╗██║██╔══██╗██╔══██╗╚██╗ ██╔╝
█████╗  ██████╔╝██║██║  ██║███████║ ╚████╔╝
██╔══╝  ██╔══██╗██║██║  ██║██╔══██║  ╚██╔╝
██║     ██║  ██║██║██████╔╝██║  ██║   ██║
╚═╝     ╚═╝  ╚═╝╚═╝╚═════╝ ╚═╝  ╚═╝   ╚═╝"""

QUICK_ACTIONS = [
    ("Execute Command", "Run shell commands and system automation"),
    ("Explain Code", "Break down logic or debug error messages"),
    ("Analyze Data", "Extract insights and trends from data"),
    ("Summarize Text", "Condense articles or meeting notes"),
    ("Brainstorm", "Generate ideas for any project"),
    ("Search Web", "Find current info, news, and prices"),
]


class QuickActionCard(Static, can_focus=True):
    """Focusable quick-action card in the welcome grid."""

    def __init__(self, title: str, description: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.action_title = title
        self.action_desc = description

    def render(self) -> str:
        return f"  {self.action_title}\n  {self.action_desc[:38]}"

    def on_key(self, event) -> None:
        if event.key == "enter":
            self.screen.post_message(ChatScreen.QuickActionChosen(self.action_title))


class WelcomePanel(Vertical):
    """Centered welcome content with logo and quick-action grid."""

    def compose(self) -> ComposeResult:
        yield Static(FRIDAY_LOGO, id="welcome-logo")
        yield Label("What can I help with?", id="welcome-subtitle")
        with ItemGrid(id="quick-action-grid", min_column_width=36):
            for title, desc in QUICK_ACTIONS:
                yield QuickActionCard(title, desc, classes="quick-action")


class ChatScreen(Screen):
    """The main chat interface."""

    BINDINGS = [
        ("ctrl+b", "toggle_sidebar", "History"),
        ("ctrl+t", "toggle_telemetry", "System"),
        ("ctrl+s", "app.open_settings", "Settings"),
        ("ctrl+n", "app.new_conversation", "New Chat"),
        ("ctrl+1", "mode_chat", "Chat"),
        ("ctrl+2", "mode_command", "Command"),
        ("ctrl+3", "mode_search", "Search"),
        ("i", "focus_input", "Input"),
        ("q", "app.quit", "Quit"),
    ]

    class QuickActionChosen(Message):
        """Emitted when a quick action card is selected."""

        def __init__(self, prompt: str) -> None:
            super().__init__()
            self.prompt = prompt

    def compose(self) -> ComposeResult:
        # Overlay panels (float on separate layer)
        yield Sidebar(classes="hidden")
        yield TelemetryPanel(classes="hidden")
        # Bottom-docked elements (first = outermost bottom)
        yield Footer()
        yield InputBar()
        yield ModeBar()
        # Main content area — welcome panel shown initially, messages hidden
        yield WelcomePanel(id="welcome-panel")
        yield VerticalScroll(id="messages", classes="hidden")

    def add_message(
        self,
        content: str,
        role: str = "user",
        provider: str = "",
        latency: float = 0.0,
    ) -> MessageWidget:
        """Add a message to the chat area."""
        # Switch from welcome to messages on first message
        try:
            welcome = self.query_one("#welcome-panel", WelcomePanel)
            if not welcome.has_class("hidden"):
                welcome.add_class("hidden")
                messages = self.query_one("#messages", VerticalScroll)
                messages.remove_class("hidden")
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
