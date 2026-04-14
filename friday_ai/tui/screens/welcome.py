"""Welcome screen shown when no conversation history exists."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Grid, Vertical
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Label, Static

FRIDAY_LOGO = r"""
 ███████╗
 ██╔════╝
 █████╗
 ██╔══╝
 ██║
 ╚═╝
"""

QUICK_ACTIONS = [
    ("Draft an email", "Compose professional replies for clients or colleagues."),
    ("Explain code", "Break down complex logic or debug cryptic error messages."),
    ("Analyze data", "Extract key information for insights and trend visualization."),
    ("Summarize text", "Condense lengthy articles or meeting notes."),
    ("Brainstorm", "Generate fresh ideas for marketing or creative projects."),
    ("Run command", "Execute shell commands and system automation."),
]


class QuickAction(Static):
    """A clickable quick action card."""

    class Selected(Message):
        def __init__(self, prompt: str) -> None:
            super().__init__()
            self.prompt = prompt

    def __init__(self, title: str, description: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.title = title
        self.description = description
        self.add_class("quick-action")

    def render(self) -> str:
        return f"{self.title}\n{self.description[:40]}"

    def on_click(self) -> None:
        self.post_message(self.Selected(self.title))


class WelcomeScreen(Screen):
    """Empty state with logo and quick action cards."""

    class ActionSelected(Message):
        def __init__(self, prompt: str) -> None:
            super().__init__()
            self.prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="welcome"):
            yield Static(FRIDAY_LOGO, id="welcome-logo")
            yield Label("What can I help with?", id="welcome-title")
            with Grid(id="quick-action-grid"):
                for title, desc in QUICK_ACTIONS:
                    yield QuickAction(title, desc)

    def on_quick_action_selected(self, event: QuickAction.Selected) -> None:
        self.post_message(self.ActionSelected(event.prompt))
