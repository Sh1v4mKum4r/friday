"""Syntax-highlighted code block with copy and collapse support."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from rich.syntax import Syntax

COLLAPSE_THRESHOLD = 50


class CodeBlock(Widget):
    """Syntax-highlighted code block."""

    is_collapsed: reactive[bool] = reactive(False)

    def __init__(
        self,
        code: str = "",
        language: str = "text",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.code = code
        self.language = language
        line_count = code.count("\n") + 1
        self.is_collapsed = line_count > COLLAPSE_THRESHOLD
        self._line_count = line_count

    def compose(self) -> ComposeResult:
        with Vertical(classes="code-block"):
            yield Label(
                f" {self.language}  [y] copy ",
                classes="code-header",
            )
            if self.is_collapsed:
                preview = "\n".join(self.code.splitlines()[:10])
                yield Static(
                    Syntax(preview, self.language, theme="monokai", line_numbers=False),
                    id="code-body",
                )
                yield Label(
                    f" ... {self._line_count} lines (Enter to expand) ",
                    classes="code-collapse-hint",
                )
            else:
                yield Static(
                    Syntax(self.code, self.language, theme="monokai", line_numbers=False),
                    id="code-body",
                )

    def toggle_collapse(self) -> None:
        self.is_collapsed = not self.is_collapsed
        self._rebuild()

    def _rebuild(self) -> None:
        self.remove_children()
        for child in self.compose():
            self.mount(child)

    def get_code(self) -> str:
        return self.code
