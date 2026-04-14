"""Smart input bar with mode-aware placeholder and thinking state."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Label

PLACEHOLDERS = {
    "chat": "Message Friday...",
    "command": "! shell or /friday command...",
    "search": "Search conversations...",
}


class InputBar(Widget):
    """Input bar with mode indicator and thinking state."""

    is_thinking: reactive[bool] = reactive(False)
    placeholder: reactive[str] = reactive("Message Friday...")

    class Submitted(Message):
        def __init__(self, value: str, mode: str) -> None:
            super().__init__()
            self.value = value
            self.mode = mode

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._mode = "chat"

    def compose(self) -> ComposeResult:
        with Vertical(id="input-area"):
            with Horizontal(classes="input-row"):
                yield Input(
                    placeholder=self.placeholder,
                    id="chat-input",
                )
                yield Label("Thinking...", id="thinking-label", classes="thinking-indicator hidden")

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        self.placeholder = PLACEHOLDERS.get(mode, "Message Friday...")
        try:
            inp = self.query_one("#chat-input", Input)
            inp.placeholder = self.placeholder
        except Exception:
            pass

    def set_thinking(self, thinking: bool) -> None:
        self.is_thinking = thinking
        try:
            label = self.query_one("#thinking-label", Label)
            if thinking:
                label.remove_class("hidden")
            else:
                label.add_class("hidden")
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        event.input.value = ""
        self.post_message(self.Submitted(value, self._mode))
