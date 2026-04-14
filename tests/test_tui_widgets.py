"""Tests for TUI widgets."""

import pytest
from textual.app import App, ComposeResult

from friday_ai.tui.widgets.message import MessageWidget


class MessageTestApp(App):
    """Minimal app for testing widgets."""

    def __init__(self, widget):
        super().__init__()
        self._widget = widget

    def compose(self) -> ComposeResult:
        yield self._widget


class TestMessageWidget:
    @pytest.mark.asyncio
    async def test_user_message_renders(self):
        widget = MessageWidget(
            content="Hello Friday",
            role="user",
            timestamp="12:04",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            assert pilot.app.query_one(MessageWidget)
            assert widget.role == "user"
            assert widget.content == "Hello Friday"

    @pytest.mark.asyncio
    async def test_assistant_message_renders(self):
        widget = MessageWidget(
            content="Hello! How can I help?",
            role="assistant",
            provider="ollama",
            latency=0.84,
            timestamp="12:04",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            assert msg.role == "assistant"
            assert msg.provider == "ollama"
            assert msg.latency == 0.84

    @pytest.mark.asyncio
    async def test_user_message_has_user_class(self):
        widget = MessageWidget(content="Hi", role="user", timestamp="12:00")
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            assert msg.has_class("msg-user")

    @pytest.mark.asyncio
    async def test_assistant_message_has_assistant_class(self):
        widget = MessageWidget(
            content="Hi", role="assistant", provider="ollama", timestamp="12:00",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            assert msg.has_class("msg-assistant")

    @pytest.mark.asyncio
    async def test_message_with_code_block(self):
        content = "Here is code:\n```python\nprint('hello')\n```"
        widget = MessageWidget(
            content=content, role="assistant", provider="ollama", timestamp="12:00",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            assert msg.content == content

    @pytest.mark.asyncio
    async def test_append_token(self):
        widget = MessageWidget(
            content="", role="assistant", provider="ollama", timestamp="12:00",
        )
        async with MessageTestApp(widget).run_test() as pilot:
            msg = pilot.app.query_one(MessageWidget)
            msg.append_token("Hello")
            msg.append_token(" world")
            assert msg.content == "Hello world"
