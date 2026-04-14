"""Chat/Command/Search mode switcher bar."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label

MODES = ("chat", "command", "search")


class ModeBar(Widget):
    """Displays and switches between Chat/Command/Search modes."""

    current_mode: reactive[str] = reactive("chat")

    class ModeChanged(Message):
        def __init__(self, mode: str) -> None:
            super().__init__()
            self.mode = mode

    def compose(self) -> ComposeResult:
        with Horizontal(id="mode-bar"):
            for mode in MODES:
                cls = "mode-active" if mode == self.current_mode else "mode-inactive"
                indicator = ">" if mode == self.current_mode else " "
                yield Label(f" {indicator} {mode.upper()} ", id=f"mode-{mode}", classes=cls)

    def set_mode(self, mode: str) -> None:
        if mode in MODES:
            self.current_mode = mode
            self.post_message(self.ModeChanged(mode))

    def watch_current_mode(self, new_mode: str) -> None:
        for mode in MODES:
            try:
                label = self.query_one(f"#mode-{mode}", Label)
                if mode == new_mode:
                    label.remove_class("mode-inactive")
                    label.add_class("mode-active")
                    indicator = ">"
                else:
                    label.remove_class("mode-active")
                    label.add_class("mode-inactive")
                    indicator = " "
                label.update(f" {indicator} {mode.upper()} ")
            except Exception:
                pass
