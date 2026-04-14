"""Chat message widget for user and assistant messages."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Markdown


class MessageWidget(Widget):
    """A single chat message — user or assistant."""

    content: reactive[str] = reactive("", layout=True)

    def __init__(
        self,
        content: str = "",
        role: str = "user",
        provider: str = "",
        latency: float = 0.0,
        timestamp: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.role = role
        self.provider = provider
        self.latency = latency
        self.timestamp = timestamp
        self.content = content
        self.add_class(f"msg-{role}")

    def compose(self) -> ComposeResult:
        with Vertical():
            if self.role == "assistant":
                with Horizontal(classes="msg-header"):
                    if self.provider:
                        yield Label(f" {self.provider.upper()} ", classes="provider-tag")
                    yield Label(f" {self.timestamp}", classes="timestamp")
            yield Markdown(self.content, id="msg-body")
            if self.role == "user":
                with Horizontal(classes="msg-footer"):
                    yield Label(f"{self.timestamp} ", classes="timestamp")
            elif self.latency > 0:
                yield Label(f"{self.latency:.2f}s", classes="latency-tag")

    def watch_content(self, new_content: str) -> None:
        """Update the Markdown widget when content changes."""
        try:
            md = self.query_one("#msg-body", Markdown)
            md.update(new_content)
        except Exception:
            pass

    def append_token(self, token: str) -> None:
        """Append a token to the message content (for streaming)."""
        self.content += token
